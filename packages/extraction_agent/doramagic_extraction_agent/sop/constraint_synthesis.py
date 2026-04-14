"""Constraint synthesis: Instructor-based kind rebalance on merged constraint list.

Implements the ``con_constraint_synthesis`` phase of SOP v2.2.

The merged constraint list produced by prior extraction steps tends to
over-classify constraints as ``operational_lesson`` or ``claim_boundary``.
This module uses a structured Instructor call to review and upgrade those
entries to ``domain_rule`` or ``architecture_guardrail`` where warranted,
targeting ≥60% combined share for the two "hard rule" kinds.
"""

from __future__ import annotations

import json
import logging
import shutil
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from doramagic_extraction_agent.sop.constraint_schemas_v2 import (
    ConstraintSynthesisResult,
)
from doramagic_extraction_agent.sop.schemas_v5 import RawFallback

if TYPE_CHECKING:
    from doramagic_extraction_agent.core.agent_loop import ExtractionAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Threshold: QG-04 requires domain_rule + architecture_guardrail >= 60%.
# Skip rebalance when that condition is already met.
# ---------------------------------------------------------------------------
_QG04_THRESHOLD = 0.60  # 60% — skip rebalance when dr+ag already ≥ 60%
_REVIEW_KINDS = {"operational_lesson", "claim_boundary"}
_SUMMARY_MAX_ITEMS = 200
_WHEN_ACTION_CHARS = 50

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

