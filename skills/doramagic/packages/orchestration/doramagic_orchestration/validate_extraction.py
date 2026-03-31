#!/usr/bin/env python3
"""
Soul Extractor v0.7: Stage 3.5 — Hard Validation
Validates extracted cards for format compliance, evidence traceability,
and community signal utilization.

Usage:
    python3 validate_extraction.py --output-dir <output_dir>

Exit codes:
    0 = all hard checks pass
    1 = hard failures found (blocks Stage 4)
"""

import argparse
import json
import os
import re
import sys

# --- Config ---

REQUIRED_DR_FIELDS = [
    "card_type",
    "card_id",
    "repo",
    "type",
    "title",
    "severity",
    "rule",
    "do",
    "dont",
    "confidence",
    "sources",
]
REQUIRED_CC_FIELDS = ["card_type", "card_id", "repo", "title"]
REQUIRED_WF_FIELDS = ["card_type", "card_id", "repo", "title"]

VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
VALID_CARD_TYPES = {"decision_rule_card", "concept_card", "workflow_card"}

MIN_CODE_RULES = 5
MIN_COMMUNITY_RULES = 3


# --- YAML frontmatter parser (minimal, no dependency) ---


def parse_frontmatter(text):
    """Parse YAML frontmatter between --- markers. Returns (dict, body)."""
    if not text.startswith("---"):
        return {}, text

    end = text.find("---", 3)
    if end == -1:
        return {}, text

    yaml_block = text[3:end].strip()
    body = text[end + 3 :].strip()
    meta = {}

    current_key = None
    current_value_lines = []

    for line in yaml_block.split("\n"):
        # Handle list items under a key
        stripped = line.strip()
        if stripped.startswith("- "):
            if current_key:
                if current_key not in meta:
                    meta[current_key] = []
                item = stripped[2:].strip().strip('"').strip("'")
                if isinstance(meta[current_key], list):
                    meta[current_key].append(item)
                else:
                    meta[current_key] = [meta[current_key], item]
            continue

        # Handle multiline block scalar (|)
        if (
            current_key
            and (line.startswith("  ") or line.startswith("\t"))
            and not re.match(r"^[a-z_]+:", line)
        ):
            current_value_lines.append(line.strip())
            continue

        # Flush previous multiline value
        if current_key and current_value_lines:
            meta[current_key] = "\n".join(current_value_lines)
            current_value_lines = []

        # New key:value pair
        match = re.match(r"^([a-z_]+):\s*(.*)", line)
        if match:
            current_key = match.group(1)
            value = match.group(2).strip()
            if value == "|":
                current_value_lines = []
            elif value:
                # Remove quotes
                value = value.strip('"').strip("'")
                # Try numeric
                try:
                    value = float(value)
                    if value == int(value):
                        value = int(value)
                except (ValueError, TypeError):
                    pass
                meta[current_key] = value
            else:
                meta[current_key] = []

    # Flush last key
    if current_key and current_value_lines:
        meta[current_key] = "\n".join(current_value_lines)

    return meta, body


# --- Validators ---


def check_required_fields(meta, required, card_path):
    """Check that all required fields are present and non-empty."""
    errors = []
    for field in required:
        if field not in meta or meta[field] is None or meta[field] == "":
            errors.append(f"Missing required field: {field}")
        elif field == "sources" and not meta[field]:
            errors.append("Empty sources list")
    return errors


def check_severity(meta):
    """Check severity is a valid enum value."""
    sev = str(meta.get("severity", "")).upper()
    if sev not in VALID_SEVERITIES:
        return [f"Invalid severity '{meta.get('severity')}', must be one of {VALID_SEVERITIES}"]
    return []


def check_card_type(meta):
    """Check card_type is valid."""
    ct = meta.get("card_type", "")
    if ct not in VALID_CARD_TYPES:
        return [f"Invalid card_type '{ct}', must be one of {VALID_CARD_TYPES}"]
    return []


def check_confidence(meta):
    """Check confidence is a number between 0 and 1."""
    conf = meta.get("confidence")
    if conf is None:
        return []  # Optional for non-DR cards
    try:
        val = float(conf)
        if not 0 <= val <= 1:
            return [f"confidence {val} out of range [0, 1]"]
    except (ValueError, TypeError):
        return [f"confidence '{conf}' is not a number"]
    return []


