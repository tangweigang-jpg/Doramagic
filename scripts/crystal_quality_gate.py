#!/usr/bin/env python3
"""Crystal Quality Gate v5.3 — Schema Validator + Semantic Gate

Validates a v5.3 seed.yaml crystal against:
  Layer 1: JSON Schema (crystal_contract.schema.yaml)
  Layer 2: 19 semantic assertions (SA-01 … SA-19, incl. SA-19 translation_completeness
           driven by schemas/consumer_map.yaml)

Usage:
    python3 crystal_quality_gate.py \\
        --blueprint   path/to/LATEST.yaml \\
        --constraints path/to/LATEST.jsonl \\
        --crystal     path/to/seed.yaml \\
        [--schema     path/to/crystal_contract.schema.yaml] \\
        [--output     path/to/quality_report.json] \\
        [--strict]

Exit codes:
    0 — all gates PASS
    1 — any gate FAIL (strict mode)
    2 — bad input (file not found, wrong format)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("[error] PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

# Optional: use jsonschema if available; fall back to hand-rolled validator
try:
    from jsonschema import ValidationError as _JsValidationError
    from jsonschema import validate as _js_validate

    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


# ──────────────────────────────────────────────────────────────────────────────
# Minimal recursive validator (used when jsonschema is not installed)
# Supports: type, required, const, enum, pattern, minItems, additionalProperties
# ──────────────────────────────────────────────────────────────────────────────

_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def _minimal_validate(instance: Any, schema: dict, path: str = "$") -> list[str]:
    """Return list of validation error strings; empty = valid."""
    errors: list[str] = []
    if not isinstance(schema, dict):
        return errors

    # type check
    raw_type = schema.get("type")
    if raw_type is not None:
        type_names = [raw_type] if isinstance(raw_type, str) else list(raw_type)
        allowed = tuple(_TYPE_MAP[t] for t in type_names if t in _TYPE_MAP)
        if allowed and not isinstance(instance, allowed):
            errors.append(f"{path}: expected type {raw_type}, got {type(instance).__name__}")
            return errors  # no point descending if type is wrong

    # const
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")

    # enum
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in enum {schema['enum']}")

    # pattern (strings)
    if (
        "pattern" in schema
        and isinstance(instance, str)
        and not re.search(schema["pattern"], instance)
    ):
        errors.append(f"{path}: {instance!r} does not match pattern {schema['pattern']!r}")

    # minItems (arrays)
    if "minItems" in schema and isinstance(instance, list) and len(instance) < schema["minItems"]:
        errors.append(f"{path}: array length {len(instance)} < minItems {schema['minItems']}")

    # required + properties (objects)
    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}: missing required field '{req}'")

        props = schema.get("properties", {})
        for key, sub_schema in props.items():
            if key in instance:
                errors.extend(_minimal_validate(instance[key], sub_schema, f"{path}.{key}"))

        if schema.get("additionalProperties") is False:
            allowed_keys = set(props.keys()) | set(schema.get("patternProperties", {}).keys())
            for k in instance:
                if k not in allowed_keys and not k.startswith("$"):
                    errors.append(f"{path}: additional property not allowed: '{k}'")

    # items (arrays)
    if isinstance(instance, list) and "items" in schema:
        item_schema = schema["items"]
        for i, item in enumerate(instance):
            errors.extend(_minimal_validate(item, item_schema, f"{path}[{i}]"))

    # $ref resolution is skipped in the minimal validator (only top-level schema used)

    return errors


# ──────────────────────────────────────────────────────────────────────────────
# Layer 1: Schema Validation
# ──────────────────────────────────────────────────────────────────────────────


def validate_schema(crystal: dict, schema: dict) -> tuple[bool, str]:
    """Returns (ok, error_detail)."""
    if _HAS_JSONSCHEMA:
        try:
            _js_validate(instance=crystal, schema=schema)
            return True, ""
        except _JsValidationError as e:
            path_str = " → ".join(str(p) for p in e.absolute_path) or "(root)"
            return False, f"path: {path_str}, message: {e.message}"
    else:
        errors = _minimal_validate(crystal, schema)
        if errors:
            return False, "; ".join(errors[:5]) + (
                f" (+ {len(errors) - 5} more)" if len(errors) > 5 else ""
            )
        return True, ""


# ──────────────────────────────────────────────────────────────────────────────
# Input loaders
# ──────────────────────────────────────────────────────────────────────────────


def load_blueprint(path: Path) -> dict:
    with path.open() as f:
        data = yaml.safe_load(f)
    bd_ids = [bd["id"] for bd in (data.get("business_decisions") or []) if bd.get("id")]
    uc_ids = [uc["id"] for uc in (data.get("known_use_cases") or []) if uc.get("id")]
    return {
        "raw": data,
        "bd_ids": bd_ids,
        "uc_ids": uc_ids,
        "bd_count": len(bd_ids),
        "uc_count": len(uc_ids),
    }


def load_constraints(path: Path, domain_path: Path | None = None) -> dict:
    all_ids: list[str] = []
    fatal_ids: list[str] = []
    regular_ids: list[str] = []
    seen: set[str] = set()
    domain_skipped: list[str] = []

    def _consume(p: Path, is_domain: bool = False) -> None:
        with p.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    c = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cid = c.get("id")
                if not cid:
                    continue
                if cid in seen:
                    if is_domain:
                        domain_skipped.append(cid)
                    continue
                seen.add(cid)
                all_ids.append(cid)
                if c.get("severity") == "fatal":
                    fatal_ids.append(cid)
                else:
                    regular_ids.append(cid)

    _consume(path)
    if domain_path is not None:
        _consume(domain_path, is_domain=True)
        if domain_skipped:
            print(
                f"[warn] {len(domain_skipped)} domain constraint(s) skipped in quality gate "
                f"due to id collision with project constraints: "
                f"{domain_skipped[:10]}" + ("..." if len(domain_skipped) > 10 else ""),
                file=sys.stderr,
            )

    return {
        "all_ids": all_ids,
        "fatal_ids": fatal_ids,
        "regular_ids": regular_ids,
        "count": len(all_ids),
        "fatal_count": len(fatal_ids),
        "regular_count": len(regular_ids),
    }


def load_crystal(path: Path) -> dict:
    """Load seed.yaml. Reject .md / .seed.md files immediately."""
    suffix = path.suffix.lower()
    name_lower = path.name.lower()
    if suffix == ".md" or name_lower.endswith(".seed.md"):
        print(
            f"[error] v3.x Markdown crystals are not accepted by quality gate v5.0.\n"
            f"  Got: {path}\n"
            f"  Expected: a .yaml file conforming to crystal_contract.schema.yaml v5.0.\n"
            f"  Tip: migrate to seed.yaml format before running this gate.",
            file=sys.stderr,
        )
        sys.exit(2)
    with path.open() as f:
        return yaml.safe_load(f)


def load_schema(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


# ──────────────────────────────────────────────────────────────────────────────
# CJK detection helpers
# ──────────────────────────────────────────────────────────────────────────────

_CJK_RE = re.compile(r"[\u4e00-\u9fa5]")
# Known technical identifiers that may look like CJK context but are exempt
_VERBATIM_EXEMPT_PATTERNS = re.compile(
    r"\b(MACD|ZVT|KDJ|RSI|BOLL|SMA|EMA|ATR|OBV|VOL|PB|PE|ROE|ROA|EPS)\b"
)


def _cjk_ratio(text: str, preserve_verbatim: list[str] | None = None) -> float:
    """Fraction of characters that are CJK Han ideographs."""
    if not text:
        return 0.0
    # Remove technical identifiers before counting
    cleaned = _VERBATIM_EXEMPT_PATTERNS.sub("", text)
    total = len(cleaned)
    if total == 0:
        return 0.0
    cjk_count = len(_CJK_RE.findall(cleaned))
    return cjk_count / total


def _collect_strings(obj: Any, skip_keys: set[str] | None = None) -> list[str]:
    """Recursively collect all string values from a nested structure."""
    results: list[str] = []
    if isinstance(obj, str):
        results.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if skip_keys and k in skip_keys:
                continue
            results.extend(_collect_strings(v, skip_keys))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_collect_strings(item, skip_keys))
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Layer 2: Semantic Assertions
# Each returns (passed: bool, detail: str)
# ──────────────────────────────────────────────────────────────────────────────


def sa01_bd_coverage(crystal: dict, bp: dict) -> tuple[bool, str]:
    """SA-01: Every blueprint BD-ID appears somewhere in architecture.stages[].business_decisions[].id."""
    found: set[str] = set()
    for stage in (crystal.get("architecture") or {}).get("stages") or []:
        for bd in stage.get("business_decisions") or []:
            bid = bd.get("id")
            if bid:
                found.add(bid)
    expected = set(bp["bd_ids"])
    missing = sorted(expected - found)
    extra = sorted(found - expected)
    if missing:
        sample = missing[:10]
        return False, (
            f"missing {len(missing)}/{len(expected)} BD-IDs in crystal. "
            f"Sample: {sample}" + (f"; extra IDs: {extra[:5]}" if extra else "")
        )
    return True, f"{len(expected)}/{len(expected)} BD-IDs covered"


def sa02_uc_coverage(crystal: dict, bp: dict) -> tuple[bool, str]:
    """SA-02: intent_router.uc_entries[].uc_id = blueprint known_use_cases[].id full set."""
    router_ucs = {
        e.get("uc_id")
        for e in (crystal.get("intent_router") or {}).get("uc_entries") or []
        if e.get("uc_id")
    }
    expected = set(bp["uc_ids"])
    missing = sorted(expected - router_ucs)
    if missing:
        sample = missing[:10]
        return False, f"missing {len(missing)}/{len(expected)} UC-IDs. Sample: {sample}"
    return True, f"{len(expected)}/{len(expected)} UC-IDs covered"


def sa03_constraint_coverage(crystal: dict, cons: dict) -> tuple[bool, str]:
    """SA-03: fatal[] + regular[] id union = LATEST.jsonl full set."""
    c_section = crystal.get("constraints") or {}
    crystal_ids: set[str] = set()
    for c in (c_section.get("fatal") or []) + (c_section.get("regular") or []):
        cid = c.get("id")
        if cid:
            crystal_ids.add(cid)
    expected = set(cons["all_ids"])
    missing = sorted(expected - crystal_ids)
    if missing:
        sample = missing[:10]
        return False, (f"missing {len(missing)}/{len(expected)} constraint IDs. Sample: {sample}")
    return True, f"{len(expected)}/{len(expected)} constraint IDs covered"


def sa04_fatal_match(crystal: dict, cons: dict) -> tuple[bool, str]:
    """SA-04: crystal.constraints.fatal[].id = LATEST.jsonl fatal-severity IDs exactly."""
    c_section = crystal.get("constraints") or {}
    crystal_fatal: set[str] = {c["id"] for c in (c_section.get("fatal") or []) if c.get("id")}
    expected_fatal = set(cons["fatal_ids"])
    missing = sorted(expected_fatal - crystal_fatal)
    extra = sorted(crystal_fatal - expected_fatal)
    issues = []
    if missing:
        issues.append(f"missing fatal IDs: {missing[:10]}")
    if extra:
        issues.append(f"extra IDs not fatal in jsonl: {extra[:10]}")
    if issues:
        return False, "; ".join(issues)
    return True, f"{len(expected_fatal)} fatal IDs match exactly"


_OV_BLACKLIST = {"len(result) == 0", "not result", "result is None"}


def sa05_ov_business_semantics(crystal: dict) -> tuple[bool, str]:
    """SA-05: output_validator assertions must not use blacklisted structural predicates."""
    assertions = (crystal.get("output_validator") or {}).get("assertions") or []
    violations: list[str] = []
    empty_meaning: list[str] = []
    for a in assertions:
        aid = a.get("id", "?")
        pred = (a.get("check_predicate") or "").strip()
        meaning = (a.get("business_meaning") or "").strip()
        if pred in _OV_BLACKLIST:
            violations.append(f"{aid}: blacklisted predicate '{pred}'")
        if not meaning:
            empty_meaning.append(f"{aid}: business_meaning is empty")
    all_issues = violations + empty_meaning
    if all_issues:
        return False, "; ".join(all_issues[:8])
    n = len(assertions)
    return True, f"no blacklisted predicates, all {n} assertions have business_meaning"


def sa06_preconditions_nonempty(crystal: dict) -> tuple[bool, str]:
    """SA-06: preconditions[] must have at least 1 entry."""
    pcs = crystal.get("preconditions") or []
    if not pcs:
        return False, "preconditions[] is empty or missing"
    return True, f"{len(pcs)} precondition(s) declared"


def sa07_evidence_rules_structured(crystal: dict) -> tuple[bool, str]:
    """SA-07: evidence_quality.enforcement_rules[] each has trigger + action + violation_code."""
    rules = (crystal.get("evidence_quality") or {}).get("enforcement_rules") or []
    if not rules:
        return False, "enforcement_rules[] is empty"
    bad: list[str] = []
    for r in rules:
        rid = r.get("id", "?")
        for field in ("trigger", "action", "violation_code"):
            if not r.get(field):
                bad.append(f"{rid}: missing {field}")
    if bad:
        return False, "; ".join(bad[:8])
    return True, f"all {len(rules)} enforcement_rules have trigger+action+violation_code"


def sa08_language_uniformity(crystal: dict) -> tuple[bool, str]:
    """SA-08: CJK char ratio < 5% across all string values (except preserve_verbatim exempt paths)."""
    # Get preserve_verbatim list (field names to skip, not full paths)
    pv_list: list[str] = (
        (crystal.get("human_summary") or {})
        .get("locale_rendering", {})
        .get("preserve_verbatim", [])
    )
    pv_set = set(pv_list)

    # Collect all string values except human_summary (handled by SA-12) and preserve_verbatim keys
    skip_keys = pv_set | {"human_summary"}
    all_strings = _collect_strings(crystal, skip_keys=skip_keys)
    combined = " ".join(all_strings)
    ratio = _cjk_ratio(combined)
    if ratio >= 0.05:
        sample_cjk = _CJK_RE.findall(combined)[:20]
        return False, (
            f"CJK ratio {ratio * 100:.1f}% >= 5% threshold. Sample CJK chars: {''.join(sample_cjk)}"
        )
    return True, f"CJK ratio {ratio * 100:.2f}% < 5% threshold"


def sa09_skill_contract_complete(crystal: dict) -> tuple[bool, str]:
    """SA-09: skill_crystallization has trigger/output_path_template/captured_fields/action."""
    sc = crystal.get("skill_crystallization") or {}
    required_fields = ["trigger", "output_path_template", "captured_fields", "action"]
    missing = [f for f in required_fields if not sc.get(f)]
    if missing:
        return False, f"skill_crystallization missing: {missing}"
    cf = sc.get("captured_fields") or []
    if not cf:
        return False, "skill_crystallization.captured_fields is empty"
    return True, f"all 4 skill_crystallization contract fields present, {len(cf)} captured_fields"


def sa10_locale_contract_complete(crystal: dict) -> tuple[bool, str]:
    """SA-10: locale_contract.translation_enforcement has trigger/action/violation_code."""
    te = (crystal.get("locale_contract") or {}).get("translation_enforcement") or {}
    required = ["trigger", "action", "violation_code"]
    missing = [f for f in required if not te.get(f)]
    if missing:
        return False, f"locale_contract.translation_enforcement missing: {missing}"
    return True, "trigger + action + violation_code all present"


def sa11_hard_gates_count(crystal: dict) -> tuple[bool, str]:
    """SA-11: acceptance.hard_gates[] has at least 4 entries."""
    gates = (crystal.get("acceptance") or {}).get("hard_gates") or []
    if len(gates) < 4:
        return False, f"only {len(gates)} hard_gates found; need >= 4"
    return True, f"{len(gates)} hard_gates (>= 4)"


def sa12_human_summary_english(crystal: dict) -> tuple[bool, str]:
    """SA-12: human_summary.* strings CJK ratio < 2% (preserve_verbatim exempt)."""
    hs = crystal.get("human_summary") or {}
    pv_list: list[str] = hs.get("locale_rendering", {}).get("preserve_verbatim", [])
    pv_set = set(pv_list)
    # Collect strings from human_summary but skip preserve_verbatim-listed keys
    hs_strings = _collect_strings(hs, skip_keys=pv_set)
    combined = " ".join(hs_strings)
    ratio = _cjk_ratio(combined)
    if ratio >= 0.02:
        sample = _CJK_RE.findall(combined)[:20]
        return False, (
            f"human_summary CJK ratio {ratio * 100:.1f}% >= 2% threshold. Sample: {''.join(sample)}"
        )
    return True, f"human_summary CJK ratio {ratio * 100:.2f}% < 2%"


def sa13_source_language_lock(crystal: dict) -> tuple[bool, str]:
    """SA-13: meta.source_language == 'en'."""
    lang = (crystal.get("meta") or {}).get("source_language")
    if lang != "en":
        return False, f"meta.source_language = {lang!r}, expected 'en'"
    return True, "meta.source_language == 'en'"


def sa14_authoritative_artifact(crystal: dict) -> tuple[bool, str]:
    """SA-14: meta.authoritative_artifact has primary/non_authoritative_derivatives/rule;
    primary == 'seed.yaml'; non_authoritative_derivatives has at least 2 items."""
    aa = (crystal.get("meta") or {}).get("authoritative_artifact")
    if not aa:
        return False, "meta.authoritative_artifact missing"
    issues: list[str] = []
    for field in ("primary", "non_authoritative_derivatives", "rule"):
        if field not in aa:
            issues.append(f"meta.authoritative_artifact missing {field}")
    if issues:
        return False, "; ".join(issues)
    if aa.get("primary") != "seed.yaml":
        issues.append(f"primary = {aa['primary']!r}, expected 'seed.yaml'")
    derivatives = aa.get("non_authoritative_derivatives") or []
    if len(derivatives) < 2:
        issues.append(f"non_authoritative_derivatives has {len(derivatives)} item(s) (need >= 2)")
    if issues:
        return False, "; ".join(issues)
    return True, (
        f"primary = 'seed.yaml', {len(derivatives)} non_authoritative_derivatives, rule present"
    )


def sa15_execution_protocol(crystal: dict) -> tuple[bool, str]:
    """SA-15: meta.execution_protocol has install_trigger/execute_trigger/on_execute/workspace_resolution;
    on_execute >= 3 items; workspace_resolution has scripts_path/skills_path/trace_path."""
    ep = (crystal.get("meta") or {}).get("execution_protocol")
    if not ep:
        return False, "meta.execution_protocol missing"
    issues: list[str] = []
    for field in ("install_trigger", "execute_trigger", "on_execute", "workspace_resolution"):
        if field not in ep:
            issues.append(f"meta.execution_protocol missing {field}")
    if issues:
        return False, "; ".join(issues)
    on_execute = ep.get("on_execute") or []
    if len(on_execute) < 3:
        issues.append(
            f"meta.execution_protocol.on_execute has only {len(on_execute)} items (need >= 3)"
        )
    wr = ep.get("workspace_resolution") or {}
    for field in ("scripts_path", "skills_path", "trace_path"):
        if field not in wr:
            issues.append(f"meta.execution_protocol.workspace_resolution missing {field}")
    if issues:
        return False, "; ".join(issues)
    return True, (
        f"install_trigger + execute_trigger present, {len(on_execute)} on_execute steps, "
        f"workspace_resolution complete"
    )


def sa17_capability_catalog(crystal: dict) -> tuple[bool, str]:
    """SA-17: capability_catalog completeness — all UCs covered, no duplicates, uc_count accurate, sample_triggers non-empty."""
    cat = (
        (crystal.get("post_install_notice") or {})
        .get("message_template", {})
        .get("capability_catalog")
    )
    if not cat:
        return False, "missing capability_catalog in post_install_notice.message_template"

    gs = cat.get("group_strategy") or {}
    if gs.get("source") not in ("blueprint_declared", "auto_grouped"):
        return False, f"group_strategy.source invalid: {gs.get('source')!r}"

    groups = cat.get("groups") or []
    if not groups:
        return False, "capability_catalog.groups is empty"

    # UC full-set coverage + no duplicates
    intent_ucs = {
        e["uc_id"]
        for e in (crystal.get("intent_router") or {}).get("uc_entries", [])
        if e.get("uc_id")
    }
    catalog_uc_pairs: list[tuple[str, str]] = []  # (group_id, uc_id)
    for g in groups:
        gid = g.get("group_id", "?")
        for uc_entry in g.get("ucs") or []:
            catalog_uc_pairs.append((gid, uc_entry.get("uc_id", "?")))

    seen: dict[str, str] = {}
    for gid, uc_id in catalog_uc_pairs:
        if uc_id in seen:
            return False, f"{uc_id} appears in multiple groups: [{seen[uc_id]}, {gid}]"
        seen[uc_id] = gid

    catalog_ucs = set(seen.keys())
    missing = intent_ucs - catalog_ucs
    extra = catalog_ucs - intent_ucs
    if missing:
        return False, f"UCs missing from catalog: {sorted(missing)[:5]}"
    if extra:
        return False, f"catalog has UCs not in intent_router: {sorted(extra)[:5]}"

    # uc_count must match actual ucs[] length
    for g in groups:
        declared = g.get("uc_count", -1)
        actual = len(g.get("ucs") or [])
        if declared != actual:
            return (
                False,
                f"group '{g.get('group_id')}' has uc_count={declared} but ucs[] has {actual} items",
            )

    # sample_triggers must be non-empty for every UC entry
    for g in groups:
        for i, uc in enumerate(g.get("ucs") or []):
            if not uc.get("sample_triggers"):
                return False, (
                    f"group '{g.get('group_id')}' ucs[{i}] ({uc.get('uc_id')}) has empty sample_triggers"
                )

    return True, (f"{len(groups)} groups, {len(catalog_ucs)} UCs, all covered, no duplicates")


_SHORT_WORD_ALLOWLIST = {
    "US",
    "UK",
    "AI",
    "ML",
    "IT",
    "EU",
    "UI",
    "UX",
    "DB",
    "CI",
    "CD",
    "OS",
    "3D",
}
_SENTENCE_TERMINATORS = {".", "?", "!", "。", "？", "！"}


def sa18_short_description_no_midcut(crystal: dict) -> tuple[bool, str]:
    """SA-18: short_description must not end mid-sentence.

    Each capability_catalog.groups[].ucs[].short_description must end either
    with a sentence terminator (. ? ! 。) or with a word ≥ 3 chars (short
    common abbreviations like US / UK / AI are whitelisted).

    Catches regressions to the '[:80]' mid-cut bug that required Fix #1.
    """
    cat = (
        (crystal.get("post_install_notice") or {})
        .get("message_template", {})
        .get("capability_catalog")
    )
    if not cat:
        return False, "capability_catalog missing (run SA-17 first)"

    suspicious: list[str] = []
    checked = 0
    for g in cat.get("groups") or []:
        for uc in g.get("ucs") or []:
            sd = (uc.get("short_description") or "").strip()
            if not sd:
                continue
            checked += 1
            if sd[-1] in _SENTENCE_TERMINATORS:
                continue
            last_word = sd.split()[-1] if sd.split() else ""
            if len(last_word) >= 3:
                continue
            if last_word.upper() in _SHORT_WORD_ALLOWLIST:
                continue
            suspicious.append(f"{uc.get('uc_id')}: …{sd[-40:]!r}")

    if suspicious:
        sample = "; ".join(suspicious[:3])
        extra = f" (+{len(suspicious) - 3} more)" if len(suspicious) > 3 else ""
        return (
            False,
            f"{len(suspicious)}/{checked} short_description(s) look mid-cut: {sample}{extra}",
        )

    return True, f"all {checked} short_description(s) end cleanly"


def sa19_translation_completeness(crystal: dict) -> tuple[bool, str]:
    """SA-19 (v5.3): every NR+TR field in consumer_map is listed in user_facing_fields.

    Reads schemas/consumer_map.yaml → user_facing_fields_expected[] and diffs against
    crystal.locale_contract.user_facing_fields. Any missing path = FAIL with that path
    in the violation signal. Root-cause guard for translator-scope drift — the class of
    bug that would leave non-en users seeing untranslated English in error messages,
    stage narratives, or PIN catalog entries.
    """
    from pathlib import Path as _Path

    import yaml as _yaml

    # Locate consumer_map.yaml relative to this script
    script_dir = _Path(__file__).resolve().parent
    repo_root = script_dir.parent
    cmap_path = repo_root / "schemas" / "consumer_map.yaml"
    if not cmap_path.exists():
        return False, f"consumer_map.yaml not found at {cmap_path}"

    try:
        cmap = _yaml.safe_load(cmap_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"consumer_map.yaml parse error: {e}"

    expected = cmap.get("user_facing_fields_expected") or []
    if not expected:
        return False, "consumer_map.yaml user_facing_fields_expected[] empty"

    actual = set((crystal.get("locale_contract") or {}).get("user_facing_fields") or [])
    missing = [p for p in expected if p not in actual]

    if missing:
        sample = "; ".join(missing[:5])
        extra = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
        return (
            False,
            f"{len(missing)}/{len(expected)} NR+TR field(s) missing from "
            f"locale_contract.user_facing_fields: {sample}{extra}",
        )
    return True, f"all {len(expected)} NR+TR fields declared as user-facing"


def sa16_post_install_notice(crystal: dict) -> tuple[bool, str]:
    """SA-16: post_install_notice completeness + cross-validation against intent_router."""
    pin = crystal.get("post_install_notice")
    if not pin:
        return False, "post_install_notice missing"
    issues: list[str] = []

    # trigger check
    if pin.get("trigger") != "skill_installation_complete":
        issues.append(f"trigger = {pin.get('trigger')!r}, expected 'skill_installation_complete'")

    # message_template completeness
    mt = pin.get("message_template") or {}
    for field in ("positioning", "featured_entries", "more_info_hint"):
        if field not in mt:
            issues.append(f"post_install_notice.message_template missing {field}")

    if "featured_entries" in mt:
        entries = mt.get("featured_entries") or []
        if len(entries) != 3:
            issues.append(f"featured_entries has {len(entries)} item(s) (need exactly 3)")
        # per-entry field check
        for i, entry in enumerate(entries):
            for field in ("uc_id", "beginner_prompt"):
                if not entry.get(field):
                    issues.append(f"post_install_notice.featured_entries[{i}] missing {field}")

        # cross-validate uc_id against intent_router
        router_uc_ids = {
            e.get("uc_id")
            for e in (crystal.get("intent_router") or {}).get("uc_entries") or []
            if e.get("uc_id")
        }
        for i, entry in enumerate(entries):
            uc_id = entry.get("uc_id")
            if uc_id and uc_id not in router_uc_ids:
                issues.append(
                    f"post_install_notice.featured_entries[{i}].uc_id = {uc_id!r} "
                    f"not in intent_router"
                )

    # enforcement check
    enforcement = pin.get("enforcement") or {}
    vc = enforcement.get("violation_code")
    if vc != "PIN-01":
        issues.append(f"enforcement.violation_code = {vc!r}, expected 'PIN-01'")

    if issues:
        return False, "; ".join(issues)
    return True, (
        "trigger OK, message_template complete (positioning + 3 featured_entries + more_info_hint), "
        "all uc_ids in intent_router, violation_code PIN-01"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Orchestration
# ──────────────────────────────────────────────────────────────────────────────

_SA_REGISTRY = [
    ("SA-01", "BD coverage", sa01_bd_coverage, ("crystal", "bp")),
    ("SA-02", "UC coverage", sa02_uc_coverage, ("crystal", "bp")),
    ("SA-03", "Constraint coverage", sa03_constraint_coverage, ("crystal", "cons")),
    ("SA-04", "Fatal match", sa04_fatal_match, ("crystal", "cons")),
    ("SA-05", "OV business semantics", sa05_ov_business_semantics, ("crystal",)),
    ("SA-06", "Preconditions non-empty", sa06_preconditions_nonempty, ("crystal",)),
    ("SA-07", "Evidence rules structured", sa07_evidence_rules_structured, ("crystal",)),
    ("SA-08", "Language uniformity", sa08_language_uniformity, ("crystal",)),
    ("SA-09", "Skill contract complete", sa09_skill_contract_complete, ("crystal",)),
    ("SA-10", "Locale contract complete", sa10_locale_contract_complete, ("crystal",)),
    ("SA-11", "Hard gate count", sa11_hard_gates_count, ("crystal",)),
    ("SA-12", "human_summary English", sa12_human_summary_english, ("crystal",)),
    ("SA-13", "Source language lock", sa13_source_language_lock, ("crystal",)),
    ("SA-14", "authoritative_artifact completeness", sa14_authoritative_artifact, ("crystal",)),
    ("SA-15", "execution_protocol completeness", sa15_execution_protocol, ("crystal",)),
    ("SA-16", "post_install_notice completeness", sa16_post_install_notice, ("crystal",)),
    ("SA-17", "capability_catalog completeness", sa17_capability_catalog, ("crystal",)),
    ("SA-18", "short_description no mid-cut", sa18_short_description_no_midcut, ("crystal",)),
    (
        "SA-19",
        "translation completeness (consumer_map)",
        sa19_translation_completeness,
        ("crystal",),
    ),
]


def _call_sa(fn, args_spec: tuple, crystal: dict, bp: dict, cons: dict) -> tuple[bool, str]:
    kwargs: dict = {}
    for arg in args_spec:
        if arg == "crystal":
            kwargs["crystal"] = crystal
        elif arg == "bp":
            kwargs["bp"] = bp
        elif arg == "cons":
            kwargs["cons"] = cons
    return fn(**kwargs)


def run_gate(crystal: dict, schema: dict, bp: dict, cons: dict) -> dict:
    # Layer 1
    schema_ok, schema_err = validate_schema(crystal, schema)

    # Layer 2
    sa_results: list[dict] = []
    for sa_id, sa_name, sa_fn, sa_args in _SA_REGISTRY:
        try:
            passed, detail = _call_sa(sa_fn, sa_args, crystal, bp, cons)
        except Exception as exc:
            passed = False
            detail = f"assertion raised exception: {exc}"
        sa_results.append({"id": sa_id, "name": sa_name, "passed": passed, "detail": detail})

    # Coverage numbers for summary display
    c_section = crystal.get("constraints") or {}
    crystal_fatal_ids = {c["id"] for c in (c_section.get("fatal") or []) if c.get("id")}
    crystal_regular_ids = {c["id"] for c in (c_section.get("regular") or []) if c.get("id")}
    crystal_all_ids = crystal_fatal_ids | crystal_regular_ids

    router_ucs = {
        e.get("uc_id")
        for e in (crystal.get("intent_router") or {}).get("uc_entries") or []
        if e.get("uc_id")
    }
    arch_bds: set[str] = set()
    for stage in (crystal.get("architecture") or {}).get("stages") or []:
        for bd in stage.get("business_decisions") or []:
            if bd.get("id"):
                arch_bds.add(bd["id"])

    coverage = {
        "bd": {
            "found": len(arch_bds & set(bp["bd_ids"])),
            "total": bp["bd_count"],
        },
        "uc": {
            "found": len(router_ucs & set(bp["uc_ids"])),
            "total": bp["uc_count"],
        },
        "constraints": {
            "found": len(crystal_all_ids & set(cons["all_ids"])),
            "total": cons["count"],
            "fatal_found": len(crystal_fatal_ids & set(cons["fatal_ids"])),
            "fatal_total": cons["fatal_count"],
            "regular_found": len(crystal_regular_ids & set(cons["regular_ids"])),
            "regular_total": cons["regular_count"],
        },
    }

    # Crystal size
    crystal_size: dict = {}  # filled later by caller with file stats

    overall_pass = schema_ok and all(r["passed"] for r in sa_results)

    return {
        "schema_validation": {"passed": schema_ok, "error": schema_err},
        "coverage": coverage,
        "semantic_assertions": sa_results,
        "overall_pass": overall_pass,
        "crystal_size": crystal_size,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Reporting
# ──────────────────────────────────────────────────────────────────────────────


def format_summary(report: dict) -> str:
    out: list[str] = []
    W = 70
    out.append("=" * W)
    out.append("Crystal Quality Gate v5.3 — Report")
    out.append("=" * W)

    # Layer 1
    sv = report["schema_validation"]
    out.append("")
    out.append("【Schema Validation】")
    if sv["passed"]:
        out.append("  structural validation: ✓")
    else:
        out.append(f"  structural validation: ✗  ({sv['error']})")

    # Coverage
    cov = report["coverage"]
    out.append("")
    out.append("【Coverage】")
    bd = cov["bd"]
    out.append(
        f"  BD:          {bd['found']:>4}/{bd['total']:<4}  {'✓' if bd['found'] == bd['total'] else '✗'}"
    )
    uc = cov["uc"]
    out.append(
        f"  UC:          {uc['found']:>4}/{uc['total']:<4}  {'✓' if uc['found'] == uc['total'] else '✗'}"
    )
    cn = cov["constraints"]
    out.append(
        f"  Constraints: {cn['found']:>4}/{cn['total']:<4}  {'✓' if cn['found'] == cn['total'] else '✗'}"
    )
    out.append(
        f"    - fatal:   {cn['fatal_found']:>4}/{cn['fatal_total']:<4}  {'✓' if cn['fatal_found'] == cn['fatal_total'] else '✗'}"
    )
    out.append(
        f"    - regular: {cn['regular_found']:>4}/{cn['regular_total']:<4}  {'✓' if cn['regular_found'] == cn['regular_total'] else '✗'}"
    )

    # Semantic assertions
    out.append("")
    out.append("【Semantic Assertions】")
    for sa in report["semantic_assertions"]:
        mark = "✓" if sa["passed"] else "✗"
        out.append(f"  {sa['id']} {sa['name']}: {mark}  ({sa['detail']})")

    # Size
    sz = report.get("crystal_size") or {}
    if sz:
        out.append("")
        out.append("【Crystal size】")
        kb = sz.get("bytes", 0) / 1024
        out.append(f"  seed.yaml: {sz.get('lines', 0)} lines / {kb:.1f}KB")

    # Final verdict
    out.append("")
    out.append("=" * W)
    verdict = "✓ PASS" if report["overall_pass"] else "✗ FAIL"
    out.append(f"门禁总判定: {verdict}")
    out.append("=" * W)

    if not report["overall_pass"]:
        fails = []
        if not report["schema_validation"]["passed"]:
            fails.append("Schema Validation")
        for sa in report["semantic_assertions"]:
            if not sa["passed"]:
                fails.append(sa["id"])
        out.append(f"Failed gates: {', '.join(fails)}")

    return "\n".join(out)


# ──────────────────────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────────────────────

_DEFAULT_SCHEMA = Path(__file__).parent.parent / "schemas" / "crystal_contract.schema.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--blueprint", type=Path, required=True, help="LATEST.yaml path")
    parser.add_argument("--constraints", type=Path, required=True, help="LATEST.jsonl path")
    parser.add_argument(
        "--domain-constraints",
        type=Path,
        default=None,
        help="Optional domain-universal constraints JSONL (merged into all_ids for SA-03)",
    )
    parser.add_argument("--crystal", type=Path, required=True, help="seed.yaml path (.md rejected)")
    parser.add_argument(
        "--schema",
        type=Path,
        default=_DEFAULT_SCHEMA,
        help=f"crystal_contract.schema.yaml (default: {_DEFAULT_SCHEMA})",
    )
    parser.add_argument("--output", type=Path, default=None, help="quality_report.json path")
    parser.add_argument("--strict", action="store_true", help="exit 1 on any failure")
    args = parser.parse_args()

    # Input validation
    for label, p in [
        ("blueprint", args.blueprint),
        ("constraints", args.constraints),
        ("crystal", args.crystal),
        ("schema", args.schema),
    ]:
        if not p.exists():
            print(f"[error] {label} file not found: {p}", file=sys.stderr)
            return 2
    if args.domain_constraints is not None and not args.domain_constraints.exists():
        print(
            f"[error] domain-constraints file not found: {args.domain_constraints}",
            file=sys.stderr,
        )
        return 2

    # Reject .md early (load_crystal also checks, but do it here for clarity)
    if args.crystal.suffix.lower() == ".md" or args.crystal.name.lower().endswith(".seed.md"):
        print(
            f"[error] v3.x Markdown input rejected.\n"
            f"  File: {args.crystal}\n"
            f"  Quality gate v5.0 only accepts .yaml crystals conforming to crystal_contract.schema.yaml.",
            file=sys.stderr,
        )
        return 2

    schema = load_schema(args.schema)
    bp = load_blueprint(args.blueprint)
    cons = load_constraints(args.constraints, args.domain_constraints)
    crystal = load_crystal(args.crystal)

    report = run_gate(crystal, schema, bp, cons)

    # Crystal size stats
    text = args.crystal.read_text(encoding="utf-8")
    report["crystal_size"] = {
        "lines": len(text.splitlines()),
        "bytes": len(text.encode("utf-8")),
    }

    # Meta
    report["meta"] = {
        "blueprint_path": str(args.blueprint),
        "constraints_path": str(args.constraints),
        "crystal_path": str(args.crystal),
        "schema_path": str(args.schema),
        "jsonschema_library": _HAS_JSONSCHEMA,
        "bp_bd_count": bp["bd_count"],
        "bp_uc_count": bp["uc_count"],
        "cons_count": cons["count"],
        "cons_fatal_count": cons["fatal_count"],
    }

    print(format_summary(report))

    output_path = args.output
    if output_path is None:
        stem = args.crystal.stem
        output_path = args.crystal.parent / f"{stem}.quality_report.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[json report] {output_path}")

    if not report["overall_pass"] and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