CON_SYNTHESIS_V2_SYSTEM = """\
你是约束质量审查专家。你的任务是审查已提取的约束列表，纠正 kind 分类偏差。

## 问题
LLM 提取约束时倾向于将模棱两可的发现归为 operational_lesson 或 claim_boundary，
导致 domain_rule + architecture_guardrail 比例偏低（目标 ≥60%）。

## 审查规则
逐条审查 operational_lesson 和 claim_boundary 类型的约束：
- 描述工具/框架的客观规律（改了会崩/会出错）？ → 应为 domain_rule
- 描述代码的执行顺序/接口契约/模块边界？ → 应为 architecture_guardrail
- 确实是社区经验/踩坑总结（不遵守不会立即崩但会逐步腐败）？ → 保持 operational_lesson
- 确实是声明边界（不能对外宣称的能力）？ → 保持 claim_boundary

## severity 校准
- 数据完全不可用或直接金钱损失 → fatal
- 结果不准确但不崩溃 → high
- 仅影响效率或可读性 → medium
- 极低影响 → low

## 输出
只输出需要修改的条目。不需要修改的条目不要包含在 reviewed_constraints 中。
每条修改必须有 upgrade_reason 说明理由。
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_constraint_synthesis(
    agent: ExtractionAgent,
    merged_path: Path,
    output_path: Path,
) -> tuple[int, int]:
    """Run Instructor-based kind rebalance on merged constraints.

    Reads ``merged_path`` (constraints_merged.json), checks whether the
    proportion of ``operational_lesson`` + ``claim_boundary`` exceeds 40%.
    If not, the file is copied as-is.  If yes, calls the LLM via
    ``agent.run_structured_call`` to produce ``ConstraintSynthesisResult``
    and applies kind/severity patches back to the merged list.

    Args:
        agent: The active :class:`ExtractionAgent` instance.
        merged_path: Path to the merged constraints JSON file.
        output_path: Destination path for the rebalanced constraints JSON.

    Returns:
        ``(rebalanced_count, total_tokens)`` — number of constraints whose
        ``constraint_kind`` was changed, and total LLM tokens consumed.
        Both are 0 when rebalance is skipped.
    """
    # --- Load merged constraints ---
    raw_text = merged_path.read_text(encoding="utf-8")
    merged: list[dict] = json.loads(raw_text)
    total = len(merged)

    if total == 0:
        logger.warning("constraint_synthesis: merged list is empty — copying as-is")
        shutil.copy2(merged_path, output_path)
        return 0, 0

    # --- Kind distribution before rebalance ---
    kind_counts_before = Counter(c.get("constraint_kind", "unknown") for c in merged)
    _log_kind_distribution("before", kind_counts_before, total)

    by_kind = kind_counts_before
    dr_ag = by_kind.get("domain_rule", 0) + by_kind.get("architecture_guardrail", 0)
    dr_ag_ratio = dr_ag / total if total > 0 else 0

    if dr_ag_ratio >= _QG04_THRESHOLD:
        logger.info(
            "constraint_synthesis: dr+ag ratio=%.1f%% ≥ QG-04 threshold %.0f%% — "
            "already meets QG-04, skipping rebalance, copying merged → output",
            dr_ag_ratio * 100,
            _QG04_THRESHOLD * 100,
        )
        shutil.copy2(merged_path, output_path)
        return 0, 0

    soft_count = sum(by_kind[k] for k in _REVIEW_KINDS)
    logger.info(
        "constraint_synthesis: dr+ag ratio=%.1f%% < QG-04 threshold %.0f%% — "
        "launching Instructor rebalance (%d soft-kind items to review)",
        dr_ag_ratio * 100,
        _QG04_THRESHOLD * 100,
        soft_count,
    )

    # --- Build summary for LLM ---
    user_msg = _build_synthesis_summary(merged, max_items=_SUMMARY_MAX_ITEMS)

    # --- Instructor call with three-level degradation + timeout ---
    import asyncio

    try:
        result, total_tokens = await asyncio.wait_for(
            agent.run_structured_call(
                CON_SYNTHESIS_V2_SYSTEM,
                user_msg,
                ConstraintSynthesisResult,
            ),
            timeout=180,  # 3 min max for synthesis
        )
    except TimeoutError:
        logger.warning(
            "constraint_synthesis: Instructor call timed out after 180s, "
            "skipping rebalance and copying merged → output"
        )
        shutil.copy2(merged_path, output_path)
        return 0, 0

    rebalanced_count = 0

    if isinstance(result, RawFallback):
        # L2/L3 fallback — attempt JSON extraction from raw text
        logger.warning(
            "constraint_synthesis: Instructor returned RawFallback (stage=%s, %d chars) "
            "— attempting manual JSON extraction",
            result.stage,
            len(result.text),
        )
        extracted = _try_extract_synthesis_result(result.text)
        if extracted is not None:
            rebalanced_count = _apply_synthesis(merged, extracted)
            logger.info(
                "constraint_synthesis: manual JSON extraction succeeded — %d kind changes applied",
                rebalanced_count,
            )
        else:
            logger.error(
                "constraint_synthesis: JSON extraction failed — "
                "skipping rebalance, writing merged unchanged"
            )
    else:
        rebalanced_count = _apply_synthesis(merged, result)
        logger.info(
            "constraint_synthesis: Instructor L1/L2 success — %d kind changes applied (%d tokens)",
            rebalanced_count,
            total_tokens,
        )

    # --- Kind distribution after rebalance ---
    kind_counts_after = Counter(c.get("constraint_kind", "unknown") for c in merged)
    _log_kind_distribution("after", kind_counts_after, total)

    # --- Write output ---
    output_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(
        "constraint_synthesis: wrote %d constraints to %s",
        total,
        output_path,
    )

    return rebalanced_count, total_tokens


# ---------------------------------------------------------------------------
# Apply synthesis result
# ---------------------------------------------------------------------------


_MIN_KIND_RESERVE = 5  # minimum constraints to keep per kind (QG-02 guard)


def _apply_synthesis(
    merged: list[dict],
    result: ConstraintSynthesisResult,
) -> int:
    """Apply kind/severity changes from synthesis to merged list.

    Includes a safety guard: each constraint_kind must retain at least
    _MIN_KIND_RESERVE constraints after rebalance to prevent QG-02 failure
    (kind_coverage < 5).

    Returns count of constraints whose ``constraint_kind`` was changed.
    """
    # Pre-compute current kind counts
    kind_counts = Counter(c.get("constraint_kind", "") for c in merged)

    changes = 0
    for item in result.reviewed_constraints:
        idx = item.original_index
        if 0 <= idx < len(merged):
            old_kind = merged[idx].get("constraint_kind", "")
            # Safety: only allow modification of soft-kind constraints.
            if old_kind not in ("operational_lesson", "claim_boundary"):
                logger.warning(
                    "constraint_synthesis: synthesis tried to modify non-soft "
                    "constraint #%d (kind=%s) — skipping",
                    idx,
                    old_kind,
                )
                continue
            if old_kind != item.constraint_kind:
                # Guard: don't deplete a kind below the reserve minimum
                if kind_counts.get(old_kind, 0) <= _MIN_KIND_RESERVE:
                    logger.info(
                        "constraint_synthesis: [%d] skipping %s → %s "
                        "(would deplete %s below %d reserve)",
                        idx,
                        old_kind,
                        item.constraint_kind,
                        old_kind,
                        _MIN_KIND_RESERVE,
                    )
                    continue
                merged[idx]["constraint_kind"] = item.constraint_kind
                kind_counts[old_kind] -= 1
                kind_counts[item.constraint_kind] = kind_counts.get(item.constraint_kind, 0) + 1
                changes += 1
                logger.debug(
                    "constraint_synthesis: [%d] %s → %s (%s)",
                    idx,
                    old_kind,
                    item.constraint_kind,
                    item.upgrade_reason or "no reason",
                )
            merged[idx]["severity"] = item.severity
    return changes


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------


def _build_synthesis_summary(merged: list[dict], max_items: int = 200) -> str:
    """Build concise summary of constraints for the Instructor call.

    Only includes ``operational_lesson`` and ``claim_boundary`` constraints
    so the LLM focuses on the candidates that may need upgrading.

    Format per entry::

        [{index}] kind={kind} severity={severity}
          when: {when[:50]}...
          action: {action[:50]}...
    """
    lines: list[str] = [
        "以下是需要审查的约束条目（仅包含 operational_lesson / claim_boundary）：\n"
    ]
    included = 0
    for idx, constraint in enumerate(merged):
        kind = constraint.get("constraint_kind", "")
        if kind not in _REVIEW_KINDS:
            continue
        if included >= max_items:
            remaining = sum(
                1 for c in merged[idx:] if c.get("constraint_kind", "") in _REVIEW_KINDS
            )
            lines.append(f"\n... 还有 {remaining} 条未列出（已达 {max_items} 条上限）")
            break

        severity = constraint.get("severity", "")
        when_raw = constraint.get("when", "")
        action_raw = constraint.get("action", "")
        when_preview = when_raw[:_WHEN_ACTION_CHARS]
        action_preview = action_raw[:_WHEN_ACTION_CHARS]
        ellipsis_w = "..." if len(when_raw) > _WHEN_ACTION_CHARS else ""
        ellipsis_a = "..." if len(action_raw) > _WHEN_ACTION_CHARS else ""

        lines.append(
            f"[{idx}] kind={kind} severity={severity}\n"
            f"  when: {when_preview}{ellipsis_w}\n"
            f"  action: {action_preview}{ellipsis_a}"
        )
        included += 1

    if included == 0:
        lines.append("（无需审查的约束条目）")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _log_kind_distribution(label: str, counts: Counter, total: int) -> None:
    """Log kind distribution at INFO level."""
    dist = ", ".join(f"{k}={v}({v / total * 100:.1f}%)" for k, v in sorted(counts.items()))
    logger.info("constraint_synthesis kind distribution [%s]: %s", label, dist)


def _try_extract_synthesis_result(raw_text: str) -> ConstraintSynthesisResult | None:
    """Attempt to extract a ConstraintSynthesisResult from raw LLM text.

    Tries to find a JSON object inside triple-backtick blocks or bare JSON.
    Returns ``None`` if extraction or validation fails.
    """
    import re

    from pydantic import ValidationError

    # Try ```json ... ``` block first
    block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    candidates: list[str] = []
    if block_match:
        candidates.append(block_match.group(1))

    # Also try the first top-level {...} span
    brace_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if brace_match:
        candidates.append(brace_match.group(0))

    for candidate in candidates:
        try:
            data = json.loads(candidate)
            return ConstraintSynthesisResult.model_validate(data)
        except (json.JSONDecodeError, ValidationError, ValueError):
            continue

    return None
