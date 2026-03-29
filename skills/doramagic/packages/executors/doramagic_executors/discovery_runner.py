"""Phase B executor: targeted or broad discovery based on routing decision."""

from __future__ import annotations

import time

from doramagic_community.github_search import search_github
from doramagic_contracts.base import DiscoveryCandidate
from doramagic_contracts.cross_project import DiscoveryInput, DiscoveryResult
from doramagic_contracts.envelope import ErrorCodes, ModuleResultEnvelope, RunMetrics, WarningItem
from pydantic import BaseModel

MIN_STARS = 30


class DiscoveryRunner:
    async def execute(
        self, input: BaseModel, adapter: object, config
    ) -> ModuleResultEnvelope[DiscoveryResult]:
        started = time.monotonic()
        if not isinstance(input, DiscoveryInput):
            return self._error("Expected DiscoveryInput", ErrorCodes.INPUT_INVALID, started)

        need = input.need_profile
        routing = input.routing
        warnings: list[WarningItem] = []
        excluded = []

        if routing and routing.route == "NAMED_PROJECT":
            candidates = self._targeted_search(routing.project_names, routing.max_repos, config)
            search_evidence = [f"targeted:{name}" for name in routing.project_names]
        else:
            queries = need.github_queries or need.relevance_terms or need.keywords[:3]
            candidates = self._broad_search(queries, need.max_projects, config)
            search_evidence = [f"broad:{query}" for query in queries[:3]]

        filtered = []
        relevance_terms = [term.lower() for term in (need.relevance_terms or need.keywords[:4])]
        for candidate in candidates:
            searchable = f"{candidate.name} {candidate.contribution}".lower()
            if relevance_terms and not any(term in searchable for term in relevance_terms if term):
                excluded.append(candidate)
                continue
            filtered.append(candidate)

        for index, candidate in enumerate(filtered[: need.max_projects]):
            candidate.selected_for_phase_c = True
            candidate.why_selected = candidate.why_selected or (
                "top targeted match"
                if routing and routing.route == "NAMED_PROJECT"
                else "top domain match"
            )
            candidate.confidence = max(candidate.confidence, 0.9 if index == 0 else 0.72)

        result = DiscoveryResult(
            candidates=filtered[: need.max_projects],
            excluded_candidates=excluded[:5],
            search_coverage=[],
            search_evidence=search_evidence,
            candidate_count=len(filtered[: need.max_projects]),
            no_candidate_reason="" if filtered else "no relevant repositories found",
        )

        # D8: 0 候选时使用 degraded 而非 blocked, 保持与产品设计语义一致
        status = "ok" if result.candidate_count > 0 else "degraded"
        if excluded:
            warnings.append(
                WarningItem(
                    code="W_FILTERED",
                    message=f"Filtered {len(excluded)} candidate(s) by relevance gate",
                )
            )
        if status == "degraded":
            warnings.append(
                WarningItem(code="NO_RESULTS", message="Discovery found no relevant candidates")
            )

        return ModuleResultEnvelope(
            module_name="DiscoveryRunner",
            status=status,
            error_code=ErrorCodes.NO_CANDIDATES if status == "degraded" else None,
            warnings=warnings,
            data=result,
            metrics=RunMetrics(
                wall_time_ms=int((time.monotonic() - started) * 1000),
                llm_calls=0,
                prompt_tokens=0,
                completion_tokens=0,
                estimated_cost_usd=0.0,
            ),
        )

    def _emit_progress(self, config: object, query: str, candidate_count: int) -> None:
        event_bus = getattr(config, "event_bus", None)
        if event_bus is None:
            return
        event_bus.emit(
            "sub_progress",
            f"搜索 GitHub: '{query}'... 找到 {candidate_count} 个候选",
            phase="PHASE_B",
            meta={"query": query, "candidate_count": candidate_count},
        )

    def _targeted_search(self, names: list[str], limit: int, config: object) -> list:
        candidates = []
        for index, name in enumerate(names[:3]):
            results = search_github([name], top_k=4)
            self._emit_progress(config, name, len(results))
            for rank, repo in enumerate(results):
                stars = repo.get("stars", 0)
                if stars < MIN_STARS:
                    continue
                full_name = repo.get("name", "")
                score_bonus = 2 if name.lower() in full_name.lower() else 0
                candidates.append(
                    self._candidate(
                        repo,
                        candidate_id=f"gh-target-{index}-{rank}",
                        why_selected=f"matched named project `{name}`",
                        confidence=0.92 if score_bonus else 0.74,
                    )
                )
            if candidates:
                break
        return candidates[:limit]

    def _broad_search(self, queries: list[str], limit: int, config: object) -> list:
        merged = []
        seen = set()
        for query in queries[:3]:
            try:
                results = search_github([query], top_k=max(4, limit))
            except Exception:
                continue
            self._emit_progress(config, query, len(results))
            for repo in results:
                full_name = repo.get("name", "")
                if not full_name or full_name in seen or repo.get("stars", 0) < MIN_STARS:
                    continue
                seen.add(full_name)
                merged.append(
                    self._candidate(
                        repo,
                        candidate_id=f"gh-broad-{len(merged)}",
                        why_selected=f"broad exploration hit for `{query}`",
                        confidence=0.7,
                    )
                )
        return merged[:limit]

    def _candidate(self, repo: dict, *, candidate_id: str, why_selected: str, confidence: float):
        full_name = repo.get("name", "")
        repo_type_hint = "CATALOG" if full_name.lower().startswith("awesome-") else None
        extraction_profile = "shallow" if repo_type_hint == "CATALOG" else "deep"
        return DiscoveryCandidate(
            candidate_id=candidate_id,
            name=full_name,
            url=repo.get("url", ""),
            type="github_repo",
            relevance="high",
            contribution=repo.get("description", "")[:220],
            quick_score=min(10.0, max(1.0, repo.get("stars", 0) ** 0.3)),
            quality_signals={
                "stars": repo.get("stars", 0),
                "forks": repo.get("forks", 0),
                "last_updated": repo.get("updated_at", ""),
                "has_readme": True,
                "license": repo.get("license"),
            },
            source="github",
            confidence=confidence,
            why_selected=why_selected,
            repo_type_hint=repo_type_hint,
            extraction_profile=extraction_profile,
            selected_for_phase_c=False,
            selected_for_phase_d=False,
        )

    def _error(
        self, message: str, code: str, started: float
    ) -> ModuleResultEnvelope[DiscoveryResult]:
        return ModuleResultEnvelope(
            module_name="DiscoveryRunner",
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
        if not isinstance(input, DiscoveryInput):
            return ["DiscoveryRunner expects DiscoveryInput"]
        return []

    def can_degrade(self) -> bool:
        return True