def check_body_sections(body, card_type):
    """Check that body has expected sections."""
    warnings = []
    if card_type == "decision_rule_card":
        if "## 真实场景" not in body and "## Real" not in body:
            warnings.append("Missing '## 真实场景' section")
        if "## 影响范围" not in body and "## Impact" not in body:
            warnings.append("Missing '## 影响范围' section")
    elif card_type == "concept_card":
        if "## Identity" not in body and "## 身份" not in body:
            warnings.append("Missing '## Identity' section")
        if "## Evidence" not in body and "## 证据" not in body:
            warnings.append("Missing '## Evidence' section")
    return warnings


def check_rule_has_condition(meta):
    """Check that rule field contains IF/THEN or conditional language."""
    rule = str(meta.get("rule", ""))
    condition_patterns = [
        r"\bif\b",
        r"\bwhen\b",
        r"\bthen\b",
        r"\bunless\b",
        r"\bbefore\b",
        r"\bafter\b",
        r"\bmust\b",
        r"\bnever\b",
    ]
    has_condition = any(re.search(p, rule, re.IGNORECASE) for p in condition_patterns)
    if not has_condition:
        return ["Rule field lacks conditional language (IF/THEN/WHEN/MUST/NEVER)"]
    return []


def check_critical_has_code_example(meta):
    """Check that CRITICAL/HIGH cards have code examples in do list."""
    sev = str(meta.get("severity", "")).upper()
    if sev not in ("CRITICAL", "HIGH"):
        return []
    do_list = meta.get("do", [])
    do_text = " ".join(str(d) for d in do_list) if isinstance(do_list, list) else str(do_list)
    if "`" not in do_text and "code" not in do_text.lower():
        return ["CRITICAL/HIGH card lacks code example in do list"]
    return []


def check_community_has_issue_ref(meta):
    """Check that community gotcha cards reference specific Issue numbers."""
    card_id = str(meta.get("card_id", ""))
    if not re.match(r"DR-1\d{2}", card_id):
        return []
    sources = meta.get("sources", [])
    sources_text = " ".join(str(s) for s in sources)
    if not re.search(r"#\d+|Issue\s*\d+", sources_text, re.IGNORECASE):
        return ["Community gotcha card lacks specific Issue # reference"]
    return []


def check_community_source_refs(meta, community_signals):
    """Check that DR-100+ cards reference real community signals."""
    card_id = str(meta.get("card_id", ""))
    if not re.match(r"DR-1\d{2}", card_id):
        return []

    sources = meta.get("sources", [])
    if not sources:
        return ["Community gotcha card has no sources"]

    errors = []
    for src in sources:
        src_str = str(src)
        # Check for Issue references
        issue_match = re.search(r"Issue\s*#(\d+)", src_str, re.IGNORECASE)
        if issue_match:
            issue_num = issue_match.group(1)
            if community_signals and f"#{issue_num}" not in community_signals:
                errors.append(f"Issue #{issue_num} not found in community_signals.md")
        # Check for CHANGELOG references
        changelog_match = re.search(r"CHANGELOG|changelog|版本", src_str, re.IGNORECASE)
        if changelog_match and community_signals:
            # Just check if there's any tier 1 content
            pass  # CHANGELOG refs are harder to validate precisely
    return errors


def check_commands_in_facts(meta, body, repo_facts):
    """Check that commands/skill names mentioned in card body exist in repo_facts."""
    if repo_facts is None:
        return []  # No facts available, skip check

    known_commands = set(repo_facts.get("commands", []))
    known_skills = set(repo_facts.get("skills", [])) | set(repo_facts.get("entrypoints", []))
    all_known = known_commands | known_skills

    if not all_known:
        return []  # Empty whitelist, skip

    errors = []
    # Find backtick-quoted tokens that look like CLI commands or slash commands
    # e.g. `/plugin marketplace add` or `openclaw agent`
    for m in re.finditer(r"`(/[\w\s]+|[\w][\w-]+ [\w-]+)`", body):
        token = m.group(1).strip()
        first_word = token.split()[0].lstrip("/")
        # Only flag if it looks like a command (not a file path)
        if "/" not in token and "." not in token:
            if first_word not in all_known and len(first_word) > 2:
                errors.append(f"Command/skill '{token}' not found in repo_facts.json whitelist")
    return errors


