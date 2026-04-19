"""Constraint enrichment — SOP v2.2 con_enrich phase (deterministic post-processing).

P7 pattern: zero LLM calls.  All 8 patches are pure Python transformations
applied in sequence to the raw constraint list produced by the agentic
extraction phases.

Patch summary
-------------
1. evidence_refs     — parse file:line / file:line(fn) from evidence_summary
2. resource_boundary — auto-fill stage_ids from manifest replaceable_points
3. validation_threshold — tag M-class fatal constraints missing a threshold
4. derived_from      — normalise blueprint_id + derivation_version fields
5. confidence.score  — clip expert_reasoning scores to max 0.7
6. enum_fix          — remap common LLM enum spelling errors to canonical values
7. commit_hash       — inject commit hash into evidence_refs source for code_analysis constraints
8. vague_words       — tag constraints with vague action words for manual review
18. resolve_placeholders — replace {var} tokens in validation_threshold with
    evidence_refs[0].path; clear threshold + set machine_checkable=false when
    no reliable path is available
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Matches bash-style placeholder tokens like {file}, {path}, {xml_file}
# Does NOT match ${VAR} (shell variable interpolation — those are intentional)
_PLACEHOLDER_RE = re.compile(r"(?<!\$)\{([a-z_]+)\}")

# ---------------------------------------------------------------------------
# Enum fix maps (Patch 6)
# ---------------------------------------------------------------------------

ENUM_FIX_MAP: dict[str, dict[str, str]] = {
    "severity": {
        "critical": "fatal",
        "warning": "medium",
        "info": "low",
        "error": "high",
        "blocker": "fatal",
    },
    "modality": {
        "required": "must",
        "forbidden": "must_not",
        "recommended": "should",
        "optional": "should",
    },
    "source_type": {
        "code": "code_analysis",
        "docs": "official_doc",
        "issue": "community_issue",
        "expert": "expert_reasoning",
    },
    "consequence_kind": {
        "error": "bug",
        "perf": "performance",
        "money": "financial_loss",
        "crash": "bug",
        "security_issue": "safety",
    },
    "constraint_kind": {
        "business_rule": "domain_rule",
        "guardrail": "architecture_guardrail",
        "lesson": "operational_lesson",
        "boundary": "claim_boundary",
    },
}

# ---------------------------------------------------------------------------
# Regex patterns for evidence parsing (Patch 1)
# ---------------------------------------------------------------------------

# Matches:  path/to/file.py:42(function_name)   or   path/to/file.py:42
_EVIDENCE_FULL_RE = re.compile(
    r"(?P<path>[\w./\-]+\.\w+):(?P<line>\d+)(?:\((?P<fn>[\w.<>]+)\))?",
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_evidence_ref(summary: str) -> list[dict[str, Any]]:
    """Parse file:line or file:line(function) patterns from an evidence summary.

    Returns a list of dicts compatible with the EvidenceRef schema:
      {type, path, line, summary}

    If no patterns are found, returns an empty list (caller keeps original).
    """
    if not summary or not isinstance(summary, str):
        return []

    refs: list[dict[str, Any]] = []
    for m in _EVIDENCE_FULL_RE.finditer(summary):
        entry: dict[str, Any] = {
            "type": "source_code",
            "path": m.group("path"),
            "line": int(m.group("line")),
            "summary": summary.strip(),
        }
        fn = m.group("fn")
        if fn:
            entry["function"] = fn
        refs.append(entry)

    return refs


def _fix_enum(raw: dict[str, Any], field: str, fix_map: dict[str, str]) -> bool:
    """Attempt to map *field* value in *raw* through *fix_map*.

    Operates on dotted paths for nested fields (e.g. "confidence.source_type").
    Returns True if a fix was applied, False otherwise.
    """
    parts = field.split(".")
    obj: Any = raw
    for part in parts[:-1]:
        if not isinstance(obj, dict):
            return False
        obj = obj.get(part)
        if obj is None:
            return False

    if not isinstance(obj, dict):
        return False

    leaf = parts[-1]
    current = obj.get(leaf)
    if isinstance(current, str) and current in fix_map:
        obj[leaf] = fix_map[current]
        return True
    return False


def _inject_sop_metadata(
    raw: dict[str, Any],
    commit_hash: str,
    sop_version: str,
    blueprint_id: str,
) -> None:
    """Inject provenance metadata into the version sub-dict of *raw* (in-place).

    Sets schema_version, sop_version, commit_hash.  Also ensures blueprint_ids
    is present in applies_to.
    """
    version_dict = raw.setdefault("version", {})
    version_dict.setdefault("schema_version", "2.0")
    version_dict["sop_version"] = sop_version
    if commit_hash:
        version_dict["commit_hash"] = commit_hash

    # Ensure applies_to.blueprint_ids contains this blueprint
    applies_to = raw.setdefault("applies_to", {})
    bp_ids: list[str] = applies_to.setdefault("blueprint_ids", [])
    if blueprint_id and blueprint_id not in bp_ids:
        bp_ids.append(blueprint_id)


# ---------------------------------------------------------------------------
# Patch functions
# ---------------------------------------------------------------------------


def _patch_evidence_refs(constraints: list[dict[str, Any]]) -> int:
    """Patch 1: parse evidence_summary → top-level evidence_refs list.

    Raw constraints are flat dicts (enrich runs before _raw_to_constraint), so
    evidence_summary lives at the top level.  Output is always written to the
    top-level evidence_refs field (list of dicts with summary/path/line keys).

    Returns the number of constraints that received at least one parsed ref.
    """
    affected = 0
    for raw in constraints:
        # Raw constraints are flat — evidence_summary is always top-level.
        summary = raw.get("evidence_summary", "")

        if not summary:
            continue

        parsed = _parse_evidence_ref(summary)
        if not parsed:
            continue  # plain-text description — leave untouched

        # Always write to top-level evidence_refs (flat schema).
        existing = raw.setdefault("evidence_refs", [])

        # Merge: avoid duplicates by path+line combo
        existing_keys = {(r.get("path"), r.get("line")) for r in existing if isinstance(r, dict)}
        added = 0
        for ref in parsed:
            key = (ref.get("path"), ref.get("line"))
            if key not in existing_keys:
                existing.append(ref)
                existing_keys.add(key)
                added += 1

        if added:
            affected += 1

    logger.info("Patch 1 (evidence_refs): %d constraints enriched", affected)
    return affected


def _patch_resource_boundary(
    constraints: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> int:
    """Patch 2: auto-fill stage_ids for resource_boundary constraints.

    Matches against manifest.replaceable_points_by_stage (dict[stage_id, list[rp]]).
    Returns the number of constraints updated.
    """
    rp_by_stage: dict[str, list[dict[str, Any]]] = manifest.get("replaceable_points_by_stage", {})
    if not rp_by_stage:
        logger.debug(
            "Patch 2 (resource_boundary): manifest has no replaceable_points_by_stage — skipped"
        )
        return 0

    # Build a quick lookup: rp_name (lower) → list[stage_id]
    rp_to_stages: dict[str, list[str]] = {}
    for stage_id, rp_list in rp_by_stage.items():
        if not isinstance(rp_list, list):
            continue
        for rp in rp_list:
            if not isinstance(rp, dict):
                continue
            name = (rp.get("name") or rp.get("description") or "").lower().strip()
            if name:
                rp_to_stages.setdefault(name, []).append(stage_id)

    affected = 0
    for raw in constraints:
        if raw.get("constraint_kind") != "resource_boundary":
            continue

        # Raw constraints are flat — stage_ids is a top-level field.
        existing_stages: list[str] = raw.get("stage_ids") or []
        if existing_stages:
            continue  # already has stage assignments

        # Look for any rp_name match in action or evidence_summary (both top-level).
        action = raw.get("action", "")
        evidence = raw.get("evidence_summary", "")
        search_text = f"{action} {evidence}".lower()

        matched_stages: list[str] = []
        for rp_name, stage_ids in rp_to_stages.items():
            if rp_name and rp_name in search_text:
                for sid in stage_ids:
                    if sid not in matched_stages:
                        matched_stages.append(sid)

        if matched_stages:
            raw["stage_ids"] = matched_stages
            # Update target_scope if it was global but now has stages
            if raw.get("target_scope") == "global":
                raw["target_scope"] = "stage"
            affected += 1

    logger.info("Patch 2 (resource_boundary): %d constraints stage_ids filled", affected)
    return affected


def _patch_validation_threshold(constraints: list[dict[str, Any]]) -> int:
    """Patch 3: tag M-class (derived) fatal constraints missing a threshold.

    A constraint is considered M-class if it has a non-empty derived_from field.
    Returns the number of constraints tagged.
    """
    affected = 0
    for raw in constraints:
        # Check severity — top-level or nested in core
        severity = raw.get("severity") or (raw.get("core") or {}).get("severity", "")
        if severity != "fatal":
            continue

        derived_from = raw.get("derived_from")
        if not derived_from:
            continue  # not a derived (M-class) constraint

        if raw.get("validation_threshold"):
            continue  # already has one — leave it

        tags: list[str] = raw.setdefault("tags", [])
        if "needs_validation_threshold" not in tags:
            tags.append("needs_validation_threshold")
            affected += 1

    logger.info("Patch 3 (validation_threshold): %d constraints tagged", affected)
    return affected


def _patch_derived_from(
    constraints: list[dict[str, Any]],
    blueprint: dict[str, Any],
    sop_version: str,
) -> int:
    """Patch 4: normalise derived_from.blueprint_id and derivation_version.

    Returns the number of constraints where at least one field was filled.
    """
    blueprint_id: str = blueprint.get("id", "")
    affected = 0

    for raw in constraints:
        derived = raw.get("derived_from")
        if not derived or not isinstance(derived, dict):
            continue

        changed = False

        if not derived.get("blueprint_id") and blueprint_id:
            derived["blueprint_id"] = blueprint_id
            changed = True

        if not derived.get("derivation_version"):
            derived["derivation_version"] = f"sop-v{sop_version}"
            changed = True

        if changed:
            affected += 1

    logger.info("Patch 4 (derived_from): %d constraints normalised", affected)
    return affected


def _patch_confidence_score(constraints: list[dict[str, Any]]) -> int:
    """Patch 5: clip expert_reasoning confidence scores to max 0.7.

    Raw constraints are flat — source_type and confidence_score are top-level
    fields (not nested under a 'confidence' dict).

    Returns the number of constraints clipped.
    """
    affected = 0
    for raw in constraints:
        # Flat schema: source_type and confidence_score are top-level fields.
        source_type = raw.get("source_type", "")
        if source_type not in ("expert_reasoning", "expert"):
            continue

        score = raw.get("confidence_score")
        if isinstance(score, (int, float)) and score > 0.7:
            raw["confidence_score"] = 0.7
            affected += 1

    logger.info("Patch 5 (confidence_score): %d expert_reasoning scores clipped to 0.7", affected)
    return affected


def _patch_enum_fix(constraints: list[dict[str, Any]]) -> int:
    """Patch 6: remap common LLM enum spelling errors to canonical values.

    Raw constraints are flat dicts — all enum fields are at the top level
    (not nested under 'core' or 'confidence' sub-dicts).

    Returns the total number of field fixes applied (may exceed constraint count).
    """
    # (field_path, fix_map) pairs — all top-level flat fields.
    checks: list[tuple[str, dict[str, str]]] = [
        ("severity", ENUM_FIX_MAP["severity"]),
        ("modality", ENUM_FIX_MAP["modality"]),
        ("source_type", ENUM_FIX_MAP["source_type"]),
        ("consequence_kind", ENUM_FIX_MAP["consequence_kind"]),
        ("constraint_kind", ENUM_FIX_MAP["constraint_kind"]),
    ]

    total_fixes = 0
    for raw in constraints:
        for field_path, fix_map in checks:
            if _fix_enum(raw, field_path, fix_map):
                total_fixes += 1

    logger.info("Patch 6 (enum_fix): %d field values corrected", total_fixes)
    return total_fixes


# ---------------------------------------------------------------------------
# Vague words lists (Patch 8)
# ---------------------------------------------------------------------------

_VAGUE_WORDS_EN: list[str] = [
    "try to",
    "consider",
    "be careful",
    "appropriate",
    "if possible",
    "as needed",
    "ensure",
    "make sure",
]


def _patch_commit_hash(constraints: list[dict[str, Any]], commit_hash: str) -> int:
    """Patch 7: inject commit hash into evidence_summary for provenance.

    Injects into evidence_summary (the source-of-truth field that survives
    _raw_to_constraint → EvidenceRef.locator). Also injects into enriched
    evidence_refs.locator for consistency.

    Fix history:
    - v1: targeted ref["source"] which P1 never sets → no-op
    - v2: targeted ref["locator"] → works in enriched JSON but discarded
          by _raw_to_constraint which rebuilds from evidence_summary
    - v3 (current): targets evidence_summary → survives end-to-end

    Returns the number of constraints updated.
    """
    if not commit_hash:
        return 0

    short_hash = commit_hash[:7]
    count = 0
    for raw in constraints:
        # Inject for all source_types that reference repo files
        # (code_analysis, community_issue, and expert_reasoning with file refs)
        source_type = raw.get("source_type", "")
        if source_type == "official_doc":
            continue  # Skip true regulatory docs
        # Inject into evidence_summary (survives _raw_to_constraint)
        summary = raw.get("evidence_summary", "")
        if summary and short_hash not in summary:
            raw["evidence_summary"] = f"{short_hash} {summary}"
            count += 1
            # Also inject into enriched evidence_refs for consistency
            for ref in raw.get("evidence_refs", []):
                if isinstance(ref, dict) and ref.get("type") == "source_code":
                    loc = ref.get("locator", "")
                    if loc and short_hash not in loc:
                        ref["locator"] = f"{short_hash} {loc}"

    logger.info("Patch 7 (commit_hash): %d constraints updated", count)
    return count


def _patch_vague_words(constraints: list[dict[str, Any]]) -> int:
    """Patch 8: detect and rewrite vague action words.

    Checks the 'action' field for known vague phrases.
    Rewrites common patterns (Ensure X → Verify X, make sure → verify)
    and tags any remaining vague words for manual review.

    Returns the number of constraints affected.
    """
    import re as _re

    count = 0
    for raw in constraints:
        action = raw.get("action", "")
        if not action:
            continue

        original = action
        # Rewrite "Ensure X" at start → "Verify X"
        action = _re.sub(r"^Ensure\b", "Verify", action)
        action = _re.sub(r"^ensure\b", "verify", action)
        # Rewrite mid-sentence "ensure" → "verify"
        action = _re.sub(r"(?<=\s)ensure\b", "verify", action)
        # Rewrite "make sure" → "verify"
        action = _re.sub(r"[Mm]ake sure", "verify", action)
        # Rewrite "appropriate" → "specified" (context-safe)
        action = _re.sub(r"\bappropriate\b", "specified", action)

        if action != original:
            raw["action"] = action

        # Tag any remaining vague words
        action_lower = action.lower()
        found: list[str] = []
        for w in _VAGUE_WORDS_EN:
            if w in action_lower:
                found.append(w)
        if found:
            tags = raw.get("tags", [])
            if not isinstance(tags, list):
                tags = []
            tags.append(f"P4_vague_words:{','.join(found)}")
            raw["tags"] = tags

        if action != original or found:
            count += 1

    logger.info("Patch 8 (vague_words): %d constraints rewritten/tagged", count)
    return count


# Regulatory keywords that justify official_doc source_type
_REGULATORY_KEYWORDS = [
    "证监会",
    "csrc",
    "交易所规则",
    "上交所",
    "深交所",
    "保证金",
    "印花税",
    "交割制度",
    "融资融券",
    "regulation",
    "rule no.",
    "circular",
]


def _patch_source_type_correction(
    constraints: list[dict[str, Any]],
    blueprint: dict[str, Any],
) -> int:
    """Patch 9: correct source_type based on evidence content and BD provenance.

    Two directions:
    1. Downgrade: official_doc → code_analysis when evidence is not regulatory
    2. Upgrade: code_analysis/expert_reasoning → official_doc when constraint
       derives from an RC-type BD (regulatory rule)

    Returns the number of constraints corrected.
    """
    # Build RC BD set from blueprint (only non-missing, non-INTERACTION RCs)
    rc_bd_ids: set[str] = set()
    for bd in blueprint.get("business_decisions", []):
        if isinstance(bd, dict):
            bd_type = bd.get("type", "")
            bd_status = bd.get("status", "")
            bd_id = bd.get("id", "")
            # RC or RC/* types are regulatory, BUT:
            # - missing gap BDs use code_analysis (gap confirmed via code)
            # - INTERACTION BDs (BD-I*) are cross-BD aggregates, not regulations
            is_rc = bd_type.startswith("RC") or "/RC" in bd_type
            is_missing = bd_status == "missing"
            is_interaction = bd_id.startswith("BD-I")
            if is_rc and not is_missing and not is_interaction:
                rc_bd_ids.add(bd_id)

    count = 0
    for raw in constraints:
        source_type = raw.get("source_type", "")
        derived_from = raw.get("derived_from")
        bd_id = ""
        if isinstance(derived_from, dict):
            bd_id = derived_from.get("business_decision_id", "")

        # Direction 1: downgrade non-regulatory official_doc
        if source_type == "official_doc":
            # Keep official_doc if evidence has regulatory keywords
            evidence = (raw.get("evidence_summary") or "").lower()
            refs_text = ""
            for ref in raw.get("evidence_refs", []):
                if isinstance(ref, dict):
                    refs_text += (
                        ref.get("summary", "") + " " + ref.get("locator", "") + " "
                    ).lower()
            combined = f"{evidence} {refs_text}"

            # Force-downgrade INTERACTION BDs regardless of keywords
            if bd_id.startswith("BD-I"):
                raw["source_type"] = "code_analysis"
                count += 1
                continue
            if any(kw in combined for kw in _REGULATORY_KEYWORDS):
                continue  # legitimate official_doc
            # Keep official_doc if derived from RC-type BD
            if bd_id in rc_bd_ids:
                continue  # RC-derived → official_doc is correct

            raw["source_type"] = "code_analysis"
            count += 1

        # Direction 2: upgrade RC-derived constraints to official_doc
        elif bd_id in rc_bd_ids and source_type in (
            "code_analysis",
            "expert_reasoning",
        ):
            raw["source_type"] = "official_doc"
            count += 1

    logger.info(
        "Patch 9 (source_type_correction): %d constraints corrected",
        count,
    )
    return count


def _patch_stage_id_override(
    constraints: list[dict[str, Any]],
    blueprint: dict[str, Any],
) -> int:
    """Patch 10: override illegal stage_ids for derive/audit/global constraints.

    Per-stage extract constraints already get deterministic stage_ids in
    con_synthesize (line 1093). This patch handles the remaining constraints:
    - derive constraints: map BD's stage field → closest legal stage
    - audit/global: skip (target_scope=global, stage_ids=[])

    Uses a mapping from commonly invented stage names to legal ones.
    Unknown illegal stage_ids are logged and replaced with empty list
    (falls back to target_scope=global).

    Returns the number of constraints whose stage_ids were corrected.
    """
    # Build legal stage set from blueprint
    legal_stages = {
        s["id"] for s in blueprint.get("stages", []) if isinstance(s, dict) and "id" in s
    }

    if not legal_stages:
        return 0

    # Mapping from common LLM-invented stage names to legal stages
    stage_mapping = {
        "execution_feasibility": "cost_modeling",
        # cross_stage → global (not a single stage; preserves multi-stage intent)
        # Handled separately below: any stage_id containing "cross" → global scope
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
    }

    count = 0
    for raw in constraints:
        # Skip global/edge scope — they don't use stage_ids
        scope = raw.get("target_scope", "")
        if scope in ("global", "edge"):
            continue

        stage_ids = raw.get("stage_ids", [])
        if not stage_ids:
            continue

        # Special case: cross_stage → promote to global scope
        if any("cross" in sid for sid in stage_ids):
            raw["stage_ids"] = []
            raw["target_scope"] = "global"
            count += 1
            continue

        fixed = []
        changed = False
        for sid in stage_ids:
            if sid in legal_stages:
                fixed.append(sid)
            elif sid in stage_mapping and stage_mapping[sid] in legal_stages:
                fixed.append(stage_mapping[sid])
                changed = True
            else:
                logger.warning(
                    "Patch 10: unmapped stage_id '%s' in %s — dropping (constraint becomes global)",
                    sid,
                    raw.get("id", "?"),
                )
                changed = True

        if changed:
            # Deduplicate while preserving order
            seen: set[str] = set()
            deduped = [s for s in fixed if not (s in seen or seen.add(s))]
            if deduped:
                raw["stage_ids"] = deduped
            else:
                # All stage_ids were invalid → fall back to global
                raw["stage_ids"] = []
                raw["target_scope"] = "global"
            count += 1

    logger.info("Patch 10 (stage_id_override): %d constraints corrected", count)
    return count


# ---------------------------------------------------------------------------
# v3 新增 Patches P11-P15
# ---------------------------------------------------------------------------

_RUNTIME_PERSPECTIVE_PATTERNS = [
    (re.compile(r"[Ww]hen\s+(.*?)\s+is called"), lambda m: f"When implementing {m.group(1)}"),
    (re.compile(r"[Ww]hen\s+(.*?)\s+executes"), lambda m: f"When implementing {m.group(1)}"),
    (re.compile(r"[Aa]t runtime"), lambda _: "during implementation"),
    (re.compile(r"[Ww]hen invoked"), lambda _: "When implementing"),
]


def _patch_when_perspective(constraints: list[dict[str, Any]]) -> int:
    """P11: Fix runtime perspective → coding-time perspective in 'when' field.

    SOP rule: when MUST use coding-time perspective ("When implementing X"),
    NOT runtime perspective ("When X is called").
    """
    count = 0
    for raw in constraints:
        when = raw.get("when", "")
        original = when
        for pattern, replacer in _RUNTIME_PERSPECTIVE_PATTERNS:
            when = pattern.sub(replacer, when)
        if when != original:
            raw["when"] = when
            count += 1
    if count:
        logger.info("Patch 11 (when_perspective): %d constraints corrected", count)
    return count


def _patch_consequence_quality(constraints: list[dict[str, Any]]) -> int:
    """P12: Enforce consequence_description quality.

    Tags constraints where consequence_description is <20 chars, equals the
    consequence_kind enum value, or contains vague words.
    """
    _CONSEQUENCE_ENUM_WORDS = {
        "bug",
        "performance",
        "financial_loss",
        "data_corruption",
        "service_disruption",
        "operational_failure",
        "compliance",
        "safety",
        "false_claim",
    }
    count = 0
    for raw in constraints:
        desc = raw.get("consequence_description", "")
        needs_fix = (
            len(desc) < 20
            or desc.strip().lower() in _CONSEQUENCE_ENUM_WORDS
            or any(
                w in desc.lower()
                for w in (
                    "incorrect results",
                    "program error",
                    "performance degradation",
                    "unpredictable",
                )
            )
        )
        if needs_fix:
            tags = raw.setdefault("tags", [])
            if "P12_consequence_needs_fix" not in tags:
                tags.append("P12_consequence_needs_fix")
            count += 1
    if count:
        logger.info("Patch 12 (consequence_quality): %d constraints tagged", count)
    return count


_ABSOLUTE_WORD_RE = re.compile(r"\ball\s+(\w+)", re.IGNORECASE)


def _patch_absolute_words(constraints: list[dict[str, Any]]) -> int:
    """P13: Replace 'all X' with 'each X' in when/action fields.

    Mirrors blueprint P17. Prevents over-generalization in constraint language.
    """
    count = 0
    for raw in constraints:
        for field in ("when", "action"):
            text = raw.get(field, "")
            new_text = _ABSOLUTE_WORD_RE.sub(r"each \1", text)
            if new_text != text:
                raw[field] = new_text
                count += 1
    if count:
        logger.info("Patch 13 (absolute_words): %d replacements", count)
    return count


_HARDCODED_RE = re.compile(r"row\[\w+_IDX\]|self\.__\w+|_[A-Z]{2,}_IDX")


def _patch_hardcoded_constants(constraints: list[dict[str, Any]]) -> int:
    """P14: Tag constraints with hardcoded source-code constants in action.

    SOP rule: action 中用业务语义，不用源码常量。
    """
    count = 0
    for raw in constraints:
        action = raw.get("action", "")
        if _HARDCODED_RE.search(action):
            tags = raw.setdefault("tags", [])
            if "P14_hardcoded_constant" not in tags:
                tags.append("P14_hardcoded_constant")
            count += 1
    if count:
        logger.info("Patch 14 (hardcoded_constants): %d constraints tagged", count)
    return count


def _patch_hash_compute(constraints: list[dict[str, Any]]) -> int:
    """P15: Compute content hash for constraints missing one.

    hash = sha256(when + modality + action + consequence_kind + consequence_description)[:16]
    Must run LAST since hash depends on all content fields.
    """
    import hashlib
    import json as _json

    count = 0
    for raw in constraints:
        if raw.get("hash"):
            continue
        content = _json.dumps(
            {
                "when": raw.get("when", ""),
                "modality": raw.get("modality", ""),
                "action": raw.get("action", ""),
                "consequence_kind": raw.get("consequence_kind", ""),
                "consequence_description": raw.get("consequence_description", ""),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        raw["hash"] = hashlib.sha256(content.encode()).hexdigest()[:16]
        count += 1
    if count:
        logger.info("Patch 15 (hash_compute): %d hashes computed", count)
    return count


def _patch_guard_pattern(constraints: list[dict[str, Any]]) -> int:
    """P16: Auto-construct guard_pattern for rationalization_guard missing it.

    When con_extract_rationalization produces constraints with
    constraint_kind=rationalization_guard but no guard_pattern, this patch
    constructs one from the existing when/action/consequence fields.
    """
    count = 0
    for raw in constraints:
        if raw.get("constraint_kind") != "rationalization_guard":
            continue
        if raw.get("guard_pattern"):
            continue  # already has one
        # Construct guard_pattern from existing fields
        action = raw.get("action", "")
        when = raw.get("when", "")
        consequence = raw.get("consequence_description", "")
        raw["guard_pattern"] = {
            "excuse": f"Rationalization scenario: {when}",
            "rebuttal": action,
            "red_flags": [
                f"Skipping the rule because: {when}",
            ],
            "violation_detector": consequence[:200] if consequence else "",
            "_auto_generated": True,  # Mark as synthetic — LLM-extracted values should override
        }
        count += 1
    if count:
        logger.info("Patch 16 (guard_pattern): %d rationalization_guard constraints patched", count)
    return count


# ---------------------------------------------------------------------------
# Patch 17: modality/severity consistency
# ---------------------------------------------------------------------------


def _patch_modality_severity(constraints: list[dict[str, Any]]) -> int:
    """Patch 17: upgrade modality when severity contradicts it.

    Rule: severity=high or fatal implies the constraint is mandatory,
    so modality should be must or must_not (not should/should_not).
    """
    count = 0
    for raw in constraints:
        severity = raw.get("severity", "")
        modality = raw.get("modality", "")
        if severity in ("high", "fatal") and modality in ("should", "should_not"):
            old = modality
            raw["modality"] = "must" if modality == "should" else "must_not"
            count += 1
            logger.debug(
                "P17: %s modality %s→%s (severity=%s)",
                raw.get("constraint_kind", "?"),
                old,
                raw["modality"],
                severity,
            )
    if count:
        logger.info("Patch 17: upgraded %d modalities", count)
    return count


# ---------------------------------------------------------------------------
# Patch 18: resolve {var} placeholders in validation_threshold
# ---------------------------------------------------------------------------


def _is_file_path(s: str) -> bool:
    """Return True if *s* looks like a real file path (contains '/' and a file suffix)."""
    return "/" in s and "." in s.rsplit("/", 1)[-1]


def _patch_resolve_placeholders(constraints: list[dict[str, Any]]) -> int:
    """Patch 18: replace {var} placeholders in validation_threshold with real paths.

    For each constraint whose validation_threshold contains one or more tokens
    matching {[a-z_]+} (bash-style placeholders, NOT ${VAR} shell variables):

    1. Extract evidence_refs[0]["path"] as the candidate replacement path.
       "evidence_refs" is the top-level flat list populated by Patch 1.
    2. If the path looks like a real file path (contains '/' and a suffix):
       - Replace ALL {var} placeholder tokens with that single path.
       - After substitution, check again for remaining placeholders.
       - If any remain -> clear threshold + set machine_checkable=False.
    3. If no reliable path is available -> clear threshold + machine_checkable=False.

    Rationale: multiple different placeholder names in one threshold almost always
    refer to the same file (the one identified in evidence_refs[0]).

    Returns the number of constraints modified.
    """
    count = 0
    for raw in constraints:
        threshold = raw.get("validation_threshold") or ""
        if not isinstance(threshold, str):
            continue

        # Only process entries that contain at least one {var} placeholder
        if not _PLACEHOLDER_RE.search(threshold):
            continue

        # Attempt to resolve using evidence_refs[0]["path"]
        refs = raw.get("evidence_refs")
        resolved_path: str = ""
        if isinstance(refs, list) and refs:
            first_ref = refs[0]
            if isinstance(first_ref, dict):
                candidate = first_ref.get("path", "")
                if isinstance(candidate, str) and _is_file_path(candidate):
                    resolved_path = candidate

        if resolved_path:
            new_threshold = _PLACEHOLDER_RE.sub(resolved_path, threshold)
            # Verify no placeholders remain after substitution
            if _PLACEHOLDER_RE.search(new_threshold):
                # Still has {var} tokens -> clear threshold
                raw["validation_threshold"] = ""
                raw["machine_checkable"] = False
            else:
                raw["validation_threshold"] = new_threshold
        else:
            # No reliable path available -> clear threshold entirely
            raw["validation_threshold"] = ""
            raw["machine_checkable"] = False

        count += 1

    if count:
        logger.info(
            "Patch 18 (resolve_placeholders): %d validation_threshold entries updated",
            count,
        )
    return count


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def enrich_constraints(
    raw_list: list[dict[str, Any]],
    blueprint: dict[str, Any],
    manifest: dict[str, Any],
    commit_hash: str,
    sop_version: str = "2.3",
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Apply 17 deterministic enrichment patches (P1-P18) to raw constraints.

    Args:
        raw_list:    List of raw constraint dicts (from agentic extraction).
        blueprint:   Parsed blueprint YAML dict (provides id, stages, etc.).
        manifest:    con_build_manifest dict — contains replaceable_points_by_stage.
        commit_hash: Repository commit hash for provenance injection.
        sop_version: Constraint SOP version string (default "2.3").

    Returns:
        A tuple of (enriched_list, patch_stats) where:
        - enriched_list is the in-place-modified raw_list.
        - patch_stats records how many constraints/fields each patch affected.
    """
    blueprint_id: str = blueprint.get("id", "")

    # --- Metadata injection (always, before patches) ---
    for raw in raw_list:
        _inject_sop_metadata(raw, commit_hash, sop_version, blueprint_id)

    # --- Sequential patches ---
    patch_stats: dict[str, int] = {}

    patch_stats["p1_evidence_refs"] = _patch_evidence_refs(raw_list)
    patch_stats["p2_resource_boundary"] = _patch_resource_boundary(raw_list, manifest)
    patch_stats["p3_validation_threshold"] = _patch_validation_threshold(raw_list)
    patch_stats["p4_derived_from"] = _patch_derived_from(raw_list, blueprint, sop_version)
    patch_stats["p5_confidence_score"] = _patch_confidence_score(raw_list)
    patch_stats["p6_enum_fix"] = _patch_enum_fix(raw_list)
    # P9 must run BEFORE P7: P9 corrects source_type (official_doc → code_analysis),
    # then P7 injects commit_hash for all non-official_doc constraints.
    patch_stats["p9_source_type"] = _patch_source_type_correction(raw_list, blueprint)
    patch_stats["p7_commit_hash"] = _patch_commit_hash(raw_list, commit_hash)
    patch_stats["p8_vague_words"] = _patch_vague_words(raw_list)
    patch_stats["p10_stage_id"] = _patch_stage_id_override(raw_list, blueprint)

    # v3 patches (P11-P15) — content quality + hash
    patch_stats["p11_when_perspective"] = _patch_when_perspective(raw_list)
    patch_stats["p12_consequence_quality"] = _patch_consequence_quality(raw_list)
    patch_stats["p13_absolute_words"] = _patch_absolute_words(raw_list)
    patch_stats["p14_hardcoded_constants"] = _patch_hardcoded_constants(raw_list)
    patch_stats["p16_guard_pattern"] = _patch_guard_pattern(raw_list)
    patch_stats["p17_modality_severity"] = _patch_modality_severity(raw_list)
    # P18 runs AFTER all other patches (other patches may add validation_threshold)
    # and BEFORE P15 (hash must reflect final resolved threshold value)
    patch_stats["p18_resolve_placeholders"] = _patch_resolve_placeholders(raw_list)
    patch_stats["p15_hash_compute"] = _patch_hash_compute(raw_list)  # MUST be last

    total_affected = sum(patch_stats.values())
    logger.info(
        "con_enrich complete: %d total patch applications across %d constraints — %s",
        total_affected,
        len(raw_list),
        ", ".join(f"{k}={v}" for k, v in patch_stats.items()),
    )

    return raw_list, patch_stats
