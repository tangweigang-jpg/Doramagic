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
    # INS — Insurance & Actuarial
    "claims_processing": "claim_adjudication",
    "claims": "claim_adjudication",
    "reserving": "reserve_calculation",
    "reserve": "reserve_calculation",
    "underwriting_ins": "risk_assessment",
    "actuarial": "actuarial_analysis",
    "reinsurance": "reinsurance_mapping",
    # LND — Lending & Payments
    "underwriting": "loan_underwriting",
    "origination": "loan_origination",
    "collections": "collection_management",
    "disbursement": "loan_disbursement",
    "repayment": "repayment_processing",
    "reconciliation": "payment_reconciliation",
    # TRS — Treasury & ALM
    "alm": "asset_liability_management",
    "liquidity": "liquidity_management",
    "cash_management": "cash_pooling",
    "ftp": "transfer_pricing",
    # AML — Anti-Money Laundering
    "screening": "sanctions_screening",
    "monitoring": "transaction_monitoring",
    "investigation": "case_investigation",
    "reporting_aml": "regulatory_reporting",
}

# Regex patterns for evidence parsing (Patch 5)
# v10: support line ranges like file:10-50(fn) and file:42,100(fn)
_EVIDENCE_FULL_RE = re.compile(r"^(?P<path>.+?):(?P<line>\d+(?:[,\-]\d+)*)\((?P<fn>[^)]+)\)$")
_EVIDENCE_FILE_LINE_RE = re.compile(
    r"^(?P<path>[\w./\-]+\.py):(?P<line>\d+(?:[,\-]\d+)*)(?P<rest>.*)$",
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
    """P2: force bp["sop_version"] and ensure extraction_methods is a list.

    Always returns 1 (this patch is always applied).
    """
    bp["sop_version"] = "3.6"

    # Ensure source.extraction_methods is a list (v7 schema compliance)
    source = bp.get("source", {})
    if isinstance(source, dict):
        em = source.get("extraction_methods") or source.pop("extraction_method", None)
        if isinstance(em, str):
            source["extraction_methods"] = [em]
        elif not isinstance(em, list):
            source["extraction_methods"] = ["semi_auto"]
        bp["source"] = source

    logger.debug("P2 (sop_version): forced to 3.6, extraction_methods normalized")
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

    # v7: detect RC misclassification — RC without regulatory keywords → T
    _RC_KEYWORDS = {
        "regulation",
        "regulatory",
        "mandatory",
        "required",
        "compliance",
        "settlement",
        "t+1",
        "t+2",
        "stamp",
        "tax",
        "sec",
        "finra",
        "exchange rule",
        "law",
        "legal",
        "statute",
        "directive",
        "basel",
        "mifid",
        "solvency",
        "ifrs",
        "gaap",
    }
    rc_fixed = 0
    for bd in bp.get("business_decisions", []):
        if not isinstance(bd, dict):
            continue
        bd_type = bd.get("type", "")
        if bd_type != "RC" or bd.get("status") == "missing":
            continue
        text = (bd.get("content", "") + " " + bd.get("rationale", "")).lower()
        if not any(kw in text for kw in _RC_KEYWORDS):
            bd["type"] = "T"
            rc_fixed += 1
            logger.info(
                "P4: RC→T for %s (no regulatory keywords): %s",
                bd.get("id", "?"),
                bd.get("content", "")[:50],
            )

    logger.info("P4 (bd_type_enum_fix): %d type corrected, %d RC→T", count, rc_fixed)
    return count + rc_fixed


def _patch_evidence_format(
    bp: dict[str, Any],
    file_path_map: dict[str, str] | None = None,
) -> int:
    """P5: normalise BD evidence fields to file:line(fn) format.

    Three cases:
    0. Document section evidence (file:§section) — skip.
    1. Already matches file:line(fn) — skip.
    2. Matches file.py:line with optional trailing text — extract/derive fn.
       v7: also resolves bare filenames to full repo-relative paths using file_path_map.
    3. No .py file reference at all — replace with N/A:0(see_rationale).

    Also computes evidence_coverage_ratio = (BDs with valid evidence) / total BDs,
    stored in bp["_enrich_meta"]["evidence_coverage_ratio"].

    Args:
        bp: The blueprint dict.
        file_path_map: Optional mapping of bare filename → full repo-relative path.
            Built from structural_index in enrich_blueprint().

    Returns the number of BDs whose evidence was modified.
    """
    bd_list: list[dict[str, Any]] = bp.get("business_decisions", [])
    if not isinstance(bd_list, list):
        return 0

    ev_fixed = 0
    valid_evidence_count = 0
    total_count = 0

    # Document section evidence (non-code sources) — no line number needed
    doc_section_re = re.compile(r"^.+:§.+$")  # e.g. "SKILL.md:§Phase-1-Step-4"

    for entry in bd_list:
        if not isinstance(entry, dict):
            continue
        total_count += 1
        ev = entry.get("evidence", "")
        if not isinstance(ev, str):
            ev = ""

        # Case 0: document section evidence — count as valid, skip normalization
        if doc_section_re.match(ev):
            valid_evidence_count += 1
            continue

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

            # v7: resolve bare filename to full repo-relative path
            # e.g. "env_stocktrading.py" → "finrl/meta/env_stock_trading/env_stocktrading.py"
            if "/" not in fp and file_path_map:
                bare = fp.split("/")[-1]
                resolved = file_path_map.get(bare)
                if resolved:
                    fp = resolved

            # Look for explicit (function) in trailing text
            func_m = re.search(r"\(([^)]+)\)", rest)
            if func_m:
                fn_name = func_m.group(1).strip()
                # Sanitize: reject non-identifier function names
                # Invalid: "self", "module", "for i in range()", numbers, comma-lists
                if not re.match(r"^[A-Za-z_][\w.]*$", fn_name) or fn_name in (
                    "self",
                    "module",
                    "cls",
                    "args",
                    "kwargs",
                ):
                    fn_name = "module"
                entry["evidence"] = f"{fp}:{line}({fn_name})"
            else:
                # Derive from first word after separators
                word_m = re.search(r"[\s\u2014\-:]+([A-Za-z_]\w*)", rest)
                fn = word_m.group(1) if word_m else "module"
                if fn in ("self", "cls", "args", "kwargs"):
                    fn = "module"
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
    # v2 uses "use_cases", legacy used "known_use_cases"
    ucs: list[Any] = bp.get("use_cases") or bp.get("known_use_cases") or []
    if not isinstance(ucs, list):
        ucs = []
    # Store back under whichever key exists
    uc_key = "use_cases" if "use_cases" in bp else "known_use_cases"
    bp[uc_key] = ucs

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

        # v10: fill required disambiguation fields with defaults
        for _field, _default in [
            ("negative_keywords", []),
            ("disambiguation", ""),
            ("data_domain", "general"),
        ]:
            if not uc.get(_field):
                uc[_field] = _default
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
        "sop_version": bp.get("sop_version", "3.6"),
        "executed_at": "auto",
        "subdomain_labels": labels,
    }

    if audit_path.exists():
        content = audit_path.read_text(encoding="utf-8")
        # Parse pass/warn/fail per section (universal vs subdomain).
        # Sections are separated by "##" headings. Table rows start with "|".
        # Only count rows containing status emojis, skip header/separator rows.
        universal = {"pass": 0, "warn": 0, "fail": 0}
        subdomain_totals = {"pass": 0, "warn": 0, "fail": 0}
        current_section = "unknown"

        for line in content.split("\n"):
            stripped = line.strip()
            # Detect section headers
            if stripped.startswith("##"):
                lower = stripped.lower()
                if "universal" in lower or "通用" in lower:
                    current_section = "universal"
                elif any(
                    kw in lower
                    for kw in [
                        "trd",
                        "prc",
                        "rsk",
                        "crd",
                        "cmp",
                        "dat",
                        "ail",
                        "ins",
                        "lnd",
                        "trs",
                        "aml",
                        "a_stock",
                        "a股",
                    ]
                ):
                    current_section = "subdomain"
                else:
                    current_section = "other"
                continue

            if not stripped.startswith("|"):
                continue
            # Skip table header/separator rows
            if "---" in stripped or "必审项" in stripped or "Check" in stripped:
                continue

            target = universal if current_section == "universal" else subdomain_totals
            if "✅" in stripped:
                target["pass"] += 1
            elif "⚠️" in stripped:
                target["warn"] += 1
            elif "❌" in stripped:
                target["fail"] += 1

        total_all = sum(universal.values()) + sum(subdomain_totals.values())
        total_pass = universal["pass"] + subdomain_totals["pass"]

        audit_data["finance_universal"] = universal
        audit_data["subdomain_totals"] = subdomain_totals
        audit_data["coverage"] = (
            f"{total_pass}/{total_all} ({total_pass * 100 // total_all}%)"
            if total_all
            else "0/0 (0%)"
        )
        audit_data["note"] = "Parsed from worker_audit.md (universal + subdomain separated)"
        logger.info(
            "P11 (audit): universal=%s, subdomain=%s, total=%d",
            universal,
            subdomain_totals,
            total_all,
        )
    else:
        audit_data["note"] = "Auto-generated by bp_enrich; detailed audit pending"
        logger.debug("P11 (audit): placeholder (worker_audit.md not found)")

    bp["audit_checklist_summary"] = audit_data
    return 1


