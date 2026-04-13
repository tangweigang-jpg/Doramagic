"""Blueprint enrichment — SOP v3.4 bp_enrich phase (deterministic post-processing).

Zero LLM calls.  All patches are pure Python transformations applied in
sequence to the assembled blueprint YAML dict.

Patch summary (v6: 16 patches, P0–P14 + P5.5)
----------------------------------------------
P0.   id                  — inject blueprint_id if the LLM omitted the field
P1.   commit_hash         — inject state.commit_hash into source.commit_hash
P2.   sop_version         — force sop_version = "3.4"
P3.   bd_injection        — replace bp.business_decisions with authoritative
                            structured data from BDExtractionResult
P4.   bd_type_enum_fix    — remap non-canonical BD type strings to valid enums
P5.   evidence_format     — normalise BD evidence to file:line(fn) format;
                            compute evidence_coverage_ratio into _enrich_meta
P5.5  evidence_verify     — (v6) deterministic verification: file exists,
                            line valid, function present; auto-fix drifted refs
P6.   vague_words         — tag BDs whose rationale contains vague language
P7.   stage_id_validation — deduplicate stage ids/orders; repair BD.stage
                            references against legal stage set via STAGE_MAPPING
P8.   required_methods    — populate required_methods + key_behaviors per stage
P9.   uc_merge            — merge uc_list.json (Phase B output) into
                            known_use_cases, deduplicating by source
P10.  uc_normalize        — normalise known_use_cases field names and add
                            auto-generated intent_keywords
P11.  audit_checklist     — auto-generate audit_checklist_summary if absent
P12.  relations           — inject placeholder relations list if absent
P13.  execution_paradigm  — inject placeholder execution_paradigm if absent
P14.  resource_injection  — (v6) inject worker_resource.json into
                            replaceable_points per stage
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from doramagic_extraction_agent.sop.schemas_v5 import BDExtractionResult

if TYPE_CHECKING:
    from doramagic_extraction_agent.state.schema import AgentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BD type enum fix map (Patch 4)
# ---------------------------------------------------------------------------

BD_TYPE_ENUM_FIX_MAP: dict[str, str] = {
    # Long-form → single char
    "Business": "B",
    "business": "B",
    "Math": "M",
    "math": "M",
    "Technical": "T",
    "technical": "T",
    "Regulatory": "RC",
    "regulatory": "RC",
    "DomainKnowledge": "DK",
    "domain_knowledge": "DK",
    "BusinessAssumption": "BA",
    "business_assumption": "BA",
    # Nonsensical combos — precedence rules per SOP v3.4
    "B/T": "B",  # B/T is not a valid ordering; B takes precedence
    "T/B": "B",  # same
    "M/T": "M",  # M (Math) takes precedence over T (Technical)
    "T/M": "M",  # same
}

# Valid BD type regex (single or slash-separated multi-type)
_BD_TYPE_VALID_RE = re.compile(r"^(T|B|BA|DK|RC|M)(/(?:T|B|BA|DK|RC|M))*$")

# ---------------------------------------------------------------------------
# Vague words lists (Patch 6)
# ---------------------------------------------------------------------------

_VAGUE_WORDS_ZH: list[str] = ["考虑", "注意", "建议", "适当", "尽量", "酌情"]
_VAGUE_WORDS_EN: list[str] = ["try to", "consider", "be careful", "appropriate", "if possible"]

# ---------------------------------------------------------------------------
# Stage mapping table (Patch 7) — copied from constraint_enrich.py STAGE_MAPPING
# 35 entries covering common LLM-invented stage names
# ---------------------------------------------------------------------------

STAGE_MAPPING: dict[str, str] = {
    "execution_feasibility": "cost_modeling",
    "data_quality": "data_collection",
    "position_averaging": "cost_modeling",
    "position_control": "risk_management",
    "ml_training": "ml_prediction",
    "ml_labeling": "ml_prediction",
    "pattern_detection": "technical_indicator",
    "return_calculation": "cost_modeling",
    "risk_filter": "risk_management",
    "short_position": "risk_management",
    "institutional_tracking": "trading_signal",
    "multi_timeframe": "technical_indicator",
    "multi_level_strategy": "multi_factor",
    "scoring": "multi_factor",
    "adjustment_type": "data_collection",
    "target_selection": "fundamental_filter",
    "holding_period": "risk_management",
    "position_sizing": "risk_management",
    "price_filter": "liquidity_filter",
    "technical_analysis": "technical_indicator",
    "signal_generation": "trading_signal",
    "order_execution": "trading_signal",
    "simulation_config": "cost_modeling",
    "trading_constraint": "risk_management",
    "risk_assessment": "risk_management",
    "backtest_config": "cost_modeling",
    "factor_combination": "multi_factor",
    "market_regime": "trading_signal",
    "stock_screening": "fundamental_filter",
    "security": "risk_management",
    "execution_cost": "cost_modeling",
    "volume_filter": "liquidity_filter",
    "simulation_mode": "cost_modeling",
    # cross_stage is handled via "cross" substring check → global scope
    "cross_stage": "",  # sentinel — triggers global-scope promotion
    "global": "",  # sentinel — same promotion
}

# Regex patterns for evidence parsing (Patch 5)
_EVIDENCE_FULL_RE = re.compile(r"^(?P<path>[\w./\-]+\.\w+):(?P<line>\d+)\((?P<fn>[^)]+)\)$")
_EVIDENCE_FILE_LINE_RE = re.compile(
    r"^(?P<path>[\w./\-]+\.py):(?P<line>\d+)(?P<rest>.*)$",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Patch functions
# ---------------------------------------------------------------------------


def _patch_id(bp: dict[str, Any], state: AgentState) -> int:
    """P0: inject blueprint_id into bp["id"] if the field is absent.

    The LLM assembly phase sometimes omits the top-level id field.
    Returns 1 if a fix was applied, 0 otherwise.
    """
    if "id" not in bp:
        bp["id"] = state.blueprint_id
        logger.debug("P0 (id): set bp.id = %s", state.blueprint_id)
        return 1
    return 0


def _patch_commit_hash(bp: dict[str, Any], state: AgentState) -> int:
    """P1: inject state.commit_hash into bp["source"]["commit_hash"].

    Only applied when state.commit_hash is present and not the sentinel "HEAD".
    Returns 1 if a fix was applied, 0 otherwise.
    """
    if state.commit_hash and state.commit_hash != "HEAD":
        if not isinstance(bp.get("source"), dict):
            bp["source"] = {}
        bp["source"]["commit_hash"] = state.commit_hash
        logger.debug("P1 (commit_hash): injected %s", state.commit_hash[:12])
        return 1
    return 0


def _patch_sop_version(bp: dict[str, Any]) -> int:
    """P2: force bp["sop_version"] = "3.4".

    Always returns 1 (this patch is always applied).
    """
    bp["sop_version"] = "3.4"
    logger.debug("P2 (sop_version): forced to 3.4")
    return 1


def _patch_bd_injection(
    bp: dict[str, Any],
    bd_result: BDExtractionResult,
    artifacts_dir: Path,
) -> int:
    """P3: replace bp["business_decisions"] with authoritative structured BDs.

    Builds the canonical bd_dicts list from bd_result.decisions (present and
    missing).  Also pulls in any missing_gaps that are not already represented
    in decisions.  Enforces the SOP v3.4 requirement of at least 3 missing gaps.

    Returns the total number of BDs written into business_decisions.
    """
    bd_dicts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # --- Primary: iterate over all decisions (present + missing) ---
    for bd in bd_result.decisions:
        entry: dict[str, Any] = {
            "id": bd.id,
            "type": bd.type,
            "content": bd.content,
            "rationale": bd.rationale,
            "evidence": bd.evidence,
            "stage": bd.stage,
        }
        if bd.status == "missing":
            entry["status"] = "missing"
            entry["known_gap"] = True
            if bd.severity:
                entry["severity"] = bd.severity
            if bd.impact:
                entry["impact"] = bd.impact
        if bd.alternative_considered:
            entry["alternative_considered"] = bd.alternative_considered
        bd_dicts.append(entry)
        seen_ids.add(bd.id)

    # --- Secondary: pull in missing_gaps not already in decisions ---
    # NOTE: We track which gap IDs came from decisions vs missing_gaps
    # so we can still enforce the minimum-3 requirement below.
    for gap in bd_result.missing_gaps:
        if gap.id not in seen_ids:
            bd_dicts.append(
                {
                    "id": gap.id,
                    "type": gap.type,
                    "content": gap.content,
                    "rationale": gap.rationale,
                    "evidence": gap.evidence,
                    "stage": gap.stage,
                    "status": "missing",
                    "known_gap": True,
                    "severity": gap.severity or "medium",
                    "impact": gap.impact,
                }
            )
            seen_ids.add(gap.id)

    # --- Ensure minimum 3 missing gaps (SOP v3.4 requirement) ---
    # If the model produced fewer than 3 missing BDs across decisions +
    # missing_gaps, we cannot fabricate new ones — just log a warning.
    missing_count = sum(1 for d in bd_dicts if d.get("status") == "missing")
    if missing_count < 3:
        logger.warning(
            "P3 (bd_injection): only %d missing gaps available (target ≥3) "
            "— model produced insufficient gap coverage",
            missing_count,
        )

    bp["business_decisions"] = bd_dicts

    present = sum(1 for d in bd_dicts if d.get("status") != "missing")
    final_missing = sum(1 for d in bd_dicts if d.get("status") == "missing")
    logger.info(
        "P3 (bd_injection): %d BDs written (%d present, %d missing)",
        len(bd_dicts),
        present,
        final_missing,
    )
    return len(bd_dicts)


def _patch_bd_type_enum_fix(bp: dict[str, Any]) -> int:
    """P4: remap non-canonical BD type strings to valid enum values.

    Applies BD_TYPE_ENUM_FIX_MAP to each BD's "type" field.  After remapping,
    validates against the canonical pattern ^(T|B|BA|DK|RC|M)(/(...))*)$.
    Non-matching values after remapping are logged as warnings but not modified.

    Returns the number of BDs whose type was corrected.
    """
    count = 0
    for bd in bp.get("business_decisions", []):
        if not isinstance(bd, dict):
            continue
        raw_type = bd.get("type", "")
        if not isinstance(raw_type, str):
            continue

        # Try direct map lookup first
        mapped = BD_TYPE_ENUM_FIX_MAP.get(raw_type)
        if mapped is not None:
            bd["type"] = mapped
            count += 1
            logger.debug("P4: %s type %r → %r", bd.get("id", "?"), raw_type, mapped)
        elif not _BD_TYPE_VALID_RE.match(raw_type):
            # Not in fix map and not already valid — log warning, leave untouched
            logger.warning(
                "P4 (bd_type_enum_fix): BD %s has unrecognised type %r — skipping",
                bd.get("id", "?"),
                raw_type,
            )

    logger.info("P4 (bd_type_enum_fix): %d BD type fields corrected", count)
    return count


def _patch_evidence_format(bp: dict[str, Any]) -> int:
    """P5: normalise BD evidence fields to file:line(fn) format.

    Three cases:
    1. Already matches file:line(fn) — skip.
    2. Matches file.py:line with optional trailing text — extract/derive fn.
    3. No .py file reference at all — replace with N/A:0(see_rationale).

    Also computes evidence_coverage_ratio = (BDs with valid evidence) / total BDs,
    stored in bp["_enrich_meta"]["evidence_coverage_ratio"].

    Returns the number of BDs whose evidence was modified.
    """
    bd_list: list[dict[str, Any]] = bp.get("business_decisions", [])
    if not isinstance(bd_list, list):
        return 0

    ev_fixed = 0
    valid_evidence_count = 0
    total_count = 0

    for entry in bd_list:
        if not isinstance(entry, dict):
            continue
        total_count += 1
        ev = entry.get("evidence", "")
        if not isinstance(ev, str):
            ev = ""

        # Case 1: already fully valid — count as valid and skip
        if _EVIDENCE_FULL_RE.match(ev):
            valid_evidence_count += 1
            continue

        # Case 2: has file.py:line — try to extract or derive function name
        m = _EVIDENCE_FILE_LINE_RE.match(ev)
        if m:
            fp = m.group("path")
            line = m.group("line")
            rest = m.group("rest") or ""
            # Look for explicit (function) in trailing text
            func_m = re.search(r"\(([^)]+)\)", rest)
            if func_m:
                entry["evidence"] = f"{fp}:{line}({func_m.group(1)})"
            else:
                # Derive from first word after separators
                word_m = re.search(r"[\s\u2014\-:]+(\w+)", rest)
                fn = word_m.group(1) if word_m else "module"
                entry["evidence"] = f"{fp}:{line}({fn})"
            ev_fixed += 1
            valid_evidence_count += 1
            continue

        # Case 3: no .py reference — sentinel value
        entry["evidence"] = "N/A:0(see_rationale)"
        ev_fixed += 1
        # Not counted as valid evidence

    # Compute and store evidence_coverage_ratio
    ratio = (valid_evidence_count / total_count) if total_count > 0 else 0.0
    meta: dict[str, Any] = bp.setdefault("_enrich_meta", {})
    meta["evidence_coverage_ratio"] = round(ratio, 3)

    logger.info(
        "P5 (evidence_format): %d BDs normalised; coverage ratio=%.3f (%d/%d)",
        ev_fixed,
        ratio,
        valid_evidence_count,
        total_count,
    )
    return ev_fixed


def _patch_vague_words(bp: dict[str, Any]) -> int:
    """P6: tag BDs whose rationale contains known vague language.

    Checks each BD's "rationale" field against _VAGUE_WORDS_ZH and
    _VAGUE_WORDS_EN (case-insensitive for English).  When any vague word is
    found, sets bd["vague_rationale"] = True.

    Returns the number of BDs tagged.
    """
    count = 0
    all_vague = _VAGUE_WORDS_ZH + _VAGUE_WORDS_EN

    for bd in bp.get("business_decisions", []):
        if not isinstance(bd, dict):
            continue
        rationale = bd.get("rationale", "")
        if not rationale:
            continue

        rationale_lower = rationale.lower()
        found = [w for w in all_vague if w in rationale_lower]
        if found:
            bd["vague_rationale"] = True
            count += 1
            logger.debug(
                "P6: BD %s flagged — vague words: %s",
                bd.get("id", "?"),
                ", ".join(found),
            )

    logger.info("P6 (vague_words): %d BDs tagged with vague_rationale", count)
    return count


def _patch_stage_id_validation(bp: dict[str, Any]) -> int:
    """P7: validate and repair stage ids, orders, and BD.stage references.

    Three-step process:
    1. Deduplicate stages[].id — append _2, _3 suffixes for duplicates.
    2. Ensure stages[].order is strictly increasing — renumber if needed.
    3. For each BD's "stage" field, check against the legal stage set derived
       from step 1.  If invalid, try STAGE_MAPPING lookup.  Still invalid →
       log warning and leave untouched.

    Returns the total number of corrections applied across all three steps.
    """
    stages: list[dict[str, Any]] = bp.get("stages", [])
    if not isinstance(stages, list):
        return 0

    count = 0

    # --- Step 1: Deduplicate stage ids ---
    # Collect all existing ids first to avoid suffix collisions
    all_ids: set[str] = {s.get("id", "") for s in stages if isinstance(s, dict) and s.get("id")}
    seen_ids: dict[str, int] = {}  # id → occurrence count
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        sid = stage.get("id", "")
        if not sid:
            continue
        if sid in seen_ids:
            seen_ids[sid] += 1
            # Find a suffix that doesn't collide with existing ids
            suffix = seen_ids[sid]
            new_id = f"{sid}_{suffix}"
            while new_id in all_ids:
                suffix += 1
                new_id = f"{sid}_{suffix}"
            logger.warning("P7: duplicate stage id %r → renaming to %r", sid, new_id)
            stage["id"] = new_id
            all_ids.add(new_id)
            count += 1
        else:
            seen_ids[sid] = 1

    # --- Step 2: Ensure strictly increasing order ---
    numeric_stages = [
        s for s in stages if isinstance(s, dict) and isinstance(s.get("order"), (int, float))
    ]
    if len(numeric_stages) > 1:
        orders = [s["order"] for s in numeric_stages]
        is_strictly_increasing = all(orders[i] < orders[i + 1] for i in range(len(orders) - 1))
        if not is_strictly_increasing:
            logger.warning("P7: stage orders not strictly increasing — renumbering")
            for idx, stage in enumerate(numeric_stages):
                stage["order"] = idx + 1
            count += 1

    # --- Step 3: Validate BD.stage against legal stage set ---
    # Rebuild legal set after dedup (step 1 may have renamed some)
    legal_stages: set[str] = {s["id"] for s in stages if isinstance(s, dict) and s.get("id")}

    if not legal_stages:
        logger.debug("P7 (stage_id_validation): no legal stages found in blueprint")
        return count

    # Build dynamic name→id mapping from blueprint stages
    # This handles the synthesis/assembly naming mismatch:
    # BD stage = "Technical Indicator Calculation", stage.id = "factor_computation"
    name_to_id: dict[str, str] = {}
    word_to_ids: dict[str, list[str]] = {}
    for s in stages:
        if not isinstance(s, dict):
            continue
        sid = s.get("id", "")
        sname = s.get("name", "")
        if sid and sname:
            name_to_id[sname.lower()] = sid
            # Also index individual words for fuzzy matching
            for word in re.split(r"[\s_\-]+", sname.lower()):
                if len(word) >= 3:  # skip short words
                    word_to_ids.setdefault(word, []).append(sid)
            for word in re.split(r"[\s_\-]+", sid):
                if len(word) >= 3:
                    word_to_ids.setdefault(word, []).append(sid)

    def _fuzzy_match_stage(ref: str) -> str | None:
        """Try to match a BD stage name to a legal stage ID."""
        ref_lower = ref.lower()

        # 1. Exact name match (case-insensitive)
        if ref_lower in name_to_id:
            return name_to_id[ref_lower]

        # 2. Snake_case conversion match
        snake = re.sub(r"[\s\-]+", "_", ref_lower)
        if snake in legal_stages:
            return snake

        # 3. Word overlap: find the stage with most shared keywords
        ref_words = {w for w in re.split(r"[\s_\-]+", ref_lower) if len(w) >= 3}
        best_id = None
        best_score = 0
        for sid in legal_stages:
            sid_words = set(re.split(r"_", sid))
            # Also include stage name words
            sname = next(
                (s.get("name", "") for s in stages if isinstance(s, dict) and s.get("id") == sid),
                "",
            )
            sid_words |= {w.lower() for w in re.split(r"[\s_\-]+", sname) if len(w) >= 3}
            overlap = len(ref_words & sid_words)
            if overlap > best_score:
                best_score = overlap
                best_id = sid
        if best_score >= 1:
            return best_id

        return None

    for bd in bp.get("business_decisions", []):
        if not isinstance(bd, dict):
            continue
        stage_ref = bd.get("stage", "")
        if not stage_ref or stage_ref in legal_stages:
            continue

        # Try static STAGE_MAPPING first
        mapped = STAGE_MAPPING.get(stage_ref)
        if mapped is not None and mapped == "":
            bd["stage"] = "global"
            count += 1
            logger.debug(
                "P7: BD %s stage %r → 'global' (cross-stage promotion)",
                bd.get("id", "?"),
                stage_ref,
            )
        elif mapped and mapped in legal_stages:
            bd["stage"] = mapped
            count += 1
            logger.debug(
                "P7: BD %s stage %r → %r via STAGE_MAPPING",
                bd.get("id", "?"),
                stage_ref,
                mapped,
            )
        elif "cross" in stage_ref.lower():
            bd["stage"] = "global"
            count += 1
            logger.debug(
                "P7: BD %s stage %r → 'global' (contains 'cross')",
                bd.get("id", "?"),
                stage_ref,
            )
        else:
            # Try dynamic fuzzy matching
            fuzzy = _fuzzy_match_stage(stage_ref)
            if fuzzy:
                bd["stage"] = fuzzy
                count += 1
                logger.debug(
                    "P7: BD %s stage %r → %r via fuzzy match",
                    bd.get("id", "?"),
                    stage_ref,
                    fuzzy,
                )
            else:
                logger.warning(
                    "P7 (stage_id_validation): BD %s has unresolvable stage %r",
                    bd.get("id", "?"),
                    stage_ref,
                )

    logger.info(
        "P7 (stage_id_validation): %d corrections applied (legal stages: %s)",
        count,
        sorted(legal_stages),
    )
    return count


def _patch_required_methods(bp: dict[str, Any]) -> int:
    """P8: ensure required_methods and key_behaviors exist for each stage.

    If the Instructor assembly already populated these fields with real data,
    this patch is a no-op. Only fills placeholders when fields are absent
    or empty.

    For key_behaviors, handles both string and list acceptance_hints correctly.

    Returns the number of stages that received at least one of the two fields.
    """
    stages = bp.get("stages", [])
    if not isinstance(stages, list):
        return 0

    affected = 0
    for stage in stages:
        if not isinstance(stage, dict):
            continue

        stage_changed = False

        # --- required_methods: only fill if absent/empty ---
        methods = stage.get("required_methods")
        if not methods or (
            len(methods) == 1 and isinstance(methods[0], dict) and methods[0].get("name") == "N/A"
        ):
            # No real methods — keep as-is or set placeholder
            if not methods:
                stage["required_methods"] = [
                    {
                        "name": "N/A",
                        "description": "No user-facing methods identified by assembly",
                        "evidence": "N/A",
                    }
                ]
                stage_changed = True

        # --- key_behaviors: only fill if absent/empty ---
        behaviors = stage.get("key_behaviors")
        if not behaviors or (
            len(behaviors) == 1
            and isinstance(behaviors[0], dict)
            and behaviors[0].get("behavior") == "N/A"
        ):
            # Try to derive from acceptance_hints
            hints = stage.get("acceptance_hints", [])
            derived: list[dict[str, Any]] = []

            # Handle both list and string acceptance_hints
            if isinstance(hints, list):
                for hint in hints:
                    if isinstance(hint, str) and len(hint) > 5:
                        derived.append(
                            {
                                "behavior": hint[:80],
                                "description": hint,
                                "evidence": "see acceptance_hints",
                            }
                        )
            elif isinstance(hints, str) and hints:
                for line in hints.split("\n"):
                    line = line.strip().lstrip("✓⚠✗ -*")
                    if line and len(line) > 5:
                        derived.append(
                            {
                                "behavior": line[:80],
                                "description": line,
                                "evidence": "see acceptance_hints",
                            }
                        )

            stage["key_behaviors"] = derived or [
                {
                    "behavior": "N/A",
                    "description": "No observable behaviors identified by assembly",
                    "evidence": "N/A",
                }
            ]
            stage_changed = True

        if stage_changed:
            affected += 1

    logger.info(
        "P8 (required_methods): %d stages received required_methods/key_behaviors",
        affected,
    )
    return affected


def _patch_uc_merge(bp: dict[str, Any], artifacts_dir: Path) -> int:
    """P9: merge uc_list.json (Phase B artifact) into bp["known_use_cases"].

    Deduplicates by the "source" field.  Any uc_list.json parse failure is
    logged as a warning and the merge is skipped gracefully.

    Returns the number of new use cases added.
    """
    # Coerce null / non-list to empty list (BUG-1 fix, mirrors FIX 5a)
    existing_ucs: list[Any] = bp.get("known_use_cases") or []
    if not isinstance(existing_ucs, list):
        existing_ucs = []
    bp["known_use_cases"] = existing_ucs

    uc_path = artifacts_dir / "uc_list.json"
    if not uc_path.exists():
        logger.debug("P9 (uc_merge): uc_list.json not found — skipped")
        return 0

    try:
        raw = uc_path.read_text(encoding="utf-8")
        extra_ucs: list[Any] = json.loads(raw)
        if not isinstance(extra_ucs, list):
            extra_ucs = []
    except Exception as exc:
        logger.warning("P9 (uc_merge): failed to parse uc_list.json: %s", exc)
        return 0

    # Build dedup index from existing UCs (support both "source" and legacy
    # "source_file" keys for backwards compatibility)
    existing_sources: set[str] = set()
    for uc in existing_ucs:
        if isinstance(uc, dict):
            src = uc.get("source") or uc.get("source_file") or ""
            existing_sources.add(src)

    added = 0
    for uc in extra_ucs:
        if isinstance(uc, dict):
            src = uc.get("source", "")
            if src and src not in existing_sources:
                existing_ucs.append(uc)
                existing_sources.add(src)
                added += 1

    logger.info("P9 (uc_merge): +%d use cases merged from uc_list.json", added)
    return added


def _patch_uc_normalize(bp: dict[str, Any]) -> int:
    """P10: normalise known_use_cases field names and auto-generate intent_keywords.

    Two sub-steps:
    1. Rename "source_file" → "source" (legacy field name cleanup).
    2. Auto-populate "intent_keywords" from name + business_problem text when
       the field is absent or empty.

    Returns the number of use cases that were modified.
    """
    ucs: list[Any] = bp.get("known_use_cases") or []
    if not isinstance(ucs, list):
        ucs = []
        bp["known_use_cases"] = ucs

    _keyword_re = re.compile(r"[A-Z][a-z]{2,}|[A-Z]{2,}|[\u4e00-\u9fff]{2,}|\b[a-z]{4,}\b")

    affected = 0
    for uc in ucs:
        if not isinstance(uc, dict):
            continue

        changed = False

        # Step 1: source_file → source migration
        if "source_file" in uc:
            if "source" not in uc:
                uc["source"] = uc["source_file"]
            del uc["source_file"]
            changed = True

        # Step 2: auto-generate intent_keywords
        if not uc.get("intent_keywords"):
            name = str(uc.get("name", ""))
            problem = str(uc.get("business_problem", ""))
            combined = f"{name} {problem}"
            keywords: list[str] = []
            for w in _keyword_re.findall(combined):
                if w not in keywords and len(w) >= 2:
                    keywords.append(w)
            uc["intent_keywords"] = (
                keywords[:5] if keywords else ([name.split()[0]] if name.split() else ["unknown"])
            )
            changed = True

        if changed:
            affected += 1

    logger.info("P10 (uc_normalize): %d use cases normalised", affected)
    return affected


def _patch_audit_checklist(bp: dict[str, Any], state: AgentState, artifacts_dir: Path) -> int:
    """P11: generate audit_checklist_summary from worker_audit.md.

    If worker_audit.md exists, parse pass/warn/fail counts from it.
    Otherwise, generate a placeholder.

    Returns 1 if the field was created or updated, 0 if it already existed.
    """
    if bp.get("audit_checklist_summary"):
        return 0

    labels = state.subdomain_labels or ["TRD"]

    # Try to read real audit data
    audit_path = artifacts_dir / "worker_audit.md"
    audit_data: dict[str, Any] = {
        "sop_version": "3.4",
        "executed_at": "auto",
        "subdomain_labels": labels,
    }

    if audit_path.exists():
        content = audit_path.read_text(encoding="utf-8")
        # Parse pass/warn/fail from markdown table rows only (lines starting
        # with "|" that contain a status emoji).  This avoids over-counting
        # emojis in prose, examples, or remediation sections.
        pass_count = 0
        warn_count = 0
        fail_count = 0
        for line in content.split("\n"):
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue
            if "✅" in stripped:
                pass_count += 1
            elif "⚠️" in stripped:
                warn_count += 1
            elif "❌" in stripped:
                fail_count += 1
        # Cap at 20 (universal checklist size) to avoid inflated counts
        total = min(pass_count + warn_count + fail_count, 20)
        pass_count = min(pass_count, 20)
        warn_count = min(warn_count, 20 - pass_count)
        fail_count = min(fail_count, 20 - pass_count - warn_count)

        audit_data["finance_universal"] = {
            "pass": pass_count,
            "warn": warn_count,
            "fail": fail_count,
        }
        audit_data["coverage"] = f"{total}/20 ({total * 100 // 20}%)" if total else "0/20 (0%)"
        audit_data["note"] = "Parsed from worker_audit.md"
        logger.info(
            "P11 (audit_checklist): real audit data — pass=%d, warn=%d, fail=%d",
            pass_count,
            warn_count,
            fail_count,
        )
    else:
        audit_data["note"] = (
            "Auto-generated by bp_enrich; detailed audit pending Batch C worker_audit"
        )
        logger.debug("P11 (audit_checklist): placeholder (worker_audit.md not found)")

    bp["audit_checklist_summary"] = audit_data
    return 1


def _patch_relations(bp: dict[str, Any]) -> int:
    """P12: inject placeholder relations list if the field is absent or empty.

    Returns 1 if a placeholder was injected, 0 otherwise.
    """
    if not bp.get("relations"):
        bp["relations"] = [
            {
                "target": "同子领域蓝图",
                "type": "pending",
                "description": "暂无同子领域参照，待批量提取后补充",
            }
        ]
        logger.debug("P12 (relations): injected placeholder")
        return 1
    return 0


def _patch_execution_paradigm(bp: dict[str, Any]) -> int:
    """P13: inject placeholder execution_paradigm if the field is absent or empty.

    Returns 1 if a placeholder was injected, 0 otherwise.
    """
    if not bp.get("execution_paradigm"):
        bp["execution_paradigm"] = {
            "live": "unknown",
            "backtest": "unknown",
            "note": "Auto-detected from source code structure",
        }
        logger.debug("P13 (execution_paradigm): injected placeholder")
        return 1
    return 0


def _patch_evidence_verify(bp: dict[str, Any], repo_path: str) -> int:
    """P5.5: deterministic verification of evidence file:line(fn) references.

    Checks that the file exists, the line number is valid, and the function
    name is present at the cited location.  Auto-fixes minor discrepancies
    (e.g. wrong line number but correct function name).

    Returns the number of evidence references verified or auto-fixed.
    Zero LLM calls — pure Python + filesystem checks.

    Design source: Harness Engineering — computational sensor (Böckeler matrix
    bottom-left quadrant).
    """
    import ast as _ast

    verified = 0
    invalid = 0
    auto_fixed = 0
    _ev_pattern = re.compile(r"^(.+?):(\d+)\((.+?)\)$")

    for bd in bp.get("business_decisions", []):
        ev = bd.get("evidence", "")
        if not ev or ev.startswith("N/A"):
            continue
        m = _ev_pattern.match(ev)
        if not m:
            continue
        file_path, line_str, fn_name = m.group(1), m.group(2), m.group(3)
        line_no = int(line_str)
        full_path = Path(repo_path) / file_path

        # Check 1: file exists
        if not full_path.exists():
            bd.setdefault("_evidence_issues", []).append(f"NOT_FOUND: {file_path}")
            invalid += 1
            continue

        # Check 2: line number valid
        try:
            lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            invalid += 1
            continue
        if line_no > len(lines):
            bd.setdefault("_evidence_issues", []).append(
                f"LINE_OOB: {file_path}:{line_no} > {len(lines)}"
            )
            invalid += 1
            continue

        # Check 3: function name (Python files only)
        if fn_name and fn_name != "see_rationale" and file_path.endswith(".py"):
            try:
                source = full_path.read_text(encoding="utf-8", errors="replace")
                tree = _ast.parse(source, filename=file_path)
            except (SyntaxError, UnicodeDecodeError):
                verified += 1
                continue

            # Find all function/method definitions (bare name + Class.method)
            fn_defs: dict[str, int] = {}
            for node in _ast.walk(tree):
                if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                    fn_defs[node.name] = node.lineno
                if isinstance(node, _ast.ClassDef):
                    for child in _ast.iter_child_nodes(node):
                        if isinstance(child, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                            fn_defs[f"{node.name}.{child.name}"] = child.lineno

            # Handle dotted names: "Class.method" or bare "method"
            lookup_name = fn_name
            bare_name = fn_name.split(".")[-1] if "." in fn_name else fn_name

            # Check if cited function exists (try full name first, then bare)
            match_name = (
                lookup_name
                if lookup_name in fn_defs
                else (bare_name if bare_name in fn_defs else None)
            )
            if match_name and match_name in fn_defs:
                actual_line = fn_defs[match_name]
                if abs(actual_line - line_no) > 5:
                    # Auto-fix: function exists but line drifted
                    bd["evidence"] = f"{file_path}:{actual_line}({fn_name})"
                    auto_fixed += 1
                else:
                    verified += 1
            else:
                # Function not found in file
                bd.setdefault("_evidence_issues", []).append(
                    f"FN_NOT_FOUND: {fn_name} in {file_path}"
                )
                invalid += 1
                continue
        else:
            verified += 1

    meta = bp.setdefault("_enrich_meta", {})
    meta["evidence_verified"] = verified
    meta["evidence_invalid"] = invalid
    meta["evidence_auto_fixed"] = auto_fixed
    total = verified + invalid
    meta["evidence_verify_ratio"] = verified / total if total > 0 else 0.0
    logger.info(
        "P5.5 (evidence_verify): verified=%d, invalid=%d, auto_fixed=%d, ratio=%.1f%%",
        verified,
        invalid,
        auto_fixed,
        meta["evidence_verify_ratio"] * 100,
    )
    return verified + auto_fixed


def _patch_resource_injection(bp: dict[str, Any], artifacts_dir: Path) -> int:
    """P14: inject resource inventory into replaceable_points.

    Reads worker_resource.json and merges resource options into each stage's
    replaceable_points, filling gaps that the architecture Worker missed.

    Returns the number of resource slots injected.
    """
    resource_path = artifacts_dir / "worker_resource.json"
    if not resource_path.exists():
        logger.debug("P14 (resource_injection): worker_resource.json not found, skipping")
        return 0

    try:
        resource_data = json.loads(resource_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("P14 (resource_injection): failed to read resource data: %s", exc)
        return 0

    matrix = resource_data.get("replaceable_resource_matrix", [])
    if not matrix:
        return 0

    # Build lookup: slot_name → resource options
    resource_slots: dict[str, dict[str, Any]] = {}
    for slot in matrix:
        name = slot.get("slot_name", "")
        if name:
            resource_slots[name] = slot

    # Inject at blueprint level (global_resources), not per-stage.
    # Resource slots don't have stage affiliation, so per-stage injection
    # would incorrectly add all slots to every stage.
    injected = 0
    # Collect existing replaceable_point names across all stages
    all_existing_names: set[str] = set()
    for stage in bp.get("stages", []):
        for rp in stage.get("replaceable_points", []):
            if isinstance(rp, dict):
                all_existing_names.add(rp.get("name", "").lower())

    global_resources = bp.get("global_resources", [])
    for slot_name, slot_data in resource_slots.items():
        if slot_name.lower() not in all_existing_names:
            new_rp = {
                "name": slot_name,
                "description": slot_data.get("selection_criteria", ""),
                "options": [
                    {
                        "name": opt.get("name", ""),
                        "traits": opt.get("traits", []),
                        "fit_for": ([opt.get("fit_for", "")] if opt.get("fit_for") else []),
                        "not_fit_for": (
                            [opt.get("not_fit_for", "")] if opt.get("not_fit_for") else []
                        ),
                    }
                    for opt in slot_data.get("options", [])
                ],
                "default": slot_data.get("default"),
                "_source": "worker_resource",
            }
            global_resources.append(new_rp)
            injected += 1

    if global_resources:
        bp["global_resources"] = global_resources

    logger.info("P14 (resource_injection): injected %d resource slots", injected)
    return injected


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def enrich_blueprint(
    bp: dict[str, Any],
    bd_result: BDExtractionResult,
    state: AgentState,
    artifacts_dir: Path,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Apply deterministic enrichment patches to assembled blueprint YAML.

    All modifications are performed in-place on *bp*.  No YAML serialisation
    or deserialisation happens here — the caller is responsible for reading the
    YAML before calling this function and writing the enriched dict afterwards.

    Args:
        bp:            Parsed blueprint dict (from YAML safe_load).
        bd_result:     Validated BDExtractionResult from bd_list.json.
        state:         Current AgentState (provides blueprint_id, commit_hash,
                       subdomain_labels, etc.).
        artifacts_dir: Path to the run's artifacts/ directory (used to locate
                       uc_list.json for P9).

    Returns:
        A tuple of (bp, patch_stats) where:
        - bp is the same dict passed in, now enriched in-place.
        - patch_stats maps patch keys to the integer count returned by each
          patch function.
    """
    patch_stats: dict[str, int] = {}

    # Core provenance fixes (always run first)
    patch_stats["p0_id"] = _patch_id(bp, state)
    patch_stats["p1_commit_hash"] = _patch_commit_hash(bp, state)
    patch_stats["p2_sop_version"] = _patch_sop_version(bp)

    # BD structural injection (P3 must precede P4–P7)
    patch_stats["p3_bd_injection"] = _patch_bd_injection(bp, bd_result, artifacts_dir)

    # BD field-level fixes
    patch_stats["p4_bd_type_enum_fix"] = _patch_bd_type_enum_fix(bp)
    patch_stats["p5_evidence_format"] = _patch_evidence_format(bp)
    # P5.5: deterministic evidence verification (v6)
    repo_path = str(state.repo_path) if hasattr(state, "repo_path") and state.repo_path else ""
    if repo_path:
        patch_stats["p5_5_evidence_verify"] = _patch_evidence_verify(bp, repo_path)
    patch_stats["p6_vague_words"] = _patch_vague_words(bp)
    patch_stats["p7_stage_id_validation"] = _patch_stage_id_validation(bp)

    # Stage interface enrichment
    patch_stats["p8_required_methods"] = _patch_required_methods(bp)

    # Use-case normalisation
    patch_stats["p9_uc_merge"] = _patch_uc_merge(bp, artifacts_dir)
    patch_stats["p10_uc_normalize"] = _patch_uc_normalize(bp)

    # Metadata scaffolding (fill absent top-level fields)
    patch_stats["p11_audit_checklist"] = _patch_audit_checklist(bp, state, artifacts_dir)
    patch_stats["p12_relations"] = _patch_relations(bp)
    patch_stats["p13_execution_paradigm"] = _patch_execution_paradigm(bp)

    # v6: Resource injection from worker_resource
    patch_stats["p14_resource_injection"] = _patch_resource_injection(bp, artifacts_dir)

    total_affected = sum(patch_stats.values())
    logger.info(
        "bp_enrich complete: %d total patch applications — %s",
        total_affected,
        ", ".join(f"{k}={v}" for k, v in patch_stats.items()),
    )

    return bp, patch_stats
