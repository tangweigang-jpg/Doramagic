"""Frozen-decision cache for BD evaluation results.

Once a BD passes Evaluator verification (VALID evidence + SUFFICIENT
rationale), it is frozen for the remainder of the extraction session.
Downstream steps (e.g. Step 2 patch, coverage-gap backfill) skip frozen
BDs, saving LLM tokens on re-evaluation.

Design source: Claude Code ``ContentReplacementState.seenIds`` — once a
tool result is judged (replace or keep), the decision is irreversible
for prompt-cache stability and to avoid redundant evaluation.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DecisionCache:
    """Track frozen BDs that need no further evaluation or enhancement."""

    def __init__(self) -> None:
        self._frozen: set[str] = set()

    # ------------------------------------------------------------------
    # Freeze from Evaluator report
    # ------------------------------------------------------------------

    def freeze_from_evaluation(
        self,
        report: dict[str, Any],
        all_bd_ids: list[str] | None = None,
    ) -> int:
        """Mark BDs that passed all four contracts as frozen.

        Args:
            report: The evaluation_report.json parsed as dict.
            all_bd_ids: Complete list of BD IDs from bd_list.json.
                When provided, any ID NOT in ``issue_ids`` is frozen.
                When absent, falls back to ``passed_ids`` from the report.

        Returns the number of newly frozen BDs.
        """
        if not report:
            return 0

        issue_ids = {issue.get("bd_id") for issue in report.get("issues", []) if issue.get("bd_id")}

        # Determine which BDs passed: prefer explicit list, fall back to report
        if all_bd_ids:
            candidate_ids = set(all_bd_ids)
        else:
            candidate_ids = self._all_evaluated_ids(report)

        new_frozen = 0
        for bd_id in candidate_ids:
            if bd_id not in issue_ids and bd_id not in self._frozen:
                self._frozen.add(bd_id)
                new_frozen += 1

        logger.info(
            "DecisionCache: frozen %d new BDs (%d total frozen, %d candidates, %d issues)",
            new_frozen,
            len(self._frozen),
            len(candidate_ids),
            len(issue_ids),
        )
        return new_frozen

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def is_frozen(self, bd_id: str) -> bool:
        return bd_id in self._frozen

    def needy_only(self, decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return only BDs that are NOT frozen — for Step 2 patch."""
        return [d for d in decisions if d.get("id") not in self._frozen]

    @property
    def frozen_count(self) -> int:
        return len(self._frozen)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _all_evaluated_ids(report: dict[str, Any]) -> set[str]:
        """Extract all BD IDs that appear in the evaluation report."""
        ids: set[str] = set()
        for issue in report.get("issues", []):
            bd_id = issue.get("bd_id")
            if bd_id:
                ids.add(bd_id)
        # Also check for a 'passed_ids' field if the evaluator provides one
        for bd_id in report.get("passed_ids", []):
            ids.add(bd_id)
        return ids
