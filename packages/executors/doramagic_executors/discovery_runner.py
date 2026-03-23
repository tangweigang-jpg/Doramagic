"""Phase B executor: Real GitHub search + candidate ranking.

Replaces the mock run_discovery() with actual GitHub API calls via github_search.py.
Also searches ClawHub and scans local OpenClaw skills.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from pydantic import BaseModel

from doramagic_contracts.base import NeedProfile
from doramagic_contracts.cross_project import (
    DiscoveryCandidate,
    DiscoveryInput,
    DiscoveryResult,
    SearchCoverageItem,
)
from doramagic_contracts.envelope import (
    ErrorCodes,
    ModuleResultEnvelope,
    RunMetrics,
    WarningItem,
)
from doramagic_contracts.executor import ExecutorConfig

MIN_STARS = 30


def _ensure_github_search_importable() -> None:
    """Add the scripts directory to sys.path so github_search is importable."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent.parent / "skills" / "doramagic" / "scripts",
        Path.home() / "Documents" / "vibecoding" / "Doramagic" / "skills" / "doramagic" / "scripts",
        Path.home() / ".openclaw" / "skills" / "soul-extractor" / "scripts",
    ]
    for p in candidates:
        if (p / "github_search.py").exists() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
            return


class DiscoveryRunner:
    """Searches GitHub, ClawHub, and local skills for candidate projects.

    Uses github_search.py (already proven in singleshot) for real GitHub API calls.
    Falls back to mock run_discovery() if GitHub is unavailable.
    """

    async def execute(
        self, input: BaseModel, adapter: object, config: ExecutorConfig,
    ) -> ModuleResultEnvelope[DiscoveryResult]:
        start = time.monotonic()
        warnings: list[WarningItem] = []

        if not isinstance(input, DiscoveryInput):
            return self._error("Expected DiscoveryInput", ErrorCodes.INPUT_INVALID, start)

        need = input.need_profile
        keywords = need.keywords[:3]  # GitHub search: top 3 keywords

        if not keywords:
            return self._error("No keywords for search", ErrorCodes.INPUT_INVALID, start)

        # 1. Real GitHub search
        github_candidates = self._search_github(keywords)

        # 2. ClawHub search (optional)
        clawhub_candidates = self._search_clawhub(keywords)

        # 3. Local skills scan (optional)
        local_candidates = self._scan_local_skills(keywords)

        # Merge and rank
        all_candidates = github_candidates + clawhub_candidates + local_candidates

        if not all_candidates:
            return ModuleResultEnvelope(
                module_name="DiscoveryRunner",
                status="blocked",
                error_code=ErrorCodes.NO_CANDIDATES,
                warnings=[WarningItem(code="NO_RESULTS", message="No candidates found for: " + " ".join(keywords))],
                data=DiscoveryResult(candidates=[], search_coverage=[
                    SearchCoverageItem(direction=kw, status="missing") for kw in keywords
                ]),
                metrics=self._metrics(start),
            )

        # Select top candidates for extraction (max 3)
        for i, c in enumerate(all_candidates[:3]):
            c.selected_for_phase_c = True

        result = DiscoveryResult(
            candidates=all_candidates,
            search_coverage=[
                SearchCoverageItem(
                    direction=kw,
                    status="covered" if any(kw.lower() in (c.name + c.contribution).lower() for c in all_candidates) else "partial",
                ) for kw in keywords
            ],
        )

        elapsed = int((time.monotonic() - start) * 1000)
        status = "ok" if github_candidates else "degraded"
        if not github_candidates:
            warnings.append(WarningItem(code="W_NO_GITHUB", message="GitHub search returned no results, using ClawHub/local only"))

        return ModuleResultEnvelope(
            module_name="DiscoveryRunner",
            status=status,
            warnings=warnings,
            data=result,
            metrics=self._metrics(start),
        )

    def _search_github(self, keywords: list[str]) -> list[DiscoveryCandidate]:
        """Real GitHub API search via github_search.py."""
        try:
            _ensure_github_search_importable()
            from github_search import search_github

            raw = search_github(keywords, top_k=6)
            candidates = []
            for i, r in enumerate(raw):
                stars = r.get("stars", 0)
                if stars < MIN_STARS:
                    continue
                candidates.append(DiscoveryCandidate(
                    candidate_id=f"gh-{i:03d}-{r['name'].replace('/', '-')}",
                    name=r["name"],
                    url=r["url"],
                    type="github_repo",
                    relevance="high" if i < 2 else "medium",
                    contribution=r.get("description", "")[:200],
                    quick_score=min(10, int(stars ** 0.3)),  # log-scale score
                    quality_signals={
                        "stars": stars,
                        "language": r.get("language", ""),
                        "updated_at": r.get("updated_at", ""),
                    },
                    selected_for_phase_c=False,
                    selected_for_phase_d=False,
                ))
            return candidates
        except Exception as e:
            return []  # Graceful degradation

    def _search_clawhub(self, keywords: list[str]) -> list[DiscoveryCandidate]:
        """Search ClawHub skill registry."""
        try:
            import json
            import urllib.request
            import urllib.parse

            query = " ".join(keywords[:3])
            url = f"https://clawhub.ai/api/search?q={urllib.parse.quote(query)}&limit=5"
            req = urllib.request.Request(url, headers={"User-Agent": "Doramagic/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            candidates = []
            for i, s in enumerate(data.get("results", data.get("skills", []))[:3]):
                candidates.append(DiscoveryCandidate(
                    candidate_id=f"clawhub-{s.get('slug', s.get('id', i))}",
                    name=s.get("displayName", s.get("name", "")),
                    url=f"clawhub:{s.get('slug', '')}",
                    type="community_skill",
                    relevance="medium",
                    contribution=s.get("summary", s.get("description", ""))[:200],
                    quick_score=min(10, int(s.get("score", 5))),
                    quality_signals={},
                    selected_for_phase_c=False,
                    selected_for_phase_d=True,
                ))
            return candidates
        except Exception:
            return []

    def _scan_local_skills(self, keywords: list[str]) -> list[DiscoveryCandidate]:
        """Scan locally installed OpenClaw skills."""
        skills_dir = Path.home() / ".openclaw" / "skills"
        if not skills_dir.exists():
            return []

        candidates = []
        try:
            for skill_dir in skills_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue

                content = skill_md.read_text(encoding="utf-8", errors="replace")[:2000]
                # Score by keyword match
                score = sum(1 for kw in keywords if kw.lower() in content.lower())
                if score == 0:
                    continue

                candidates.append(DiscoveryCandidate(
                    candidate_id=f"local-{skill_dir.name}",
                    name=skill_dir.name,
                    url=f"local:{skill_dir}",
                    type="community_skill",
                    relevance="low",
                    contribution=content[:200],
                    quick_score=min(10, score * 3),
                    quality_signals={"local": True},
                    selected_for_phase_c=False,
                    selected_for_phase_d=True,
                ))
        except Exception:
            pass

        return sorted(candidates, key=lambda c: c.quick_score, reverse=True)[:3]

    def _error(self, msg: str, code: str, start: float) -> ModuleResultEnvelope:
        return ModuleResultEnvelope(
            module_name="DiscoveryRunner",
            status="error",
            error_code=code,
            warnings=[WarningItem(code=code, message=msg)],
            metrics=self._metrics(start),
        )

    def _metrics(self, start: float) -> RunMetrics:
        return RunMetrics(
            wall_time_ms=int((time.monotonic() - start) * 1000),
            llm_calls=0, prompt_tokens=0, completion_tokens=0,
            estimated_cost_usd=0.0,
        )

    def validate_input(self, input: BaseModel) -> list[str]:
        if not isinstance(input, DiscoveryInput):
            return [f"Expected DiscoveryInput, got {type(input).__name__}"]
        return []

    def can_degrade(self) -> bool:
        return True  # Can degrade to ClawHub/local only
