"""Phase CD executor: Download repos + parallel extraction + community harvest + soul enrichment.

Complete pipeline:
1. Download candidate repos (ZIP from GitHub codeload)
2. Extract souls in parallel (cap 3 concurrent)
3. Harvest community signals per repo (serial)
4. Enrich souls with community findings (top 3 issues → unsaid_traps)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from doramagic_contracts.envelope import ErrorCodes, ModuleResultEnvelope, RunMetrics, WarningItem
from doramagic_contracts.executor import ExecutorConfig

logger = logging.getLogger("doramagic.executor.soul_batch")


def _ensure_scripts_importable() -> None:
    candidates = [
        Path(__file__).resolve().parent.parent.parent.parent / "skills" / "doramagic" / "scripts",
        Path.home() / "Documents" / "vibecoding" / "Doramagic" / "skills" / "doramagic" / "scripts",
        Path.home() / ".openclaw" / "skills" / "soul-extractor" / "scripts",
    ]
    for p in candidates:
        if (p / "github_search.py").exists() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
            return


class _RepoResult:
    def __init__(self, repo_id: str, success: bool, output_dir: str = "",
                 local_path: str = "", soul: dict | None = None,
                 error: str = "", metrics: RunMetrics | None = None):
        self.repo_id = repo_id
        self.success = success
        self.output_dir = output_dir
        self.local_path = local_path
        self.soul = soul or {}
        self.error = error
        self.metrics = metrics or RunMetrics(
            wall_time_ms=0, llm_calls=0, prompt_tokens=0,
            completion_tokens=0, estimated_cost_usd=0.0,
        )


class SoulExtractorBatch:
    """Downloads, extracts, harvests, and enriches — the full Phase CD pipeline."""

    async def execute(
        self, input: BaseModel, adapter: object, config: ExecutorConfig,
    ) -> ModuleResultEnvelope:
        start = time.monotonic()
        _ensure_scripts_importable()

        repos = self._get_repos(input)
        if not repos:
            return self._error("No repos to extract", ErrorCodes.NO_CANDIDATES, start)

        cap = config.concurrency_limit
        sem = asyncio.Semaphore(cap)
        repos_dir = config.run_dir / "repos"
        repos_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Download repos
        downloaded = await self._download_all(repos, repos_dir)
        downloadable = [d for d in downloaded if d.local_path]
        if not downloadable:
            return self._error(
                f"Failed to download all {len(repos)} repos",
                ErrorCodes.UPSTREAM_MISSING, start,
            )

        # Step 2: Parallel extraction
        extracted = await self._extract_all(downloadable, config, sem, adapter)
        successful = [r for r in extracted if r.success]
        failed = [r for r in extracted if not r.success]

        if not successful:
            return self._error(
                f"All {len(downloadable)} repos failed extraction",
                ErrorCodes.UPSTREAM_MISSING, start,
            )

        # Step 3: Community signals (serial)
        community_results = await self._harvest_community(repos)

        # Step 4: Enrich souls with community findings
        self._enrich_souls_with_community(successful, community_results)

        # Aggregate
        total_metrics = RunMetrics(
            wall_time_ms=int((time.monotonic() - start) * 1000),
            llm_calls=sum(r.metrics.llm_calls for r in extracted),
            prompt_tokens=sum(r.metrics.prompt_tokens for r in extracted),
            completion_tokens=sum(r.metrics.completion_tokens for r in extracted),
            estimated_cost_usd=sum(r.metrics.estimated_cost_usd for r in extracted),
            retries=sum(r.metrics.retries for r in extracted),
        )

        warnings: list[WarningItem] = []
        dl_failed = [d for d in downloaded if not d.local_path]
        if dl_failed:
            warnings.append(WarningItem(
                code="DOWNLOAD_FAILED",
                message=f"{len(dl_failed)} repos failed to download: {[d.repo_id for d in dl_failed]}",
            ))
        if failed:
            warnings.append(WarningItem(
                code="PARTIAL_EXTRACTION",
                message=f"{len(failed)}/{len(downloadable)} repos failed extraction",
            ))

        return ModuleResultEnvelope(
            module_name="SoulExtractorBatch",
            status="degraded" if (failed or dl_failed) else "ok",
            warnings=warnings,
            data={
                "successful_repos": [r.repo_id for r in successful],
                "failed_repos": [{"repo_id": r.repo_id, "error": r.error} for r in failed],
                "extraction_dirs": {r.repo_id: r.output_dir for r in successful},
                "souls": {r.repo_id: r.soul for r in successful},
                "community_signals": community_results,
                "project_summaries": self._build_summaries(successful),
            },
            metrics=total_metrics,
        )

    # ─── Step 1: Download ─────────────────────────────────────

    async def _download_all(
        self, repos: list[dict], repos_dir: Path,
    ) -> list[_RepoResult]:
        results = []
        for repo in repos:
            r = await asyncio.to_thread(self._download_one, repo, repos_dir)
            results.append(r)
        return results

    def _download_one(self, repo: dict, repos_dir: Path) -> _RepoResult:
        repo_id = repo.get("repo_id", "unknown")
        url = repo.get("url", "")
        full_name = repo.get("full_name", repo.get("name", ""))

        # Extract owner/repo from URL if needed
        if not full_name and "github.com/" in url:
            parts = url.rstrip("/").split("github.com/")[-1].split("/")
            if len(parts) >= 2:
                full_name = f"{parts[0]}/{parts[1]}"

        if not full_name:
            return _RepoResult(repo_id=repo_id, success=False, error="No repo name for download")

        try:
            from github_search import download_repo
            branch = repo.get("default_branch", "main")
            local_path = download_repo(full_name, branch, str(repos_dir / repo_id))
            if local_path:
                return _RepoResult(repo_id=repo_id, success=True, local_path=local_path)
            return _RepoResult(repo_id=repo_id, success=False, error="download_repo returned empty")
        except Exception as e:
            logger.warning(f"Download failed for {repo_id}: {e}")
            return _RepoResult(repo_id=repo_id, success=False, error=str(e))

    # ─── Step 2: Extraction ───────────────────────────────────

    async def _extract_all(
        self, repos: list[_RepoResult], config: ExecutorConfig,
        sem: asyncio.Semaphore, adapter: object,
    ) -> list[_RepoResult]:
        async def extract_one(repo: _RepoResult) -> _RepoResult:
            async with sem:
                return await asyncio.to_thread(
                    self._extract_sync, repo, config, adapter
                )
        tasks = [extract_one(r) for r in repos]
        return await asyncio.gather(*tasks)

    def _extract_sync(
        self, repo: _RepoResult, config: ExecutorConfig, adapter: object,
    ) -> _RepoResult:
        output_dir = str(config.run_dir / "staging" / repo.repo_id)
        start = time.monotonic()
        try:
            from doramagic_orchestration.phase_runner import run_single_project_pipeline
            result = run_single_project_pipeline(
                repo_path=repo.local_path,
                output_dir=output_dir,
                adapter=adapter,
                router=None,
                config=None,
            )
            elapsed = int((time.monotonic() - start) * 1000)

            # Read soul data from output
            soul = self._read_soul(output_dir)

            return _RepoResult(
                repo_id=repo.repo_id,
                success=not result.stages_failed,
                output_dir=output_dir,
                local_path=repo.local_path,
                soul=soul,
                error=", ".join(result.stages_failed) if result.stages_failed else "",
                metrics=RunMetrics(
                    wall_time_ms=elapsed, llm_calls=0,
                    prompt_tokens=0, completion_tokens=0,
                    estimated_cost_usd=0.0,
                ),
            )
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            logger.exception(f"Extraction failed for {repo.repo_id}: {e}")
            return _RepoResult(
                repo_id=repo.repo_id, success=False, error=str(e),
                metrics=RunMetrics(
                    wall_time_ms=elapsed, llm_calls=0,
                    prompt_tokens=0, completion_tokens=0, estimated_cost_usd=0.0,
                ),
            )

    def _read_soul(self, output_dir: str) -> dict:
        """Read extracted soul from output directory."""
        soul_dir = Path(output_dir) / "soul"
        if not soul_dir.exists():
            soul_dir = Path(output_dir)

        soul: dict[str, Any] = {}

        # Read essence/findings
        for name in ["essence.json", "stage1_output.json", "repo_soul.json"]:
            f = soul_dir / name
            if f.exists():
                try:
                    soul.update(json.loads(f.read_text(encoding="utf-8")))
                except (json.JSONDecodeError, OSError):
                    pass

        # Read repo_facts
        facts_path = Path(output_dir) / "artifacts" / "repo_facts.json"
        if facts_path.exists():
            try:
                soul["repo_facts"] = json.loads(facts_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        return soul

    # ─── Step 3: Community ────────────────────────────────────

    async def _harvest_community(self, repos: list[dict]) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for repo in repos:
            repo_id = repo.get("repo_id", "unknown")
            url = repo.get("url", "")
            if not url or "github.com" not in url:
                results[repo_id] = {"skipped": True, "skip_reason": "not a GitHub URL"}
                continue
            try:
                from community_signals import collect_community_signals
                signals = await asyncio.to_thread(collect_community_signals, url, None)
                results[repo_id] = signals
            except Exception as e:
                logger.warning(f"Community harvest failed for {repo_id}: {e}")
                results[repo_id] = {"skipped": True, "skip_reason": str(e)}
        return results

    # ─── Step 4: Enrich ───────────────────────────────────────

    def _enrich_souls_with_community(
        self, successful: list[_RepoResult], community: dict[str, Any],
    ) -> None:
        """Inject top community findings as unsaid_traps into souls.

        Replicates singleshot's soul enrichment logic (lines 593-601).
        """
        for repo in successful:
            signals = community.get(repo.repo_id, {})
            if signals.get("skipped"):
                continue

            top_issues = signals.get("signals", [])[:3]
            if not top_issues:
                continue

            # Inject as unsaid_traps
            existing_traps = repo.soul.get("unsaid_traps", [])
            if isinstance(existing_traps, list):
                for issue in top_issues:
                    trap = {
                        "trap": f"[Community] {issue.get('title', '')}",
                        "severity": "medium" if issue.get("tier", 3) <= 2 else "low",
                        "evidence": f"GitHub Issue #{issue.get('issue_number', '?')} ({issue.get('comment_count', 0)} comments)",
                        "source": "community",
                    }
                    existing_traps.append(trap)
                repo.soul["unsaid_traps"] = existing_traps

            # Add DSD metrics
            dsd = signals.get("dsd_metrics")
            if dsd:
                repo.soul["dsd_metrics"] = dsd

    # ─── Helpers ──────────────────────────────────────────────

    def _build_summaries(self, successful: list[_RepoResult]) -> list[dict]:
        """Build project summaries for synthesis input."""
        summaries = []
        for r in successful:
            soul = r.soul
            summaries.append({
                "project_id": r.repo_id,
                "repo": {"repo_id": r.repo_id, "full_name": r.repo_id, "url": ""},
                "top_capabilities": [
                    f.get("title", f.get("statement", ""))
                    for f in soul.get("findings", [])[:5]
                ] if soul.get("findings") else [],
                "top_constraints": [],
                "top_failures": [
                    t.get("trap", t) if isinstance(t, dict) else str(t)
                    for t in soul.get("unsaid_traps", [])[:3]
                ],
                "evidence_refs": [],
            })
        return summaries

    def _get_repos(self, input: BaseModel) -> list[dict[str, str]]:
        if isinstance(input, dict):
            return input.get("repos", [])
        if hasattr(input, "repos"):
            return input.repos
        return []

    def _error(self, msg: str, code: str, start: float) -> ModuleResultEnvelope:
        elapsed = int((time.monotonic() - start) * 1000)
        return ModuleResultEnvelope(
            module_name="SoulExtractorBatch",
            status="error", error_code=code,
            warnings=[WarningItem(code=code, message=msg)],
            metrics=RunMetrics(
                wall_time_ms=elapsed, llm_calls=0,
                prompt_tokens=0, completion_tokens=0, estimated_cost_usd=0.0,
            ),
        )

    def validate_input(self, input: BaseModel) -> list[str]:
        return ["No repos"] if not self._get_repos(input) else []

    def can_degrade(self) -> bool:
        return True
