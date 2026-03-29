"""Phase D executor: Community signal harvesting.

Stub-degradable: returns empty CommunityKnowledge + ClawHub data if GitHub API fails.
Full implementation built from community_signals.py.

Note: In the current PHASE_CD design, CommunityHarvester is called INSIDE
SoulExtractorBatch after extraction completes. This standalone executor exists
for future use when Phase D becomes independent.
"""

from __future__ import annotations

import time

from doramagic_contracts.cross_project import CommunityKnowledge, CommunityKnowledgeItem
from doramagic_contracts.envelope import ModuleResultEnvelope, RunMetrics, WarningItem
from doramagic_contracts.executor import ExecutorConfig
from pydantic import BaseModel


class CommunityHarvester:
    """Harvests community signals (GitHub Issues, ClawHub, CHANGELOG).

    Stub mode: returns empty CommunityKnowledge with ClawHub search results.
    Full mode: also scrapes GitHub Issues/Discussions and CHANGELOG.
    """

    async def execute(
        self,
        input: BaseModel,
        adapter: object,
        config: ExecutorConfig,
    ) -> ModuleResultEnvelope[CommunityKnowledge]:
        start = time.monotonic()
        warnings: list[WarningItem] = []

        # Extract keywords from input for ClawHub search
        keywords: list[str] = []
        if hasattr(input, "keywords"):
            keywords = input.keywords
        elif isinstance(input, dict):
            keywords = input.get("keywords", [])

        # ClawHub search (deterministic, no LLM, always available)
        clawhub_skills = self._search_clawhub(keywords)
        if not clawhub_skills:
            warnings.append(
                WarningItem(
                    code="W_CLAWHUB_EMPTY",
                    message="ClawHub returned no results",
                )
            )

        community = CommunityKnowledge(
            skills=clawhub_skills,
            tutorials=[],
            use_cases=[],
        )

        elapsed = int((time.monotonic() - start) * 1000)
        return ModuleResultEnvelope(
            module_name="CommunityHarvester",
            status="ok" if clawhub_skills else "degraded",
            warnings=warnings,
            data=community,
            metrics=RunMetrics(
                wall_time_ms=elapsed,
                llm_calls=0,
                prompt_tokens=0,
                completion_tokens=0,
                estimated_cost_usd=0.0,
            ),
        )

    def _search_clawhub(self, keywords: list[str]) -> list[CommunityKnowledgeItem]:
        """Search ClawHub skill registry. Returns matching skills."""
        if not keywords:
            return []

        try:
            import json
            import urllib.request

            query = " ".join(keywords[:3])
            url = f"https://clawhub.ai/api/search?q={urllib.parse.quote(query)}&limit=5"
            req = urllib.request.Request(url, headers={"User-Agent": "Doramagic/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            items = []
            for skill in data.get("skills", [])[:5]:
                items.append(
                    CommunityKnowledgeItem(
                        item_id=f"clawhub-{skill.get('id', 'unknown')}",
                        name=skill.get("name", ""),
                        source=f"clawhub:{skill.get('id', '')}",
                        kind="community_skill",
                        capabilities=skill.get("capabilities", []),
                        reusable_knowledge=skill.get("description", ""),
                    )
                )
            return items
        except Exception:
            return []  # Graceful degradation

    def validate_input(self, input: BaseModel) -> list[str]:
        return []  # Any input is acceptable

    def can_degrade(self) -> bool:
        return True  # Empty community knowledge is OK — synthesis continues
