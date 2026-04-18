#!/usr/bin/env python3
"""
crystal_skill_readme_emitter.py — Authoritative SKILL.md Renderer

Renders a canonical SKILL.md from a crystal seed.yaml, bypassing host-agent
paraphrase drift. The output file declares itself as a derived summary and
instructs agents to re-read seed.yaml for all behavioral decisions.

Schema authority: schemas/crystal_contract.schema.yaml (v5.2)

Exit codes:
  0  — PASS: SKILL.md written (or dry-run printed) successfully
  1  — Degraded: crystal missing required sections (post_install_notice or
       other key fields); partial output written if --output given
  2  — Input error: file not found, unreadable YAML, or bad arguments
"""

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("PyYAML required: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="crystal_skill_readme_emitter.py",
        description=(
            "Render an authoritative SKILL.md from a crystal seed.yaml.\n\n"
            "The generated file is a derived summary — agents MUST re-read seed.yaml\n"
            "for behavioral decisions. Regenerate whenever seed.yaml changes."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/crystal_skill_readme_emitter.py \\\n"
            "    --crystal knowledge/sources/finance/finance-bp-009--zvt/finance-bp-009-v5.1.seed.yaml \\\n"
            "    --output /tmp/SKILL.md\n\n"
            "  python scripts/crystal_skill_readme_emitter.py \\\n"
            "    --crystal finance-bp-009-v5.0.seed.yaml \\\n"
            "    --output /tmp/SKILL.md --overwrite"
        ),
    )
    p.add_argument(
        "--crystal",
        required=True,
        metavar="PATH",
        help="Path to the crystal seed.yaml file",
    )
    p.add_argument(
        "--output",
        required=True,
        metavar="PATH",
        help="Destination path for the rendered SKILL.md",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output file (default: abort if file exists)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Crystal loading
# ---------------------------------------------------------------------------


def load_crystal(path: Path) -> dict:
    """Load and parse a crystal YAML file. Exits with code 2 on IO/parse error."""
    if not path.exists():
        print(f"ERROR: Crystal not found: {path}", file=sys.stderr)
        sys.exit(2)
    try:
        with path.open("r", encoding="utf-8") as f:
            crystal = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"ERROR: Failed to parse YAML: {e}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(crystal, dict):
        print(f"ERROR: Crystal YAML root is not a mapping: {path}", file=sys.stderr)
        sys.exit(2)
    return crystal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _na(value: Any) -> str:
    """Return value as string, or 'n/a' if None/empty."""
    if value is None:
        return "n/a"
    s = str(value).strip()
    return s if s else "n/a"


def _pct(value: Any) -> str:
    """Format a ratio (0-1) as percentage string, or 'n/a'."""
    if value is None:
        return "n/a"
    try:
        return f"{float(value) * 100:.1f}%"
    except (ValueError, TypeError):
        return str(value)


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Build a Markdown table string from headers and rows."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    def fmt_row(cells: list[str]) -> str:
        parts = []
        for i, cell in enumerate(cells):
            width = col_widths[i] if i < len(col_widths) else len(str(cell))
            parts.append(str(cell).ljust(width))
        return "| " + " | ".join(parts) + " |"

    separator = "| " + " | ".join("-" * w for w in col_widths) + " |"
    lines = [fmt_row(headers), separator]
    for row in rows:
        padded = list(row) + [""] * (len(headers) - len(row))
        lines.append(fmt_row([str(c) for c in padded]))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _render_capability_catalog(cap_cat: dict) -> list[str]:
    """Render capability_catalog as markdown (v5.2+).

    Returns a list of lines (no trailing newline).
    """
    groups = cap_cat.get("groups", [])
    total_ucs = sum(g.get("uc_count", len(g.get("ucs", []))) for g in groups)
    n_groups = len(groups)

    lines = [
        f"### Capability Catalog ({n_groups} groups, {total_ucs} use cases)",
        "",
    ]

    for group in groups:
        emoji = group.get("emoji", "")
        name = _na(group.get("name"))
        uc_count = group.get("uc_count", len(group.get("ucs", [])))
        description = group.get("description", "")

        prefix = f"{emoji} " if emoji else ""
        lines.append(f"#### {prefix}{name} ({uc_count} UCs)")
        lines.append("")

        if description:
            lines.append(f"_{description}_")
            lines.append("")

        ucs = group.get("ucs", [])
        if ucs:
            headers = ["UC-ID", "Name", "Short Description", "Triggers"]
            rows = []
            for uc in ucs:
                uc_id = _na(uc.get("uc_id"))
                uc_name = _na(uc.get("name"))
                short_desc = _na(uc.get("short_description"))
                triggers = uc.get("sample_triggers", [])
                triggers_str = ", ".join(str(t) for t in triggers) if triggers else "n/a"
                rows.append([uc_id, uc_name, short_desc, triggers_str])
            lines.append(_md_table(headers, rows))
            lines.append("")

    return lines


def render_section_1(crystal: dict) -> str:
    """Section 1: What This Skill Does + Capability Catalog + Quick Start.

    v5.2+: renders full capability_catalog (grouped UC tables).
    v5.1 fallback: renders a note that capability_catalog is unavailable.
    """
    hs = crystal.get("human_summary", {})
    tagline = _na(hs.get("what_i_can_do", {}).get("tagline"))

    lines = [
        "## 1. What This Skill Does",
        "",
        tagline,
        "",
    ]

    pin = crystal.get("post_install_notice")
    if not pin:
        # Degraded: no post_install_notice at all
        lines.append("_post_install_notice not found in crystal — Quick Start unavailable._")
        lines.append("")
        lines.append("**What I can do:**")
        use_cases = hs.get("what_i_can_do", {}).get("use_cases", [])
        for uc in use_cases:
            lines.append(f"- {uc}")
        return "\n".join(lines)

    msg_tpl = pin.get("message_template", {})
    positioning = msg_tpl.get("positioning", "")
    if positioning:
        lines.append(positioning)
        lines.append("")

    cap_cat = msg_tpl.get("capability_catalog")
    if cap_cat:
        # v5.2+ path: full capability catalog
        lines.extend(_render_capability_catalog(cap_cat))
    else:
        # v5.1 fallback
        lines.append(
            "_(crystal is pre-v5.2, capability catalog not available; "
            "see intent_router for raw UC list)_"
        )
        lines.append("")

    lines.append("### Quick Start")
    lines.append("")

    featured = msg_tpl.get("featured_entries", [])
    uc_count = len(crystal.get("intent_router", {}).get("uc_entries", []))
    for entry in featured:
        uc_id = _na(entry.get("uc_id"))
        prompt = _na(entry.get("beginner_prompt"))
        lines.append(f"- **{prompt}** → routes to `{uc_id}`")
    lines.append("")

    cta = msg_tpl.get("call_to_action", "")
    if cta:
        lines.append(cta)
        lines.append("")

    hint = msg_tpl.get("more_info_hint", "")
    if hint:
        rendered_hint = hint.replace("{uc_count}", str(uc_count))
        lines.append(rendered_hint)
    else:
        lines.append(f'Ask me "what else can you do?" to see all {uc_count} capabilities.')

    return "\n".join(lines)


def render_section_2(crystal: dict) -> str:
    """Section 2: Execution Protocol."""
    meta = crystal.get("meta", {})
    ep = meta.get("execution_protocol", {})

    install_trigger = _na(ep.get("install_trigger"))
    execute_trigger = _na(ep.get("execute_trigger"))
    on_execute = ep.get("on_execute", [])

    lines = [
        "## 2. Execution Protocol",
        "",
        f"**Install trigger**: {install_trigger}",
        "",
        f"**Execute trigger**: {execute_trigger}",
        "",
        "**On execute, the agent MUST**:",
        "",
    ]
    for i, step in enumerate(on_execute, start=1):
        lines.append(f"{i}. {step}")

    if not on_execute:
        lines.append("_on_execute steps not declared._")

    return "\n".join(lines)


def render_section_3(crystal: dict) -> str:
    """Section 3: Preconditions table."""
    pcs = crystal.get("preconditions", [])
    n = len(pcs)

    lines = [
        f"## 3. Preconditions ({n} checks)",
        "",
    ]

    if not pcs:
        lines.append("_No preconditions declared._")
        return "\n".join(lines)

    headers = ["ID", "Description", "Check", "On Fail", "Severity"]
    rows = []
    for pc in pcs:
        rows.append(
            [
                _na(pc.get("id")),
                _na(pc.get("description")),
                f"`{_na(pc.get('check_command'))}`",
                _na(pc.get("on_fail")),
                _na(pc.get("severity")),
            ]
        )

    lines.append(_md_table(headers, rows))
    return "\n".join(lines)


def render_section_4(crystal: dict) -> str:
    """Section 4: Evidence Quality Declaration."""
    eq = crystal.get("evidence_quality", {})
    declared = eq.get("declared", {})
    rules = eq.get("enforcement_rules", [])

    verify_ratio = _pct(declared.get("evidence_verify_ratio"))
    audit_fail_total = _na(declared.get("audit_fail_total"))

    lines = [
        "## 4. Evidence Quality Declaration",
        "",
        f"- verify_ratio: {verify_ratio}",
        f"- audit fail total: {audit_fail_total}",
        "",
        "**Active enforcement rules**:",
        "",
    ]

    for rule in rules:
        r_id = _na(rule.get("id"))
        trigger = _na(rule.get("trigger"))
        action = _na(rule.get("action"))
        violation_code = _na(rule.get("violation_code"))
        lines.append(
            f"- **{r_id}**: When `{trigger}` → MUST `{action}` (violation: `{violation_code}`)"
        )

    if not rules:
        lines.append("_No enforcement rules declared._")

    return "\n".join(lines)


def render_section_5(crystal: dict) -> str:
    """Section 5: Semantic Locks table."""
    slr = crystal.get("spec_lock_registry", {})
    locks = slr.get("semantic_locks", [])

    lines = [
        "## 5. Semantic Locks (Violation = Fatal)",
        "",
    ]

    if not locks:
        lines.append("_No semantic locks declared._")
        return "\n".join(lines)

    headers = ["SL-ID", "Locked Value", "Source BDs"]
    rows = []
    for lock in locks:
        sl_id = _na(lock.get("id"))
        locked_val = _na(lock.get("locked_value"))
        source_bds = lock.get("source_bd_ids", [])
        src_str = ", ".join(source_bds) if source_bds else "n/a"
        rows.append([sl_id, locked_val, src_str])

    lines.append(_md_table(headers, rows))
    return "\n".join(lines)


def render_section_6(crystal: dict) -> str:
    """Section 6: Output Validator Assertions."""
    ov = crystal.get("output_validator", {})
    assertions = ov.get("assertions", [])

    lines = [
        "## 6. Output Validator Assertions",
        "",
        "Each assertion has a business_meaning; purely structural checks are forbidden:",
        "",
    ]

    if not assertions:
        lines.append("_No output validator assertions declared._")
        return "\n".join(lines)

    for assertion in assertions:
        ov_id = _na(assertion.get("id"))
        predicate = _na(assertion.get("check_predicate"))
        meaning = _na(assertion.get("business_meaning"))
        source_ids = assertion.get("source_ids", [])

        lines.append(f"- **{ov_id}** — {predicate}")
        lines.append(f"  - Meaning: {meaning}")
        if source_ids:
            lines.append(f"  - Sources: {', '.join(source_ids)}")

    return "\n".join(lines)


def render_section_7(crystal: dict) -> str:
    """Section 7: Hard Gates table."""
    acceptance = crystal.get("acceptance", {})
    gates = acceptance.get("hard_gates", [])

    lines = [
        "## 7. Hard Gates (Acceptance)",
        "",
    ]

    if not gates:
        lines.append("_No hard gates declared._")
        return "\n".join(lines)

    headers = ["G-ID", "Check", "On Fail"]
    rows = []
    for gate in gates:
        rows.append(
            [
                _na(gate.get("id")),
                _na(gate.get("check")),
                _na(gate.get("on_fail")),
            ]
        )

    lines.append(_md_table(headers, rows))
    return "\n".join(lines)


def render_section_8(crystal: dict) -> str:
    """Section 8: Skill Crystallization."""
    sc = crystal.get("skill_crystallization", {})
    output_path_tpl = _na(sc.get("output_path_template"))
    captured = sc.get("captured_fields", [])
    captured_str = ", ".join(captured) if captured else "n/a"

    lines = [
        "## 8. Skill Crystallization",
        "",
        f"After all Hard Gates pass, agent MUST emit `.skill` to `{output_path_tpl}`. "
        f"Captured fields: {captured_str}.",
        "",
    ]

    action = sc.get("action")
    if action:
        lines.append(f"**Action**: {action}")

    violation_signal = sc.get("violation_signal")
    if violation_signal:
        lines.append(f"\n**Violation signal**: {violation_signal}")

    return "\n".join(lines)


def render_section_9(crystal: dict) -> str:
    """Section 9: Capability Catalog grouped by data_domain."""
    uc_entries = crystal.get("intent_router", {}).get("uc_entries", [])
    uc_count = len(uc_entries)

    lines = [
        f"## 9. Capability Catalog ({uc_count} use cases)",
        "",
    ]

    if not uc_entries:
        lines.append("_No use cases declared._")
        return "\n".join(lines)

    # Group by data_domain (preserve insertion order)
    from collections import OrderedDict

    groups: dict[str, list[dict]] = OrderedDict()
    for uc in uc_entries:
        domain = uc.get("data_domain", "other")
        groups.setdefault(domain, []).append(uc)

    for domain, ucs in groups.items():
        lines.append(f"### {domain}")
        lines.append("")
        headers = ["UC-ID", "Name", "Trigger Keywords"]
        rows = []
        for uc in ucs:
            uc_id = _na(uc.get("uc_id"))
            name = _na(uc.get("name"))
            terms = uc.get("positive_terms", [])
            keywords = ", ".join(terms[:5]) if terms else "n/a"
            if len(terms) > 5:
                keywords += ", …"
            rows.append([uc_id, name, keywords])
        lines.append(_md_table(headers, rows))
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Top-level assembler
# ---------------------------------------------------------------------------


def render_skill_md(crystal: dict, crystal_path: Path) -> tuple[str, list[str]]:
    """
    Render the full SKILL.md content.

    Returns:
        (content, warnings)  where warnings is a list of degradation notices.
    """
    meta = crystal.get("meta", {})
    crystal_id = _na(meta.get("id"))

    warnings: list[str] = []

    # Check for v5.1 required sections
    if "post_install_notice" not in crystal:
        warnings.append(
            "post_install_notice is missing — this crystal predates v5.1. "
            "Section 1 Quick Start will be degraded."
        )
    if "human_summary" not in crystal:
        warnings.append("human_summary is missing — tagline and use_cases unavailable.")

    # Derive skill_name from human_summary tagline or fallback to crystal_id
    hs = crystal.get("human_summary", {})
    tagline = hs.get("what_i_can_do", {}).get("tagline", "")
    if tagline:
        first_sentence = tagline.split(".")[0].strip()
        skill_name = first_sentence if first_sentence else crystal_id
    else:
        skill_name = crystal_id

    # Header block
    header_lines = [
        f"# {skill_name}",
        "",
        f"> **Authoritative reference**: `seed.yaml` ({crystal_id}) — this file is a derived "
        "summary and MUST NOT be relied upon for behavioral decisions. Always re-read seed.yaml.",
        "",
    ]

    # Detect v5.2: has capability_catalog inside post_install_notice.message_template
    pin = crystal.get("post_install_notice", {})
    has_capability_catalog = "capability_catalog" in pin.get("message_template", {})

    sections = [
        render_section_1(crystal),
        render_section_2(crystal),
        render_section_3(crystal),
        render_section_4(crystal),
        render_section_5(crystal),
        render_section_6(crystal),
        render_section_7(crystal),
        render_section_8(crystal),
    ]

    # Section 9 (intent_router raw UC list) is only included for pre-v5.2 crystals.
    # v5.2+ crystals already have the authoritative grouping in Section 1.
    if not has_capability_catalog:
        sections.append(render_section_9(crystal))

    footer = (
        f"\n---\n"
        f"*Generated from {crystal_id} by crystal_skill_readme_emitter.py. "
        "Regenerate whenever seed.yaml changes.*\n"
    )

    content = "\n".join(header_lines) + "\n" + "\n\n".join(sections) + footer
    return content, warnings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()

    crystal_path = Path(args.crystal)
    output_path = Path(args.output)

    # Load crystal
    crystal = load_crystal(crystal_path)

    # Output guard
    if output_path.exists() and not args.overwrite:
        print(
            f"ERROR: Output file already exists: {output_path}\n"
            "Use --overwrite to force overwrite.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Render
    content, warnings = render_skill_md(crystal, crystal_path)

    # Print warnings
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    size_bytes = output_path.stat().st_size
    crystal_id = crystal.get("meta", {}).get("id", "unknown")

    print(f"SKILL.md written: {output_path}")
    print(f"  Crystal: {crystal_id}")
    print(f"  Size: {size_bytes} bytes")

    if warnings:
        # Missing post_install_notice = exit 1 (degraded but partial)
        missing_pin = any("post_install_notice" in w for w in warnings)
        if missing_pin:
            sys.exit(1)


if __name__ == "__main__":
    main()