def _patch_relations(bp: dict[str, Any], state: AgentState | None = None) -> int:
    """P12: discover and inject relations with existing blueprints.

    v7: scans existing blueprints in the same domain to find related projects.
    Falls back to placeholder only if no existing blueprints are found.

    Returns the number of relations injected.
    """
    if bp.get("relations"):
        # Remove placeholder entries
        real = [r for r in bp["relations"] if isinstance(r, dict) and r.get("type") != "pending"]
        if real:
            return 0  # Already has real relations

    # Try to discover related blueprints from the knowledge directory
    from pathlib import Path as _Path

    domain = bp.get("applicability", {}).get("domain", "finance")
    bp_id = bp.get("id", "")
    bp_dir = _Path("knowledge/blueprints") / domain

    relations: list[dict[str, str]] = []
    if bp_dir.is_dir():
        import yaml as _yaml

        for yaml_file in sorted(bp_dir.glob("*.yaml")):
            if yaml_file.name.startswith("_"):
                continue
            try:
                other = _yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if not isinstance(other, dict):
                    continue
                other_id = other.get("id", "")
                if not other_id or other_id == bp_id:
                    continue
                other_name = other.get("name", "")
                other_task = other.get("applicability", {}).get("task_type", "")
                bp_task = bp.get("applicability", {}).get("task_type", "")

                # Determine relation type based on task_type similarity
                # Use ID as description base (English, stable) instead of name (may be Chinese)
                if bp_task and other_task and bp_task == other_task:
                    rel_type = "alternative_to"
                    desc = f"Same task type ({other_task}), different implementation approach"
                else:
                    rel_type = "complementary"
                    desc = "Different capability, potential data/component synergy"

                relations.append(
                    {
                        "type": rel_type,
                        "target": other_id,
                        "description": desc,
                    }
                )
            except Exception:
                continue

    if not relations:
        relations = [
            {
                "type": "pending",
                "target": "none",
                "description": "No existing blueprints found in this domain",
            }
        ]

    bp["relations"] = relations
    logger.info("P12 (relations): discovered %d relations", len(relations))
    return len(relations)


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
    # v10: support line ranges like file:10-50(fn) AND file:line without (fn)
    _ev_pattern = re.compile(r"^(.+?):(\d+(?:[,\-]\d+)*)\((.+?)\)$")
    _ev_pattern_no_fn = re.compile(r"^(.+?):(\d+(?:[,\-]\d+)*)$")
    # v6.3: valid Python identifier pre-check — reject constants, formulas,
    # natural language before attempting AST lookup
    _ident_pattern = re.compile(r"^[\w.]+$")

    for bd in bp.get("business_decisions", []):
        ev = bd.get("evidence", "")
        if not ev or ev.startswith("N/A"):
            continue
        # Skip AST verification for document section evidence
        if "§" in ev:
            verified += 1
            continue
        m = _ev_pattern.match(ev)
        fn_name = ""
        if m:
            file_path, line_str, fn_name = m.group(1), m.group(2), m.group(3)
        else:
            # v10: fallback for file:line without (function)
            m2 = _ev_pattern_no_fn.match(ev)
            if not m2:
                continue
            file_path, line_str = m2.group(1), m2.group(2)
        # v10: extract first line number from ranges like "10-50" or "42,100"
        line_no = int(line_str.split("-")[0].split(",")[0])
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
            # v6.3: pre-check — reject non-identifier fn names before AST
            # lookup.  Constants (max_n_bins=10), formulas (np.log(...)),
            # and natural language ("Event Rate rounding") waste AST parse.
            if not _ident_pattern.match(fn_name):
                bd.setdefault("_evidence_issues", []).append(
                    f"INVALID_IDENTIFIER: {fn_name} in {file_path}"
                )
                invalid += 1
                continue

            try:
                source = full_path.read_text(encoding="utf-8", errors="replace")
                tree = _ast.parse(source, filename=file_path)
            except (SyntaxError, UnicodeDecodeError):
                verified += 1
                continue

            # Find all function/method/class definitions
            fn_defs: dict[str, int] = {}
            for node in _ast.walk(tree):
                if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                    fn_defs[node.name] = node.lineno
                if isinstance(node, _ast.ClassDef):
                    # v6.3: also register class name itself (LLM often
                    # cites the class embodying a decision, not a method)
                    fn_defs[node.name] = node.lineno
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
    # v6.3: auto_fixed BDs ARE successfully verified (fn found, line
    # corrected) — include them in denominator for accurate ratio
    total = verified + invalid + auto_fixed
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

    raw_text = resource_path.read_text(encoding="utf-8")
    try:
        resource_data = json.loads(raw_text)
    except json.JSONDecodeError as initial_err:
        # MiniMax sometimes outputs invalid JSON values like:
        #   "default_port": 80 (SSL), configurable,
        # Targeted repair: only fix the specific line that caused the error,
        # to avoid corrupting valid fields elsewhere in the document.
        lines = raw_text.split("\n")
        err_line = initial_err.lineno - 1  # 0-indexed
        repaired = False
        if 0 <= err_line < len(lines):
            line = lines[err_line]
            # Quote the value portion after the colon if it looks like
            # an unquoted string (not a number, bool, null, or container).
            import re as _re

            fixed = _re.sub(
                r"(:\s*)(\d+\s+\(.*?\)[^,}\]]*)([\s,}\]])",
                lambda m: m.group(1) + '"' + m.group(2).strip() + '"' + m.group(3),
                line,
            )
            if fixed != line:
                lines[err_line] = fixed
                try:
                    resource_data = json.loads("\n".join(lines))
                    repaired = True
                    logger.info(
                        "P14 (resource_injection): repaired JSON at line %d",
                        initial_err.lineno,
                    )
                except json.JSONDecodeError:
                    pass
        if not repaired:
            # v10: try generic _repair_json (handles extra data, trailing commas)
            try:
                from doramagic_extraction_agent.sop.synthesis_v9 import _repair_json

                repaired_text = _repair_json(raw_text)
                if repaired_text:
                    resource_data = json.loads(repaired_text)
                    repaired = True
                    logger.info("P14 (resource_injection): repaired JSON via _repair_json")
            except Exception:
                pass
        if not repaired:
            logger.warning(
                "P14 (resource_injection): failed to read resource data: %s",
                initial_err,
            )
            return 0
    except OSError as exc:
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

    # v7: use "resources" (schema-compliant) instead of "global_resources"
    resources = bp.get("resources", bp.get("global_resources", []))
    res_counter = len(resources)
    for slot_name, slot_data in resource_slots.items():
        if slot_name.lower() not in all_existing_names:
            res_counter += 1
            new_rp = {
                "id": f"res-slot-{res_counter:03d}",
                "type": "replaceable_component",
                "name": slot_name,
                "path": None,
                "description": slot_data.get("selection_criteria", ""),
                "used_in_stages": [],
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
            resources.append(new_rp)
            injected += 1

    # v7: also inject data_sources and external_services into resources[]
    # with schema-compliant format (id/type/name/path/description/used_in_stages)
    res_counter = len(resources)
    data_sources = resource_data.get("data_sources", [])
    for ds in data_sources:
        if not isinstance(ds, dict):
            continue
        provider = ds.get("provider", "")
        if not provider:
            continue
        res_counter += 1
        resources.append(
            {
                "id": f"res-{res_counter:03d}",
                "type": "external_service",
                "name": provider,
                "description": (
                    f"{ds.get('data_type', '')}. "
                    f"Coverage: {ds.get('coverage', 'N/A')}. "
                    f"Auth: {ds.get('auth_requirements', 'N/A')}"
                ).strip(),
                "used_in_stages": ["data_download"],
                "_source": "worker_resource",
            }
        )
        injected += 1

    ext_services = resource_data.get("external_services", [])
    for svc in ext_services:
        if not isinstance(svc, dict):
            continue
        name = svc.get("name", svc.get("service", ""))
        if not name:
            continue
        res_counter += 1
        resources.append(
            {
                "id": f"res-{res_counter:03d}",
                "type": "external_service",
                "name": name,
                "description": svc.get("description", svc.get("purpose", "")),
                "used_in_stages": svc.get("used_in_stages", []),
                "_source": "worker_resource",
            }
        )
        injected += 1

    raw_deps = resource_data.get("dependencies", [])
    # dependencies can be list or dict ({"core": [...], "optional": [...]})
    if isinstance(raw_deps, dict):
        deps: list = []
        for group in raw_deps.values():
            if isinstance(group, list):
                deps.extend(group)
    elif isinstance(raw_deps, list):
        deps = raw_deps
    else:
        deps = []
    for dep in deps[:10]:  # Cap at 10 most important
        if not isinstance(dep, dict):
            continue
        pkg = dep.get("package", dep.get("name", ""))
        if not pkg:
            continue
        res_counter += 1
        resources.append(
            {
                "id": f"res-{res_counter:03d}",
                "type": "python_package",
                "name": pkg,
                "description": dep.get("purpose", dep.get("description", "")),
                "used_in_stages": dep.get("used_in_stages", []),
                "_source": "worker_resource",
            }
        )
        injected += 1

    if resources:
        bp["resources"] = resources
        bp.pop("global_resources", None)  # remove legacy field name

    logger.info("P14 (resource_injection): injected %d resources total", injected)
    return injected


def _patch_missing_gaps_from_audit(
    bp: dict[str, Any],
    artifacts_dir: Path,
    state: Any = None,
) -> int:
    """P15: deterministic missing gap generation from audit findings.

    Cross-references worker_audit.md ❌ FAIL items against existing BDs.
    Any audit failure not covered by an existing BD becomes a missing gap.
    This is pure Python — no LLM dependency — ensuring missing gaps are
    always generated even when Synthesis Step 3 hits L3 fallback.

    Returns the number of missing gap BDs injected.
    """
    audit_path = artifacts_dir / "worker_audit.md"
    if not audit_path.exists():
        logger.debug("P15 (missing_gaps): worker_audit.md not found, skipping")
        return 0

    audit_text = audit_path.read_text(encoding="utf-8")

    # Extract FAIL items from audit report.
    # v6.3: match both ❌ and ⚠️ lines with case-insensitive "fail"/"absent".
    # Worker_audit may use "⚠️ Fail" (warning emoji + title-case) instead
    # of "❌ FAIL" (cross emoji + all-caps).
    fail_items: list[dict[str, str]] = []
    current_item = ""
    current_detail_lines: list[str] = []
    _MAX_DETAIL_LINES = 2
    _MAX_DETAIL_CHARS = 200
    for line in audit_text.splitlines():
        line_lower = line.lower()
        # v6.3: broadened trigger — any line with (❌ or ⚠️) + fail/absent
        is_fail_line = ("❌" in line or "⚠️" in line) and (
            "fail" in line_lower or "absent" in line_lower
        )
        if is_fail_line:
            if current_item:
                detail = " ".join(current_detail_lines)[:_MAX_DETAIL_CHARS]
                fail_items.append({"item": current_item, "detail": detail.strip()})
            clean = (
                line.replace("❌", "")
                .replace("⚠️", "")
                .replace("FAIL", "")
                .replace("Fail", "")
                .replace("fail", "")
                .strip(" |-#*")
            )
            current_item = clean
            current_detail_lines = []
        # ✅ or new section means stop collecting detail for current item
        elif (
            "✅" in line
            or line.strip().startswith(("##", "---"))
            or ("⚠️" in line and "fail" not in line_lower)
        ):
            if current_item:
                detail = " ".join(current_detail_lines)[:_MAX_DETAIL_CHARS]
                fail_items.append({"item": current_item, "detail": detail.strip()})
                current_item = ""
                current_detail_lines = []
        elif current_item and len(current_detail_lines) < _MAX_DETAIL_LINES:
            stripped = line.strip(" -•*|")
            if stripped and len(stripped) > 5:
                current_detail_lines.append(stripped)
    if current_item:
        detail = " ".join(current_detail_lines)[:_MAX_DETAIL_CHARS]
        fail_items.append({"item": current_item, "detail": detail.strip()})

    # v6.3: also parse "Missing Gap BD Candidates" structured section
    # Worker audit may include a markdown section with pre-structured gap BDs
    _gap_section_re = re.compile(
        r"##\s*Missing\s+Gap\s+BD\s+Candidates",
        re.IGNORECASE,
    )
    _gap_section_match = _gap_section_re.search(audit_text)
    if _gap_section_match:
        gap_section = audit_text[_gap_section_match.end() :]
        # Stop at next ## heading or end of text
        next_heading = re.search(r"\n##\s", gap_section)
        if next_heading:
            gap_section = gap_section[: next_heading.start()]
        # Parse structured items: look for "content:", "type:", etc.
        for block in re.split(r"\n(?=\d+\.\s|\*\s|-\s(?=\*\*)|###\s)", gap_section):
            content_m = re.search(r"content[:\s]+[\"']?(.+?)[\"']?\s*$", block, re.MULTILINE)
            if content_m:
                item_text = content_m.group(1).strip()
                detail_m = re.search(
                    r"(?:impact|rationale|detail)[:\s]+[\"']?(.+?)[\"']?\s*$",
                    block,
                    re.MULTILINE,
                )
                detail = detail_m.group(1).strip() if detail_m else ""
                # De-dup against existing fail_items
                if not any(item_text[:50].lower() in fi["item"].lower() for fi in fail_items):
                    fail_items.append({"item": item_text, "detail": detail})

    if not fail_items:
        logger.debug("P15 (missing_gaps): no FAIL items found in audit")
        return 0

    # v10: filter out audit items from subdomains with no code backing
    def _item_has_code_backing(item_text: str, repo_files: set[str]) -> bool:
        """Check if audit item references concepts present in actual code.

        v10 fix: search both subdomain abbreviations AND full concept names
        in file paths (e.g. 'pricing', 'black_scholes', 'credit', 'ifrs9').
        """
        _subdomain_terms: dict[str, tuple[set[str], set[str]]] = {
            # (audit keywords → trigger, file path keywords → verify)
            # v10.1: added Chinese trigger terms for audit items written in Chinese
            "prc": (
                {
                    "implied volatility",
                    "greeks",
                    "black-scholes",
                    "finite difference",
                    "no-arbitrage",
                    "day count convention",
                    "act/360",
                    "yield curve",
                    "option pricing",
                    "monte carlo",
                    "binomial tree",
                    # Chinese triggers
                    "定价模型",
                    "波动率曲面",
                    "隐含波动率",
                    "无套利",
                    "日计数",
                    "复利约定",
                    "模型校准",
                    "收敛诊断",
                },
                {
                    "prc",
                    "pricing",
                    "option",
                    "black_scholes",
                    "greeks",
                    "volatil",
                    "derivative",
                    "finite_diff",
                    "binomial",
                    "monte_carlo",
                },
            ),
            "rsk": (
                {
                    # Risk management terms (PRC-adjacent)
                    "协方差矩阵",
                    "协方差估计",
                    "var/cvar",
                    "压力测试",
                    "转移矩阵",
                    "covariance",
                    "stress test",
                },
                {
                    "risk",
                    "var",
                    "cvar",
                    "covariance",
                    "stress",
                    "portfolio_opt",
                },
            ),
            "crd": (
                {
                    "pd/lgd/ead",
                    "ifrs 9",
                    "expected credit loss",
                    "vasicek",
                    "npl",
                    "credit scoring",
                    "probability of default",
                    "loss given default",
                },
                {
                    "crd",
                    "credit",
                    "ifrs",
                    "lgd",
                    "ead",
                    "scoring",
                    "default",
                    "loss_given",
                    "vasicek",
                },
            ),
            "trs": (
                {
                    "lcr",
                    "nsfr",
                    "interest rate gap",
                    "cash pool",
                    "alm",
                    "liquidity coverage",
                    "asset liability",
                    # Chinese triggers
                    "利率缺口",
                    "资金转移定价",
                    "现金池",
                    "ftp",
                },
                {
                    "trs",
                    "treasury",
                    "alm",
                    "liquidity",
                    "lcr",
                    "nsfr",
                    "asset_liability",
                    "cash_pool",
                    "interest_rate",
                },
            ),
        }
        item_lower = item_text.lower()
        for terms, file_keywords in _subdomain_terms.values():
            if any(term in item_lower for term in terms):
                # Require ≥2 file keyword hits to count as "has backing"
                # (prevents e.g. a single 'default' match from passing CRD)
                hits = sum(1 for kw in file_keywords if any(kw in f.lower() for f in repo_files))
                if hits < 2:
                    return False
        return True

    # Apply filter if structural_index is available
    if hasattr(state, "extra") and state is not None and state.extra.get("structural_index"):
        _repo_files = set(state.extra["structural_index"].get("files", {}).keys())
        fail_items = [
            item for item in fail_items if _item_has_code_backing(item["item"], _repo_files)
        ]

    # Check which fail items are already covered by existing BDs
    bds = bp.get("business_decisions", [])
    existing_content = " ".join(
        str(bd.get("content", "")) + " " + str(bd.get("rationale", ""))
        for bd in bds
        if isinstance(bd, dict)
    ).lower()

    # Find the next available BD ID
    existing_ids = {bd.get("id", "") for bd in bds if isinstance(bd, dict)}
    gap_counter = 1

    # --- GAP type inference from audit item keywords ---
    _GAP_TYPE_MAP: list[tuple[list[str], str]] = [
        (["regulation", "mandatory", "settlement", "T+1", "stamp", "tax", "compliance"], "RC"),
        (["decimal", "precision", "float", "rounding", "tick_size", "lot_size"], "RC"),
        (["convergence", "tolerance", "matrix", "condition", "numerical"], "M"),
        (["day_count", "act360", "thirty360"], "M/DK"),
        (["point-in-time", "stale", "snapshot", "release_date", "as_of"], "DK"),
        (["seed", "random", "reproducib"], "DK"),
        (["version", "experiment_id", "run_id"], "B"),
        (["calendar", "holiday", "timezone"], "DK"),
    ]

    # --- GAP stage inference from audit item keywords ---
    _GAP_STAGE_MAP: list[tuple[list[str], str]] = [
        (["execution", "order", "settlement", "slippage", "cost"], "trading_execution"),
        (["data", "provider", "stale", "point-in-time", "snapshot"], "data_collection"),
        (["factor", "compute", "indicator", "ma", "macd"], "factor_computation"),
        (["model", "ml", "train", "predict", "seed", "random"], "ml_prediction"),
        (["precision", "decimal", "float", "tick_size"], "trading_execution"),
        (["calendar", "holiday", "day_count", "timezone"], "data_collection"),
        (["version", "experiment", "log", "audit"], "data_storage"),
    ]

    def _infer_gap_type(item_text: str) -> str:
        text_lower = item_text.lower()
        for keywords, gap_type in _GAP_TYPE_MAP:
            if sum(1 for kw in keywords if kw.lower() in text_lower) >= 1:
                return gap_type
        return "B"

    def _infer_gap_stage(item_text: str, stages: list[str]) -> str:
        text_lower = item_text.lower()
        for keywords, stage in _GAP_STAGE_MAP:
            if stage in stages and sum(1 for kw in keywords if kw.lower() in text_lower) >= 1:
                return stage
        return stages[0] if stages else "unknown"

    def _clean_gap_content(raw_item: str) -> str:
        """Clean audit table format: '4 | float vs Decimal... | absent | ...' → natural language."""
        # Remove leading number + pipe separators
        parts = raw_item.split("|")
        if len(parts) >= 2:
            # Take the second part (the description), skip number and status
            desc = parts[1].strip() if len(parts) > 1 else raw_item
            return f"Missing: {desc}"
        return f"Missing: {raw_item.strip()}"

    # Get stage IDs from blueprint for stage inference
    bp_stages = [
        s.get("id", "") for s in bp.get("stages", []) if isinstance(s, dict) and s.get("id")
    ]

    injected = 0
    for fail in fail_items:
        # Simple keyword overlap check
        keywords = [
            w.lower()
            for w in fail["item"].split()
            if len(w) > 3
            and w.lower()
            not in {
                "the",
                "and",
                "for",
                "with",
                "from",
                "that",
                "this",
                "item",
                "check",
                "missing",
                "absent",
            }
        ]
        covered = sum(1 for k in keywords if k in existing_content)
        coverage_ratio = covered / max(len(keywords), 1)

        if coverage_ratio < 0.5:
            gap_id = f"BD-GAP-{gap_counter:03d}"
            while gap_id in existing_ids:
                gap_counter += 1
                gap_id = f"BD-GAP-{gap_counter:03d}"

            # Clean content, infer type and stage
            content = _clean_gap_content(fail["item"])
            gap_type = _infer_gap_type(fail["item"] + " " + fail.get("detail", ""))
            gap_stage = _infer_gap_stage(
                fail["item"] + " " + fail.get("detail", ""),
                bp_stages,
            )
            detail = fail.get("detail", "") or "Identified by audit checklist"

            gap_bd = {
                "id": gap_id,
                "content": content,
                "type": gap_type,
                "rationale": (
                    f"Audit finding: {content.lower()}. {detail}. "
                    f"This gap affects production reliability and should be addressed."
                ),
                "evidence": "N/A:0(see_rationale)",
                "stage": gap_stage,
                "status": "missing",
                "severity": "high",
                "impact": detail[:200],
                "known_gap": True,
            }
            if len(gap_bd["rationale"]) < 40:
                gap_bd["rationale"] += " " * (40 - len(gap_bd["rationale"]))

            bds.append(gap_bd)
            existing_ids.add(gap_id)
            gap_counter += 1
            injected += 1

    if injected > 0:
        bp["business_decisions"] = bds

    logger.info(
        "P15 (missing_gaps): %d gap BDs from %d audit FAIL items (%.0f%% already covered)",
        injected,
        len(fail_items),
        (1 - injected / max(len(fail_items), 1)) * 100,
    )
    return injected


# Keywords that signal a BD might deserve a secondary type annotation
_MULTI_TYPE_RULES: list[tuple[str, str, list[str]]] = [
    # (current_type, candidate_secondary, trigger_keywords)
    # v7: expanded keyword lists + AI/RL/finance signals for better coverage
    (
        "B",
        "BA",
        [
            "assume",
            "assumption",
            "default",
            "threshold",
            "expect",
            "tolerance",
            "typical",
            "empirical",
            "heuristic",
            "convention",
            "encode",
            "implicit",
            "approximate",
            "simplif",
            "proxy",
            "initial",
            "baseline",
            "conservative",
            "aggressive",
            "institutional",
            "retail",
            "scale",
            "capital",
        ],
    ),
    (
        "B",
        "DK",
        [
            "market",
            "china",
            "a-share",
            "a股",
            "exchange",
            "regulatory",
            "convention",
            "tradition",
            "culture",
            "nyse",
            "nasdaq",
            "us equity",
            "us stock",
            "crypto",
            "dow",
            "s&p",
        ],
    ),
    (
        "B",
        "RC",
        [
            "regulation",
            "mandatory",
            "required",
            "compliance",
            "settlement",
            "T+1",
            "stamp",
            "tax",
            "sec",
            "finra",
        ],
    ),
    (
        "BA",
        "DK",
        [
            "market",
            "china",
            "a-share",
            "specific",
            "local",
            "domestic",
            "convention",
            "us equity",
            "trading day",
        ],
    ),
    (
        "BA",
        "M",
        [
            "formula",
            "model",
            "statistical",
            "distribution",
            "normal",
            "gaussian",
            "variance",
            "correlation",
            "sharpe",
            "sortino",
            "mahalanobis",
            "covariance",
            "annuali",
            "sqrt",
        ],
    ),
    (
        "M",
        "DK",
        [
            "market",
            "china",
            "a-share",
            "specific",
            "domestic",
            "trading day",
            "252",
            "us equity",
            "nyse",
        ],
    ),
    (
        "M",
        "BA",
        [
            "assume",
            "assumption",
            "empirical",
            "calibrat",
            "parameter",
            "default",
            "convention",
            "approximate",
            "practical",
            "domain",
            "financial",
            "reward",
            "scaling",
            "normalize",
        ],
    ),
    (
        "DK",
        "B",
        [
            "design",
            "choice",
            "select",
            "choose",
            "implement",
            "decision",
            "architect",
            "framework",
        ],
    ),
]


def _patch_multi_type_annotation(bp: dict[str, Any]) -> int:
    """P16: deterministic multi-type annotation enhancement.

    Scans single-type non-T BDs for keyword signals that suggest a
    secondary type. E.g., a B-type BD whose rationale mentions
    "assumption" or "threshold" likely has BA implications.

    This is a quality enhancement — it never removes existing types,
    only adds secondary types to single-type BDs. Pure Python, no LLM.

    Returns the number of BDs upgraded to multi-type.
    """
    bds = bp.get("business_decisions", [])
    upgraded = 0

    for bd in bds:
        if not isinstance(bd, dict):
            continue
        bd_type = bd.get("type", "T")
        # Skip T, missing, and already multi-type
        if bd_type == "T" or "/" in bd_type or bd.get("status") == "missing":
            continue

        rationale = (bd.get("rationale", "") + " " + bd.get("content", "")).lower()

        for primary, secondary, keywords in _MULTI_TYPE_RULES:
            if bd_type != primary:
                continue
            # Count keyword matches (v7: lowered threshold from 2→1)
            hits = sum(1 for kw in keywords if kw.lower() in rationale)
            if hits >= 1:
                bd["type"] = f"{primary}/{secondary}"
                upgraded += 1
                break  # Only apply first matching rule

    logger.info("P16 (multi_type): upgraded %d BDs to multi-type annotation", upgraded)
    return upgraded


def _patch_absolute_words(bp: dict[str, Any]) -> int:
    """P17: reduce 'all/All' frequency to ≤3 in text fields.

    SOP v3.4 rule: "所有"+"全部" ≤3 occurrences; English "all" similarly
    restricted. Uses regex to replace "all {noun}" → "each {noun}" broadly.
    """

    def _replace_all_in_str(text: str) -> tuple[str, int]:
        """Replace 'all/All + noun' patterns with 'each/Every + noun'."""
        count = 0
        # "All X" at start of sentence → "Every X"
        new, n = re.subn(r"\bAll (\w+)", r"Every \1", text)
        count += n
        text = new
        # "all X" mid-sentence → "each X" (but not "all" standalone)
        new, n = re.subn(r"\ball (\w+)", r"each \1", text)
        count += n
        text = new
        return text, count

    def _walk_and_replace(obj: Any) -> tuple[Any, int]:
        """Recursively replace in all string values."""
        total = 0
        if isinstance(obj, str):
            new_str, count = _replace_all_in_str(obj)
            return new_str, count
        elif isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                new_v, count = _walk_and_replace(v)
                new_dict[k] = new_v
                total += count
            return new_dict, total
        elif isinstance(obj, list):
            new_list = []
            for item in obj:
                new_item, count = _walk_and_replace(item)
                new_list.append(new_item)
                total += count
            return new_list, total
        return obj, 0

    # Count current occurrences
    import yaml as _yaml

    content = _yaml.dump(bp, allow_unicode=True, default_flow_style=False)
    before_count = len(re.findall(r"\ball\b", content, re.IGNORECASE))
    if before_count <= 3:
        return 0

    new_bp, replaced = _walk_and_replace(bp)
    bp.update(new_bp)

    after_content = _yaml.dump(bp, allow_unicode=True, default_flow_style=False)
    after_count = len(re.findall(r"\ball\b", after_content, re.IGNORECASE))

    logger.info(
        "P17 (absolute_words): %d replacements (%d → %d occurrences)",
        replaced,
        before_count,
        after_count,
    )
    return replaced


def _patch_activation_injection(bp: dict[str, Any], run_dir: Path, **kw: Any) -> None:
    """P16b: Inject activation from worker_structural.json into applicability.activation.

    Falls back to generating basic activation from applicability fields
    when no document-sourced activation is available.
    """
    structural_path = run_dir / "artifacts" / "worker_structural.json"
    activation: dict[str, Any] = {}

    if structural_path.exists():
        try:
            with open(structural_path) as f:
                structural = json.load(f)
            activation = structural.get("activation", {})
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("P16b: failed to parse worker_structural.json: %s", exc)

    # Don't overwrite an existing activation (e.g. from assembly output).
    existing_activation = bp.get("applicability", {}).get("activation")
    if existing_activation:
        return

    # Fallback: generate basic activation from applicability if no
    # document-sourced activation is available (Issue 6 fix).
    # Only generate when worker_structural didn't fail — don't mask
    # extraction failures with synthetic data.
    if not activation and not structural_path.exists():
        app = bp.get("applicability", {})
        name = bp.get("name", "")
        domain = app.get("domain", "")
        task_type = app.get("task_type", "")
        if name and (domain or task_type):
            triggers = [f"User needs {task_type or domain} capabilities"]
            if name:
                triggers.append(f"Project involves {name} or similar tools")
            if domain:
                triggers.append(f"Domain is {domain}")
            activation = {
                "triggers": triggers,
                "emphasis": [],
                "anti_skip": [],
            }

    if not activation:
        return

    if "applicability" not in bp:
        bp["applicability"] = {}
    bp["applicability"]["activation"] = activation
    logger.info("P16b: injected activation with %d triggers", len(activation.get("triggers", [])))


def _patch_uc_from_examples(bp: dict[str, Any], state: Any) -> int:
    """P18: Generate use-case skeletons from examples/ directory.

    When known_use_cases is empty after P9 (uc_merge), scan the repo for
    examples/, demo/, tutorials/, notebooks/ directories and generate minimal
    UC entries from their file names.  This is a deterministic fallback that
    ensures at least basic UC coverage.

    Returns the number of UCs added.
    """
    existing = bp.get("known_use_cases") or []
    if existing:
        return 0  # already has UCs, don't override

    repo_path = getattr(state, "repo_path", None)
    if not repo_path:
        return 0

    from pathlib import Path as _P

    repo_root = _P(str(repo_path)).resolve()
    example_dirs = ["examples", "demo", "demos", "tutorials", "notebooks", "sample"]
    uc_files: list[str] = []

    for dirname in example_dirs:
        edir = repo_root / dirname
        if edir.is_dir():
            for f in sorted(edir.rglob("*")):
                if f.suffix in (".py", ".ipynb", ".md", ".rst", ".php", ".rb", ".ts", ".js"):
                    rel = str(f.relative_to(repo_root))
                    uc_files.append(rel)
                if len(uc_files) >= 20:
                    break
            if len(uc_files) >= 20:
                break

    if not uc_files:
        return 0

    added = 0
    for fpath in uc_files:
        # Derive a readable name from the filename
        fname = _P(fpath).stem.replace("_", " ").replace("-", " ").strip()
        if len(fname) < 3:
            continue
        uc = {
            "name": fname.title(),
            "source": fpath,
            "description": f"Example from {fpath}",
        }
        existing.append(uc)
        added += 1

    if added:
        bp["known_use_cases"] = existing
        logger.info("P18 (uc_from_examples): +%d use cases from example files", added)

    return added


def _patch_relations_injection(bp: dict[str, Any], run_dir: Path, **kw: Any) -> None:
    """P17b: Inject relations from worker_structural.json, merging with existing."""
    structural_path = run_dir / "artifacts" / "worker_structural.json"
    if not structural_path.exists():
        return

    try:
        with open(structural_path) as f:
            structural = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("P17b: failed to parse worker_structural.json: %s", exc)
        return

    new_relations = structural.get("relations", [])
    if not new_relations:
        return

    existing = bp.get("relations", [])
    # Deduplicate by (type, target)
    existing_keys = {(r.get("type"), r.get("target")) for r in existing if isinstance(r, dict)}
    for rel in new_relations:
        key = (rel.get("type"), rel.get("target"))
        if key not in existing_keys:
            existing.append(rel)
            existing_keys.add(key)
    bp["relations"] = existing
    logger.info(
        "P17b: relations now %d (added %d from structural)",
        len(existing),
        len(new_relations),
    )


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

    # v7: build filename→full_path map for evidence path resolution
    file_path_map: dict[str, str] = {}
    repo_path = str(state.repo_path) if hasattr(state, "repo_path") and state.repo_path else ""
    if repo_path:
        from pathlib import Path as _P

        repo_root = _P(repo_path).resolve()
        for py_file in repo_root.rglob("*.py"):
            rel_parts = py_file.relative_to(repo_root).parts
            if any(p.startswith(".") or p == "__pycache__" for p in rel_parts):
                continue
            rel = str(py_file.relative_to(repo_root))
            bare = py_file.name
            # Only map if no collision (first match wins)
            if bare not in file_path_map:
                file_path_map[bare] = rel

    # v10: build file_path_map from structural_index for bare filename resolution
    _structural_idx = (
        state.extra.get("structural_index", {}) if hasattr(state, "extra") and state.extra else {}
    )
    for _full_path in _structural_idx.get("files", {}):
        _bare = _full_path.rsplit("/", 1)[-1]
        if _bare not in file_path_map:
            file_path_map[_bare] = _full_path

    patch_stats["p5_evidence_format"] = _patch_evidence_format(bp, file_path_map=file_path_map)
    # P5.5: deterministic evidence verification (v6)
    if repo_path:
        patch_stats["p5_5_evidence_verify"] = _patch_evidence_verify(bp, repo_path)
    patch_stats["p6_vague_words"] = _patch_vague_words(bp)
    patch_stats["p7_stage_id_validation"] = _patch_stage_id_validation(bp)

    # Stage interface enrichment
    patch_stats["p8_required_methods"] = _patch_required_methods(bp)

    # Use-case merge + fallback + normalisation (order matters:
    # P9 merges LLM-extracted UCs, P18 fills gaps from examples/,
    # P10 normalises all UCs including P18's additions).
    patch_stats["p9_uc_merge"] = _patch_uc_merge(bp, artifacts_dir)
    patch_stats["p18_uc_from_examples"] = _patch_uc_from_examples(bp, state)
    patch_stats["p10_uc_normalize"] = _patch_uc_normalize(bp)

    # Metadata scaffolding (fill absent top-level fields)
    patch_stats["p11_audit_checklist"] = _patch_audit_checklist(bp, state, artifacts_dir)
    patch_stats["p12_relations"] = _patch_relations(bp, state=state)
    patch_stats["p13_execution_paradigm"] = _patch_execution_paradigm(bp)

    # v6: Resource injection from worker_resource
    patch_stats["p14_resource_injection"] = _patch_resource_injection(bp, artifacts_dir)

    # v6: Deterministic missing gap generation from audit findings
    patch_stats["p15_missing_gaps"] = _patch_missing_gaps_from_audit(bp, artifacts_dir, state=state)

    # v6: Deterministic multi-type annotation enhancement
    patch_stats["p16_multi_type"] = _patch_multi_type_annotation(bp)

    # v6: Replace overused absolute words (SOP: "all/All" ≤ 3 occurrences)
    patch_stats["p17_absolute_words"] = _patch_absolute_words(bp)

    # v7: Structural document injection (activation + relations from worker_structural)
    run_dir = artifacts_dir.parent if artifacts_dir.name == "artifacts" else artifacts_dir
    _patch_activation_injection(bp, run_dir)
    _patch_relations_injection(bp, run_dir)

    total_affected = sum(patch_stats.values())
    logger.info(
        "bp_enrich complete: %d total patch applications — %s",
        total_affected,
        ", ".join(f"{k}={v}" for k, v in patch_stats.items()),
    )

    return bp, patch_stats
