"""Phase C executor: fan-out repo workers with isolated workspaces."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from doramagic_community.community_signals import collect_community_signals
from doramagic_community.github_search import download_repo
from doramagic_contracts.base import ExtractionAggregateContract, RepoExtractionEnvelope, RepoType
from doramagic_contracts.envelope import ErrorCodes, ModuleResultEnvelope, RunMetrics, WarningItem
from doramagic_contracts.executor import ExecutorConfig
from doramagic_extraction.brick_injection import load_and_inject_bricks
from pydantic import BaseModel

logger = logging.getLogger("doramagic.executor.worker_supervisor")


@dataclass
class RepoWorkerContext:
    worker_id: str
    repo_url: str
    repo_name: str
    repo_type_hint: str | None
    why_selected: str
    work_dir: Path
    token_budget: int
    cost_budget_usd: float
    timeout_seconds: int = 180


class WorkerSupervisor:
    async def execute(
        self, input: BaseModel, adapter: object, config: ExecutorConfig
    ) -> ModuleResultEnvelope[ExtractionAggregateContract]:
        started = time.monotonic()
        repos = list(getattr(input, "repos", []))
        if not repos:
            return self._error("No repos to extract", ErrorCodes.NO_CANDIDATES, started)

        contexts = self._allocate_workers(repos, config)
        envelopes = await asyncio.to_thread(self._fan_out, contexts, adapter, config)
        aggregate = self._collect(envelopes)
        status = "ok" if aggregate.success_count > 0 else "blocked"
        if 0 < aggregate.success_count < len(envelopes):
            status = "degraded"

        return ModuleResultEnvelope(
            module_name="WorkerSupervisor",
            status=status,
            error_code=ErrorCodes.UPSTREAM_MISSING if aggregate.success_count == 0 else None,
            warnings=self._warnings(envelopes),
            data=aggregate,
            metrics=RunMetrics(
                wall_time_ms=int((time.monotonic() - started) * 1000),
                llm_calls=sum(env.metrics.llm_calls for env in envelopes),
                prompt_tokens=sum(env.metrics.prompt_tokens for env in envelopes),
                completion_tokens=sum(env.metrics.completion_tokens for env in envelopes),
                estimated_cost_usd=sum(env.metrics.estimated_cost_usd for env in envelopes),
                retries=sum(env.metrics.retries for env in envelopes),
            ),
        )

    def _allocate_workers(
        self, repos: list[dict[str, Any]], config: ExecutorConfig
    ) -> list[RepoWorkerContext]:
        total_tokens = max(config.budget_remaining.remaining_tokens, 1)
        total_cost = max(config.budget_remaining.remaining_usd, 0.01)
        count = max(1, len(repos))
        per_worker_tokens = int(total_tokens * 0.8 / count)
        per_worker_cost = total_cost * 0.8 / count
        contexts = []
        for index, repo in enumerate(repos[: config.concurrency_limit or 3]):
            contexts.append(
                RepoWorkerContext(
                    worker_id=f"worker-{index}",
                    repo_url=repo.get("url", ""),
                    repo_name=repo.get("name") or repo.get("candidate_id", f"repo-{index}"),
                    repo_type_hint=repo.get("repo_type_hint"),
                    why_selected=repo.get("why_selected", ""),
                    work_dir=config.run_dir / "workers" / f"worker-{index}",
                    token_budget=per_worker_tokens,
                    cost_budget_usd=per_worker_cost,
                )
            )
        return contexts

    def _fan_out(
        self, contexts: list[RepoWorkerContext], adapter: object, config: ExecutorConfig
    ) -> list[RepoExtractionEnvelope]:
        from concurrent.futures import FIRST_COMPLETED, wait

        envelopes: list[RepoExtractionEnvelope] = []
        event_bus = getattr(config, "event_bus", None)
        total = len(contexts)
        with ThreadPoolExecutor(max_workers=min(config.concurrency_limit, len(contexts))) as pool:
            future_map = {}
            for index, context in enumerate(contexts, start=1):
                if event_bus is not None:
                    event_bus.emit(
                        "sub_progress",
                        f"分析 {context.repo_name} ({index}/{total})",
                        phase="PHASE_C",
                        worker_id=context.worker_id,
                        meta={
                            "repo_name": context.repo_name,
                            "index": index,
                            "total": total,
                        },
                    )
                future_map[pool.submit(self._run_worker, context, adapter, config)] = context
            pending = set(future_map.keys())
            while pending:
                max_timeout = max(future_map[f].timeout_seconds for f in pending)
                done, pending = wait(pending, timeout=max_timeout, return_when=FIRST_COMPLETED)
                if not done and pending:
                    # All remaining futures timed out
                    for future in pending:
                        future.cancel()
                        context = future_map[future]
                        envelopes.append(
                            self._failed_envelope(
                                context, f"Worker timed out after {context.timeout_seconds}s"
                            )
                        )
                    break
                for future in done:
                    context = future_map[future]
                    try:
                        envelopes.append(future.result(timeout=0))
                    except Exception as exc:
                        envelopes.append(self._failed_envelope(context, str(exc)))
        return envelopes

    def _run_worker(
        self, context: RepoWorkerContext, adapter: object, config: ExecutorConfig
    ) -> RepoExtractionEnvelope:
        started = time.monotonic()
        context.work_dir.mkdir(parents=True, exist_ok=True)
        if config.event_bus is not None:
            config.event_bus.emit(
                "worker_started",
                f"{context.repo_name} extraction started",
                phase="PHASE_C",
                worker_id=context.worker_id,
                status="started",
            )

        try:
            full_name = self._full_name_from_url(context.repo_url)
            if not full_name:
                raise RuntimeError(f"Cannot parse repo name from {context.repo_url}")

            local_path = download_repo(full_name, "main", str(context.work_dir / "repo"))
            if not local_path or Path(local_path).resolve() == Path.cwd().resolve():
                raise RuntimeError(
                    f"download_repo returned empty/CWD path for {full_name}; "
                    f"refusing to analyze current working directory"
                )
            output_dir = context.work_dir / "output"
            from doramagic_orchestration.phase_runner import run_single_project_pipeline

            result = run_single_project_pipeline(
                repo_path=local_path,
                output_dir=str(output_dir),
                adapter=adapter,
                router=None,
                config=None,
            )

            facts = self._load_json(output_dir / "artifacts" / "repo_facts.json")
            repo_type = self._classify_repo_type(context, facts)
            bricks = load_and_inject_bricks(
                facts.get("frameworks", []), output_dir=str(output_dir)
            ).raw_bricks

            if repo_type == "CATALOG":
                summary = self._shallow_extract(output_dir, facts)
            else:
                summary = self._deep_extract(output_dir, facts, bricks)

            community = {}
            try:
                community = collect_community_signals(context.repo_url, local_path, None)
            except Exception:
                community = {}

            envelope = RepoExtractionEnvelope(
                worker_id=context.worker_id,
                repo_name=context.repo_name,
                repo_url=context.repo_url,
                repo_type=repo_type,
                status="ok" if "stage0" in result.stages_completed else "partial",
                repo_facts=facts,
                extraction_profile_used="shallow" if repo_type == "CATALOG" else "deep",
                evidence_cards=summary["evidence_cards"],
                why_hypotheses=summary["why_hypotheses"],
                anti_patterns=summary["anti_patterns"],
                design_philosophy=summary["design_philosophy"],
                mental_model=summary["mental_model"],
                feature_inventory=summary["feature_inventory"],
                community_signals=community,
                extraction_confidence=summary["confidence"],
                evidence_count=len(summary["evidence_cards"]),
                warnings=[],
                metrics=RunMetrics(
                    wall_time_ms=int((time.monotonic() - started) * 1000),
                    llm_calls=0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    estimated_cost_usd=0.0,
                ),
            )
            if config.event_bus is not None:
                config.event_bus.emit(
                    "worker_completed",
                    f"{context.repo_name} extraction complete",
                    phase="PHASE_C",
                    worker_id=context.worker_id,
                    status=envelope.status,
                    meta={"repo_type": repo_type, "confidence": envelope.extraction_confidence},
                )
            return envelope
        except Exception as exc:
            envelope = self._failed_envelope(
                context, str(exc), int((time.monotonic() - started) * 1000)
            )
            if config.event_bus is not None:
                config.event_bus.emit(
                    "worker_failed",
                    f"{context.repo_name} extraction failed",
                    phase="PHASE_C",
                    worker_id=context.worker_id,
                    status="failed",
                    meta={"error": str(exc)},
                )
            return envelope

    def _classify_repo_type(self, context: RepoWorkerContext, facts: dict[str, Any]) -> RepoType:
        if context.repo_type_hint in ("TOOL", "FRAMEWORK", "CATALOG"):
            return context.repo_type_hint
        name = context.repo_name.lower()
        if name.startswith("awesome-") or name.endswith("-awesome"):
            return "CATALOG"
        frameworks = facts.get("frameworks", [])
        if frameworks:
            return "FRAMEWORK"
        return "TOOL"

    def _deep_extract(
        self, output_dir: Path, facts: dict[str, Any], bricks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        repo_summary = facts.get("repo_summary", "")
        frameworks = facts.get("frameworks", [])
        dependencies = facts.get("dependencies", [])
        commands = facts.get("commands", [])
        return {
            "design_philosophy": repo_summary
            or "Prefer extracted repo evidence over generic advice.",
            "mental_model": f"Frameworks: {', '.join(frameworks[:3])}"
            if frameworks
            else "General purpose tool",
            "why_hypotheses": [
                f"Uses {framework} as a core architectural choice" for framework in frameworks[:3]
            ]
            or ["Favors a practical implementation with explicit entrypoints."],
            "anti_patterns": [f"Avoid breaking {dependency}" for dependency in dependencies[:3]],
            "feature_inventory": commands[:5] or dependencies[:5] or frameworks[:5],
            "evidence_cards": [
                {
                    "kind": "repo_fact",
                    "summary": repo_summary,
                    "frameworks": frameworks[:3],
                    "bricks": [brick.get("brick_id") for brick in bricks[:3]],
                }
            ],
            "confidence": 0.82 if repo_summary else 0.66,
        }

    def _shallow_extract(self, output_dir: Path, facts: dict[str, Any]) -> dict[str, Any]:
        readme = ""
        for candidate in ("README.md", "readme.md"):
            path = output_dir.parent / "repo" / candidate
            if path.exists():
                readme = path.read_text(encoding="utf-8", errors="replace")[:4000]
                break
        link_density = readme.count("http://") + readme.count("https://")
        return {
            "design_philosophy": facts.get("repo_summary", "")
            or "Curated catalog for this domain.",
            "mental_model": "A catalog is useful as market context, not a deep implementation source.",
            "why_hypotheses": [
                "Treat this repository as a reference index instead of a deep code exemplar."
            ],
            "anti_patterns": ["Do not overfit to a catalog repository's README structure."],
            "feature_inventory": [f"external_links={link_density}"],
            "evidence_cards": [{"kind": "catalog", "summary": readme[:500]}],
            "confidence": 0.6,
        }

    def _collect(self, envelopes: list[RepoExtractionEnvelope]) -> ExtractionAggregateContract:
        coverage_matrix = {
            envelope.repo_name: envelope.feature_inventory[:5]
            for envelope in envelopes
            if envelope.status != "failed"
        }
        conflict_map = {}
        return ExtractionAggregateContract(
            repo_envelopes=envelopes,
            success_count=sum(1 for env in envelopes if env.status != "failed"),
            failed_count=sum(1 for env in envelopes if env.status == "failed"),
            coverage_matrix=coverage_matrix,
            conflict_map=conflict_map,
            ready_for_synthesis=any(env.status != "failed" for env in envelopes),
        )

    def _warnings(self, envelopes: list[RepoExtractionEnvelope]) -> list[WarningItem]:
        failed = [env for env in envelopes if env.status == "failed"]
        if not failed:
            return []
        return [
            WarningItem(
                code="PARTIAL_EXTRACTION",
                message=f"{len(failed)} repo worker(s) failed during extraction",
            )
        ]

    def _failed_envelope(
        self, context: RepoWorkerContext, error: str, elapsed_ms: int = 0
    ) -> RepoExtractionEnvelope:
        return RepoExtractionEnvelope(
            worker_id=context.worker_id,
            repo_name=context.repo_name,
            repo_url=context.repo_url,
            repo_type=context.repo_type_hint or "TOOL",
            status="failed",
            repo_facts={},
            extraction_profile_used="failed",
            evidence_cards=[],
            why_hypotheses=[],
            anti_patterns=[],
            feature_inventory=[],
            community_signals={},
            extraction_confidence=0.0,
            evidence_count=0,
            failure_scope=error[:300],
            warnings=[error[:300]],
            metrics=RunMetrics(
                wall_time_ms=elapsed_ms,
                llm_calls=0,
                prompt_tokens=0,
                completion_tokens=0,
                estimated_cost_usd=0.0,
            ),
        )

    def _full_name_from_url(self, url: str) -> str:
        if "github.com/" not in url:
            return ""
        parts = url.rstrip("/").split("github.com/")[-1].split("/")
        if len(parts) < 2:
            return ""
        return f"{parts[0]}/{parts[1]}"

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _error(
        self, message: str, code: str, started: float
    ) -> ModuleResultEnvelope[ExtractionAggregateContract]:
        return ModuleResultEnvelope(
            module_name="WorkerSupervisor",
            status="error",
            error_code=code,
            warnings=[WarningItem(code=code, message=message)],
            data=None,
            metrics=RunMetrics(
                wall_time_ms=int((time.monotonic() - started) * 1000),
                llm_calls=0,
                prompt_tokens=0,
                completion_tokens=0,
                estimated_cost_usd=0.0,
            ),
        )

    def validate_input(self, input: BaseModel) -> list[str]:
        if not hasattr(input, "repos"):
            return ["WorkerSupervisor expects repos"]
        return []

    def can_degrade(self) -> bool:
        return True
