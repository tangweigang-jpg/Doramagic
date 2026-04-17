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

from doramagic_agent_core.core.fallback import RawFallback

from doramagic_constraint_agent.sop.constraint_schemas_v2 import (
    ConstraintSynthesisResult,
)

if TYPE_CHECKING:
    from doramagic_agent_core.core.agent_loop import ExtractionAgent

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
            # Persist raw text for post-mortem
            raw_dump = output_path.parent / "constraints_synthesis_raw.txt"
            try:
                raw_dump.write_text(result.text, encoding="utf-8")
                logger.error(
                    "constraint_synthesis: JSON extraction failed — "
                    "skipping rebalance, writing merged unchanged; raw text dumped to %s",
                    raw_dump,
                )
            except OSError:
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

    Robust recovery mirroring ``_recover_derive_from_raw``:
    1. Strip markdown code fences
    2. Greedy object match ``\\{[\\s\\S]*\\}`` to capture from first ``{`` to last ``}``
    3. Greedy array match as fallback (bare ``reviewed_constraints`` list)
    4. Validate the result; if only a bare list is present, wrap it

    Returns ``None`` if extraction or validation fails.
    """
    import re

    from pydantic import ValidationError

    # 0. Multi-fenced-block variant: several ```json {...}``` blocks scattered
    #    in a markdown report, each describing ONE reviewed constraint. Try this
    #    before fence-stripping because stripping merges all objects into an
    #    invalid concatenation.
    fenced_blocks = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw_text)
    if len(fenced_blocks) >= 2:
        aggregated: list[dict] = []
        for block in fenced_blocks:
            try:
                parsed = json.loads(block)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(parsed, dict):
                # Accept both single items and wrapper objects
                if "reviewed_constraints" in parsed and isinstance(
                    parsed["reviewed_constraints"], list
                ):
                    aggregated.extend(
                        p for p in parsed["reviewed_constraints"] if isinstance(p, dict)
                    )
                else:
                    aggregated.append(parsed)
        if aggregated:
            data = {
                "reviewed_constraints": [_normalize_synthesis_item(it) for it in aggregated],
                "rebalance_actions": [],
            }
            try:
                return ConstraintSynthesisResult.model_validate(data)
            except (ValidationError, ValueError):
                pass  # fall through to other recovery strategies

    # 1. Strip all markdown fences first
    cleaned = re.sub(r"```(?:json)?\s*\n?", "", raw_text)
    cleaned = re.sub(r"\n?```", "", cleaned)

    candidates: list[tuple[str, bool]] = []  # (text, is_bare_list)

    # 2. Greedy top-level object
    obj_match = re.search(r"\{[\s\S]*\}", cleaned)
    if obj_match:
        candidates.append((obj_match.group(0), False))

    # 3. Greedy top-level array (bare reviewed_constraints list)
    arr_match = re.search(r"\[[\s\S]*\]", cleaned)
    if arr_match:
        candidates.append((arr_match.group(0), True))

    for candidate, is_bare_list in candidates:
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue

        # Wrap bare list into expected schema shape
        if is_bare_list and isinstance(data, list):
            data = {"reviewed_constraints": data, "rebalance_actions": []}
        elif isinstance(data, dict) and "reviewed_constraints" not in data:
            # Some models return {"constraints": [...]} or similar — try to adapt
            for key in ("constraints", "items", "reviewed"):
                if isinstance(data.get(key), list):
                    data = {
                        "reviewed_constraints": data[key],
                        "rebalance_actions": data.get("rebalance_actions", []),
                    }
                    break

        # Normalize item shape variants — MiniMax sometimes emits
        # {id, original:{kind,severity,...}, modified:{kind,severity}, upgrade_reason}
        # instead of the flat expected shape.
        if isinstance(data, dict) and isinstance(data.get("reviewed_constraints"), list):
            data["reviewed_constraints"] = [
                _normalize_synthesis_item(item) for item in data["reviewed_constraints"]
            ]
            data.setdefault("rebalance_actions", [])

        try:
            return ConstraintSynthesisResult.model_validate(data)
        except (ValidationError, ValueError):
            continue

    # JSON extraction exhausted — try markdown parser as last resort
    return _parse_synthesis_from_markdown(cleaned)


def _normalize_synthesis_item(item: object) -> object:
    """Coerce LLM shape variants to SynthesizedConstraint fields.

    Maps ``id`` → ``original_index`` and flattens ``modified.{kind,severity}``
    to top-level ``constraint_kind`` / ``severity`` when present.
    Unknown shapes pass through unchanged.
    """
    if not isinstance(item, dict):
        return item
    out = dict(item)

    # id → original_index
    if "original_index" not in out and "id" in out:
        out["original_index"] = out.pop("id")

    # Flatten {modified|proposed|updated|new}.{kind,severity} if present
    for new_key in ("modified", "proposed", "updated", "new"):
        nested = out.get(new_key)
        if isinstance(nested, dict):
            if "constraint_kind" not in out:
                kind_val = nested.get("kind") or nested.get("constraint_kind")
                if kind_val:
                    out["constraint_kind"] = kind_val
            if "severity" not in out and "severity" in nested:
                out["severity"] = nested["severity"]

    # Fallback: pull from {original|current|old} if new side absent
    for old_key in ("original", "current", "old"):
        nested = out.get(old_key)
        if isinstance(nested, dict):
            if "constraint_kind" not in out:
                kind_val = nested.get("kind") or nested.get("constraint_kind")
                if kind_val:
                    out["constraint_kind"] = kind_val
            if "severity" not in out and "severity" in nested:
                out["severity"] = nested["severity"]

    # Flat variant: {id, kind, upgrade_kind, severity, upgrade_reason}
    if "constraint_kind" not in out:
        kind_val = out.get("upgrade_kind") or out.get("new_kind") or out.get("kind")
        if kind_val:
            out["constraint_kind"] = kind_val

    out.setdefault("upgrade_reason", "")
    out.setdefault("severity", "medium")
    return out


_KIND_VOCAB = (
    "domain_rule",
    "architecture_guardrail",
    "operational_lesson",
    "claim_boundary",
    "resource_boundary",
    "rationalization_guard",
)
_SEVERITY_VOCAB = ("fatal", "high", "medium", "low")


def _parse_synthesis_from_markdown(text: str) -> ConstraintSynthesisResult | None:
    """Parse kind-upgrade decisions out of a free-form markdown report.

    Tolerant of several LLM-emitted formats, e.g.::

        ### [13] kind=claim_boundary → kind=domain_rule (severity=fatal)
        **[13]** `operational_lesson` → **`domain_rule`**
        [13] operational_lesson → domain_rule

    Strategy: split the text into sections on ``[N]`` boundaries. In each
    section look for the first kind-vocab word after an arrow (→/->/—>) —
    that is the new kind. Severity is the first vocab word appearing in
    the section; defaults to ``medium``. Items without an arrow+new-kind
    are dropped.
    """
    import re

    from pydantic import ValidationError

    section_re = re.compile(r"\[(\d+)\]", re.MULTILINE)
    positions = [(m.start(), int(m.group(1))) for m in section_re.finditer(text)]
    if not positions:
        return None
    positions.append((len(text), -1))

    kind_alt = "|".join(_KIND_VOCAB)
    # Allow short token (e.g. "kind=", "**`") between arrow and kind name
    arrow_kind_re = re.compile(rf"(?:→|->|—>)[^\n]{{0,30}}?({kind_alt})\b", re.IGNORECASE)
    severity_re = re.compile(rf"\b({'|'.join(_SEVERITY_VOCAB)})\b", re.IGNORECASE)
    reason_re = re.compile(r"\*\*upgrade[_\s]reason\*\*\s*[:：]\s*([^\n]+)", re.IGNORECASE)

    items: list[dict] = []
    seen: set[int] = set()
    for i in range(len(positions) - 1):
        start, idx = positions[i]
        end = positions[i + 1][0]
        if idx < 0 or idx in seen:
            continue
        section = text[start:end]

        km = arrow_kind_re.search(section)
        if not km:
            continue
        new_kind = km.group(1).lower()

        sm = severity_re.search(section)
        severity = sm.group(1).lower() if sm else "medium"

        rm = reason_re.search(section)
        reason = rm.group(1).strip() if rm else ""

        items.append(
            {
                "original_index": idx,
                "constraint_kind": new_kind,
                "severity": severity,
                "upgrade_reason": reason,
            }
        )
        seen.add(idx)

    if not items:
        return None

    try:
        return ConstraintSynthesisResult.model_validate(
            {"reviewed_constraints": items, "rebalance_actions": []}
        )
    except (ValidationError, ValueError):
        return None