def check_code_source_refs(meta, repo_file_index):
    """Check that code source refs point to files that exist in the repo."""
    card_id = str(meta.get("card_id", ""))
    # Only check code rules (DR-001~099)
    if re.match(r"DR-1\d{2}", card_id):
        return []  # Community cards use issue refs, not file:line

    sources = meta.get("sources", [])
    warnings = []
    for src in sources:
        src_str = str(src)
        # Look for file:line patterns
        file_match = re.match(r'^"?([^:]+\.\w+)(?::.*)?', src_str)
        if file_match and repo_file_index:
            file_ref = file_match.group(1).strip('"')
            # Check if any indexed file ends with this reference
            found = any(f.endswith(file_ref) or file_ref in f for f in repo_file_index)
            if not found:
                warnings.append(f"Source file ref '{file_ref}' not found in repo")
    return warnings


# --- Main validation ---


def load_community_signals(output_dir):
    """Load community_signals.md content for cross-referencing."""
    path = os.path.join(output_dir, "artifacts", "community_signals.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return None


def load_repo_facts(output_dir):
    """Load repo_facts.json for claim verification."""
    path = os.path.join(output_dir, "artifacts", "repo_facts.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def build_repo_file_index(output_dir):
    """Build a list of files in the repo for source ref checking."""
    repo_dir = os.path.join(output_dir, "artifacts", "_repo")
    if not os.path.isdir(repo_dir):
        return None
    index = []
    for root, dirs, files in os.walk(repo_dir):
        # Skip hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), repo_dir)
            index.append(rel)
    return index


def validate_all(output_dir):
    """Run all validations and produce report."""
    soul_dir = os.path.join(output_dir, "soul")
    os.makedirs(soul_dir, exist_ok=True)
    cards_dir = os.path.join(soul_dir, "cards")

    # Load cross-reference data
    community_signals = load_community_signals(output_dir)
    repo_file_index = build_repo_file_index(output_dir)
    repo_facts = load_repo_facts(output_dir)

    report = {
        "output_dir": output_dir,
        "cards": [],
        "summary": {},
    }

    # Collect all card files
    card_files = []
    for subdir in ["concepts", "workflows", "rules"]:
        dirpath = os.path.join(cards_dir, subdir)
        if os.path.isdir(dirpath):
            for f in sorted(os.listdir(dirpath)):
                if f.endswith(".md"):
                    card_files.append(os.path.join(dirpath, f))

    # Check essence file exists
    essence_path = os.path.join(soul_dir, "00-soul.md")
    if not os.path.exists(essence_path):
        report["cards"].append(
            {
                "file": "00-project-essence.md",
                "errors": ["Essence file missing"],
                "warnings": [],
                "pass": False,
            }
        )

    # Validate each card
    seen_ids = set()
    code_rule_count = 0
    community_rule_count = 0

    for card_path in card_files:
        with open(card_path, encoding="utf-8") as f:
            text = f.read()

        meta, body = parse_frontmatter(text)
        card_id = str(meta.get("card_id", os.path.basename(card_path)))
        card_type = meta.get("card_type", "unknown")

        errors = []
        warnings = []

        # Determine required fields based on card type
        if card_type == "decision_rule_card":
            errors.extend(check_required_fields(meta, REQUIRED_DR_FIELDS, card_path))
        elif card_type == "concept_card":
            errors.extend(check_required_fields(meta, REQUIRED_CC_FIELDS, card_path))
        elif card_type == "workflow_card":
            errors.extend(check_required_fields(meta, REQUIRED_WF_FIELDS, card_path))
        else:
            errors.extend(check_card_type(meta))

        # Severity check (for DR cards)
        if card_type == "decision_rule_card":
            errors.extend(check_severity(meta))

        # Confidence check
        warnings.extend(check_confidence(meta))

        # ID uniqueness
        if card_id in seen_ids:
            errors.append(f"Duplicate card_id: {card_id}")
        seen_ids.add(card_id)

        # Body section checks
        warnings.extend(check_body_sections(body, card_type))

        # Source ref checks
        if card_type == "decision_rule_card":
            errors.extend(check_community_source_refs(meta, community_signals))
            warnings.extend(check_code_source_refs(meta, repo_file_index))

        # Content quality checks (v0.9 new)
        if card_type == "decision_rule_card":
            errors.extend(check_rule_has_condition(meta))
            errors.extend(check_critical_has_code_example(meta))
            errors.extend(check_community_has_issue_ref(meta))

        # Fact-checking gate (v0.9 patch)
        if card_type == "decision_rule_card" and repo_facts:
            errors.extend(check_commands_in_facts(meta, body, repo_facts))

        # Count rule types
        if re.match(r"DR-0\d{2}", card_id):
            code_rule_count += 1
        elif re.match(r"DR-1\d{2}", card_id):
            community_rule_count += 1

        report["cards"].append(
            {
                "file": os.path.basename(card_path),
                "card_id": card_id,
                "card_type": card_type,
                "errors": errors,
                "warnings": warnings,
                "pass": len(errors) == 0,
            }
        )

    # Count checks
    total_cards = len(report["cards"])
    pass_cards = sum(1 for c in report["cards"] if c["pass"])
    total_errors = sum(len(c["errors"]) for c in report["cards"])
    total_warnings = sum(len(c["warnings"]) for c in report["cards"])

    # Quantity checks
    quantity_errors = []
    if code_rule_count < MIN_CODE_RULES:
        quantity_errors.append(
            f"Only {code_rule_count} code rules (DR-00x), minimum {MIN_CODE_RULES}"
        )
    if community_rule_count < MIN_COMMUNITY_RULES:
        quantity_errors.append(
            f"Only {community_rule_count} community rules (DR-10x), minimum {MIN_COMMUNITY_RULES}"
        )

    # Community signal utilization
    community_util = 0.0
    if community_signals:
        sig_count = len(re.findall(r"### SIG-\d+", community_signals))
        if sig_count > 0:
            community_util = community_rule_count / sig_count

    # Compute metrics
    format_compliance = pass_cards / total_cards if total_cards > 0 else 0
    traceability = 1.0  # Will be updated if source errors found
    source_errors = sum(
        1
        for c in report["cards"]
        for e in c["errors"]
        if "source" in e.lower() or "issue" in e.lower()
    )
    total_sources = sum(
        len(meta.get("sources", []))
        for card_path_item in card_files
        for meta in [parse_frontmatter(open(card_path_item, encoding="utf-8").read())[0]]
    )
    if total_sources > 0:
        traceability = 1.0 - (source_errors / total_sources)

    report["summary"] = {
        "total_cards": total_cards,
        "pass_cards": pass_cards,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "code_rules": code_rule_count,
        "community_rules": community_rule_count,
        "quantity_errors": quantity_errors,
        "metrics": {
            "format_compliance_rate": round(format_compliance, 3),
            "traceability_rate": round(traceability, 3),
            "community_utilization": round(community_util, 3),
        },
        "hard_gate": {
            "format_compliance_pass": format_compliance >= 0.95,
            "traceability_pass": traceability >= 1.0,
            "min_code_rules_pass": code_rule_count >= MIN_CODE_RULES,
            "min_community_rules_pass": community_rule_count >= MIN_COMMUNITY_RULES,
        },
        "overall_pass": (total_errors == 0 and len(quantity_errors) == 0 and traceability >= 1.0),
    }

    return report


def write_report(report, output_dir):
    """Write validation report as JSON and human-readable summary."""
    soul_dir = os.path.join(output_dir, "soul")
    os.makedirs(soul_dir, exist_ok=True)

    # JSON report
    json_path = os.path.join(soul_dir, "validation_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Markdown summary
    md_path = os.path.join(soul_dir, "validation_summary.md")
    s = report["summary"]
    m = s["metrics"]
    g = s["hard_gate"]

    lines = [
        "# Validation Summary",
        "",
        f"## Overall: {'PASS' if s['overall_pass'] else 'BLOCKED'}",
        "",
        "## Metrics",
        "",
        "| Metric | Value | Gate | Status |",
        "|--------|-------|------|--------|",
        f"| Format Compliance | {m['format_compliance_rate']:.1%} | ≥ 95% | {'PASS' if g['format_compliance_pass'] else 'FAIL'} |",
        f"| Traceability | {m['traceability_rate']:.1%} | = 100% | {'PASS' if g['traceability_pass'] else 'FAIL'} |",
        f"| Community Utilization | {m['community_utilization']:.1%} | ≥ 30% | {'PASS' if m['community_utilization'] >= 0.30 else 'WARN'} |",
        f"| Code Rules (DR-00x) | {s['code_rules']} | ≥ {MIN_CODE_RULES} | {'PASS' if g['min_code_rules_pass'] else 'FAIL'} |",
        f"| Community Rules (DR-10x) | {s['community_rules']} | ≥ {MIN_COMMUNITY_RULES} | {'PASS' if g['min_community_rules_pass'] else 'FAIL'} |",
        "",
        f"## Card Details ({s['pass_cards']}/{s['total_cards']} pass)",
        "",
    ]

    for card in report["cards"]:
        status = "PASS" if card["pass"] else "FAIL"
        lines.append(f"### {card.get('card_id', card['file'])} — {status}")
        if card["errors"]:
            lines.append("**Errors:**")
            for e in card["errors"]:
                lines.append(f"- {e}")
        if card["warnings"]:
            lines.append("**Warnings:**")
            for w in card["warnings"]:
                lines.append(f"- {w}")
        if not card["errors"] and not card["warnings"]:
            lines.append("No issues.")
        lines.append("")

    if s["quantity_errors"]:
        lines.append("## Quantity Issues")
        for q in s["quantity_errors"]:
            lines.append(f"- {q}")
        lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # Structured feedback JSON for Stage 3.5 retry loop (v0.9 new)
    feedback_items = []
    for card in report["cards"]:
        if card["errors"]:
            feedback_items.append(
                {
                    "card_id": card.get("card_id", card["file"]),
                    "file": card["file"],
                    "errors": card["errors"],
                    "suggestion": "Fix the listed errors and rerun validation",
                }
            )
    if feedback_items:
        feedback_path = os.path.join(soul_dir, "structured_feedback.json")
        with open(feedback_path, "w", encoding="utf-8") as f:
            json.dump(feedback_items, f, indent=2, ensure_ascii=False)
        # Add reference to markdown summary
        with open(md_path, "a", encoding="utf-8") as f:
            f.write(
                "\n## Structured Feedback\n\nSee `structured_feedback.json` for retry instructions.\n"
            )

    return json_path, md_path


def main():
    parser = argparse.ArgumentParser(description="Soul Extractor: Validate extracted cards")
    parser.add_argument("--output-dir", required=True, help="Path to extraction output directory")
    args = parser.parse_args()

    output_dir = args.output_dir
    if not os.path.isdir(output_dir):
        print(f"ERROR: Output directory not found: {output_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"=== Stage 3.5: Validating extraction in {output_dir} ===")
    report = validate_all(output_dir)
    json_path, md_path = write_report(report, output_dir)

    s = report["summary"]
    m = s["metrics"]

    print("")
    print(f"Cards: {s['pass_cards']}/{s['total_cards']} pass")
    print(f"Errors: {s['total_errors']}, Warnings: {s['total_warnings']}")
    print(f"Code rules: {s['code_rules']}, Community rules: {s['community_rules']}")
    print(f"Format compliance: {m['format_compliance_rate']:.1%}")
    print(f"Traceability: {m['traceability_rate']:.1%}")
    print(f"Community utilization: {m['community_utilization']:.1%}")
    print("")
    print(f"Report: {json_path}")
    print(f"Summary: {md_path}")

    if s["overall_pass"]:
        print("\nRESULT: PASS — Ready for Stage 4 assembly")
        sys.exit(0)
    else:
        print("\nRESULT: BLOCKED — Fix errors before assembly")
        if s["quantity_errors"]:
            for q in s["quantity_errors"]:
                print(f"  - {q}")
        sys.exit(1)


if __name__ == "__main__":
    main()
