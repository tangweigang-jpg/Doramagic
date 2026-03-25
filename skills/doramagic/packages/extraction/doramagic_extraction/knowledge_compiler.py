#!/usr/bin/env python3
"""
Knowledge Compiler — Stage 4.5

Compiles extracted knowledge cards (CC-*, WF-*, DR-* markdown with YAML
frontmatter), 00-soul.md, and repo_facts.json into a formatted
compiled_knowledge.md.

Pure deterministic logic — zero LLM calls.

Usage:
    python3 knowledge_compiler.py --output-dir <output_dir>
    python3 knowledge_compiler.py --output-dir <output_dir> --budget 1800
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Token budget constants
# ---------------------------------------------------------------------------

DEFAULT_BUDGET = 1750  # target mid-point of 1500-2000 range

SECTION_RATIOS = {
    "critical_rules": 0.15,
    "concepts": 0.10,
    "workflows": 0.10,
    "feature_inventory": 0.10,
    "design_philosophy": 0.15,
    "mental_model": 0.05,
    "why_chains": 0.15,
    "traps": 0.15,
    "quick_reference": 0.05,
}


# ---------------------------------------------------------------------------
# YAML frontmatter parser (no external deps)
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Parse YAML frontmatter from a markdown file.

    Returns (meta_dict, body_text).  Handles scalar values, pipe-block
    strings, and list items.  Numeric strings are kept as strings to avoid
    ambiguity (confidence: 0.98 stays "0.98").

    Backward-compatible: files without frontmatter return ({}, text).
    """
    if not text.startswith("---"):
        return {}, text

    end = text.find("---", 3)
    if end == -1:
        return {}, text

    yaml_block = text[3:end].strip()
    body = text[end + 3:].strip()

    meta: dict = {}
    current_key: Optional[str] = None
    in_block_scalar = False
    block_lines: list[str] = []

    for line in yaml_block.split("\n"):
        # Detect list item under a known key
        stripped = line.strip()

        if in_block_scalar:
            # Continuation of a | block value
            if re.match(r'^[a-z_]+:\s*', line) and not line.startswith(" "):
                # New key — flush block
                meta[current_key] = "\n".join(block_lines).strip()  # type: ignore[index]
                block_lines = []
                in_block_scalar = False
                # Fall through to parse the new key below
            else:
                block_lines.append(line.rstrip())
                continue

        if stripped.startswith("- ") and current_key is not None:
            item = stripped[2:].strip().strip('"').strip("'")
            if not isinstance(meta.get(current_key), list):
                meta[current_key] = []
            meta[current_key].append(item)
            continue

        m = re.match(r'^([a-z_A-Z][a-zA-Z0-9_]*):\s*(.*)', line)
        if m:
            # Flush any pending block
            if in_block_scalar and current_key is not None:
                meta[current_key] = "\n".join(block_lines).strip()
                block_lines = []
                in_block_scalar = False

            current_key = m.group(1)
            raw_value = m.group(2).strip()

            if raw_value == "|":
                in_block_scalar = True
                block_lines = []
            elif raw_value == "":
                meta[current_key] = []
            else:
                # Strip surrounding quotes
                value: object = raw_value.strip('"').strip("'")
                meta[current_key] = value

    # Flush trailing block scalar
    if in_block_scalar and current_key is not None:
        meta[current_key] = "\n".join(block_lines).strip()

    return meta, body


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Estimate token count using characters/4 heuristic."""
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# File loaders
# ---------------------------------------------------------------------------

def load_text(path: str) -> Optional[str]:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return None


def load_json(path: str) -> Optional[dict]:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def load_cards(soul_dir: str) -> list[tuple[dict, str]]:
    """
    Load all CC-*, WF-*, DR-* cards from soul/cards/{concepts,workflows,rules}.

    Returns list of (meta, body) tuples, sorted by card_id within each
    subdirectory.
    """
    cards: list[tuple[dict, str]] = []
    cards_base = os.path.join(soul_dir, "cards")

    for subdir in ("concepts", "workflows", "rules"):
        dirpath = os.path.join(cards_base, subdir)
        if not os.path.isdir(dirpath):
            continue
        for fname in sorted(os.listdir(dirpath)):
            if not fname.endswith(".md"):
                continue
            text = load_text(os.path.join(dirpath, fname))
            if text:
                meta, body = parse_frontmatter(text)
                meta["_filename"] = fname
                meta["_subdir"] = subdir
                cards.append((meta, body))

    return cards


# ---------------------------------------------------------------------------
# Verdict / confidence filtering
# ---------------------------------------------------------------------------

def verdict_label(meta: dict) -> Optional[str]:
    """
    Return verdict string (upper-cased) or None if not present.
    Backward compatible: missing verdict field is treated as None (pass).
    """
    v = meta.get("verdict")
    if v is None:
        return None
    return str(v).upper()


def is_rejected(meta: dict) -> bool:
    return verdict_label(meta) == "REJECTED"


def is_weak(meta: dict) -> bool:
    return verdict_label(meta) == "WEAK"


def weak_prefix(meta: dict) -> str:
    return "[推测] " if is_weak(meta) else ""


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _version_note(meta: dict) -> str:
    """Produce ' (适用: >=2.0)' style annotation if applicable_versions set."""
    av = meta.get("applicable_versions")
    if av and str(av).strip():
        return f" (适用: {av})"
    return ""


def build_critical_rules(cards: list[tuple[dict, str]], budget: int) -> str:
    """
    Section 1: CRITICAL RULES

    Format: `[SEVERITY] title — rule_summary (version_note)`

    Sorted: CRITICAL first, then HIGH.  Within each severity,
    is_exception_path==true cards go after non-exception cards.
    REJECTED cards skipped; WEAK cards get [推测] prefix on the title.

    Budget trimming: if over budget, drop MEDIUM/LOW rows first (they
    shouldn't appear here anyway), then trim trailing rows.
    """
    lines: list[str] = [
        "## CRITICAL RULES",
        "",
        "从代码分析和社区经验提取的高风险规则，按严重度排序。",
        "",
    ]

    def sort_key(entry: tuple[dict, str]) -> tuple[int, int]:
        sev_order = {"CRITICAL": 0, "HIGH": 1}
        sev = str(entry[0].get("severity", "")).upper()
        exc = 1 if str(entry[0].get("is_exception_path", "false")).lower() == "true" else 0
        return (sev_order.get(sev, 99), exc)

    eligible = [
        (m, b) for m, b in cards
        if m.get("card_type") == "decision_rule_card"
        and str(m.get("severity", "")).upper() in ("CRITICAL", "HIGH")
        and not is_rejected(m)
    ]
    eligible.sort(key=sort_key)

    for meta, body in eligible:
        sev = str(meta.get("severity", "")).upper()
        title = str(meta.get("title", meta.get("_filename", "")))
        rule_raw = str(meta.get("rule", ""))
        rule_lines = [l.strip() for l in rule_raw.split("\n") if l.strip()]
        rule_summary = " ".join(rule_lines[:2])  # max two lines
        prefix = weak_prefix(meta)
        ver = _version_note(meta)
        lines.append(f"- **[{sev}]** {prefix}{title}{ver} — {rule_summary}")

    lines.append("")
    return "\n".join(lines)


def build_concepts(cards: list[tuple[dict, str]], budget: int) -> str:
    """
    Section 2: CONCEPTS

    Format: `**Name**: definition. Is: X. IsNot: Y.`
    Each concept is compressed to a single line.
    """
    lines: list[str] = ["## CONCEPTS", ""]

    for meta, body in cards:
        if meta.get("card_type") != "concept_card":
            continue
        if is_rejected(meta):
            continue
        prefix = weak_prefix(meta)
        title = str(meta.get("title", meta.get("_filename", "")))

        # Extract first sentence from Identity section as definition
        definition = _extract_section(body, "Identity")
        if not definition:
            definition = _first_sentence(body)

        # Extract IS / IS NOT
        is_val = _extract_table_col(body, "IS", col=0)
        isnot_val = _extract_table_col(body, "IS NOT", col=1)

        parts: list[str] = [f"**{prefix}{title}**"]
        if definition:
            parts.append(definition.strip(".") + ".")
        if is_val:
            parts.append(f"Is: {is_val}.")
        if isnot_val:
            parts.append(f"IsNot: {isnot_val}.")

        lines.append("- " + " ".join(parts))

    lines.append("")
    return "\n".join(lines)


def build_workflows(cards: list[tuple[dict, str]], budget: int) -> str:
    """
    Section 3: WORKFLOWS

    Format: `**Title**: Step 1 → Step 2 → Step 3` (one line per workflow).
    """
    lines: list[str] = ["## WORKFLOWS", ""]

    for meta, body in cards:
        if meta.get("card_type") != "workflow_card":
            continue
        if is_rejected(meta):
            continue
        prefix = weak_prefix(meta)
        title = str(meta.get("title", meta.get("_filename", "")))
        steps = _extract_steps(body)
        if steps:
            flow = " → ".join(steps[:5])  # cap at 5 steps for token budget
            lines.append(f"- **{prefix}{title}**: {flow}")
        else:
            lines.append(f"- **{prefix}{title}**")

    lines.append("")
    return "\n".join(lines)


def build_feature_inventory(repo_facts: Optional[dict]) -> str:
    """
    Section 4: FEATURE INVENTORY from repo_facts.json.
    """
    if not repo_facts:
        return ""

    lines: list[str] = ["## FEATURE INVENTORY", ""]
    skills = repo_facts.get("skills", [])
    commands = repo_facts.get("commands", [])
    config_keys = repo_facts.get("config_keys", [])

    if skills:
        lines.append("**Skills / Features:**")
        for s in skills:
            lines.append(f"- `{s}`")
        lines.append("")
    if commands:
        lines.append("**Commands:**")
        for c in commands[:20]:
            lines.append(f"- `{c}`")
        lines.append("")
    if config_keys:
        lines.append("**Config Keys:**")
        for k in config_keys[:15]:
            lines.append(f"- `{k}`")
        lines.append("")

    if not (skills or commands or config_keys):
        return ""

    return "\n".join(lines)


def build_design_philosophy(soul_content: str) -> str:
    """
    Section 5: DESIGN PHILOSOPHY — Q6 from 00-soul.md.
    """
    q6 = _extract_soul_section(soul_content, ["6.", "Q6", "设计哲学", "Design Philosophy"])
    if not q6:
        return ""

    lines: list[str] = ["## DESIGN PHILOSOPHY", "", q6.strip(), ""]
    return "\n".join(lines)


def build_mental_model(soul_content: str) -> str:
    """
    Section 6: MENTAL MODEL — Q7 from 00-soul.md.
    """
    q7 = _extract_soul_section(soul_content, ["7.", "Q7", "心智模型", "Mental Model"])
    if not q7:
        return ""

    lines: list[str] = ["## MENTAL MODEL", "", q7.strip(), ""]
    return "\n".join(lines)


def build_why_chains(cards: list[tuple[dict, str]], budget: int) -> str:
    """
    Section 7: WHY CHAINS — top-3 DR-* cards with the richest rationale.

    Rationale richness = len(rule_text) + len(body).  Higher = more content
    to explain the "why".  Only non-REJECTED DR cards are eligible.
    Format: narrative "为什么这样设计".
    """
    lines: list[str] = ["## WHY CHAINS", ""]

    candidates = [
        (m, b) for m, b in cards
        if m.get("card_type") == "decision_rule_card"
        and not is_rejected(m)
    ]

    def richness(entry: tuple[dict, str]) -> int:
        m, b = entry
        return len(str(m.get("rule", ""))) + len(b)

    top3 = sorted(candidates, key=richness, reverse=True)[:3]

    for meta, body in top3:
        prefix = weak_prefix(meta)
        title = str(meta.get("title", meta.get("_filename", "")))
        rule_raw = str(meta.get("rule", ""))
        # Extract 真实场景 section
        scenario = _extract_section(body, "真实场景")
        # Compose narrative
        lines.append(f"### {prefix}{title}")
        rule_lines = [l.strip() for l in rule_raw.split("\n") if l.strip()]
        if rule_lines:
            lines.append(f"**设计原因**: {' '.join(rule_lines)}")
        if scenario:
            lines.append(f"**典型场景**: {scenario.strip()}")
        sources = meta.get("sources", [])
        if isinstance(sources, list) and sources:
            lines.append(f"**来源**: {', '.join(str(s) for s in sources[:3])}")
        lines.append("")

    return "\n".join(lines)


def build_traps(cards: list[tuple[dict, str]], budget: int) -> str:
    """
    Section 8: TRAPS — DR-100+ community gotchas.

    Format: warning block with issue references.
    Sorted: non-exception first, exception_path last within same severity.
    """
    lines: list[str] = ["## TRAPS", "", "社区反复踩坑的模式，来自 Issues / CHANGELOG / 安全公告。", ""]

    def is_trap(meta: dict) -> bool:
        card_id = str(meta.get("card_id", ""))
        # DR-100 and above
        m = re.match(r"DR-(\d+)", card_id)
        if m:
            return int(m.group(1)) >= 100
        # Or COMMUNITY_GOTCHA type
        return str(meta.get("type", "")).upper() == "COMMUNITY_GOTCHA"

    def trap_sort_key(entry: tuple[dict, str]) -> tuple[int, int]:
        sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        sev = str(entry[0].get("severity", "")).upper()
        exc = 1 if str(entry[0].get("is_exception_path", "false")).lower() == "true" else 0
        return (sev_order.get(sev, 99), exc)

    traps = [
        (m, b) for m, b in cards
        if m.get("card_type") == "decision_rule_card"
        and is_trap(m)
        and not is_rejected(m)
    ]
    traps.sort(key=trap_sort_key)

    for meta, body in traps:
        prefix = weak_prefix(meta)
        title = str(meta.get("title", meta.get("_filename", "")))
        sev = str(meta.get("severity", "")).upper()
        sources = meta.get("sources", [])
        rule_raw = str(meta.get("rule", ""))
        rule_lines = [l.strip() for l in rule_raw.split("\n") if l.strip()]
        ver = _version_note(meta)

        source_str = ""
        if isinstance(sources, list) and sources:
            source_str = f" | 来源: {', '.join(str(s) for s in sources[:2])}"

        lines.append(f"- ⚠️ **[{sev}] {prefix}{title}**{ver}{source_str}")
        if rule_lines:
            lines.append(f"  {' '.join(rule_lines[:2])}")

    lines.append("")
    return "\n".join(lines)


def build_quick_reference(cards: list[tuple[dict, str]], full_budget: bool = True) -> str:
    """
    Section 9: QUICK REFERENCE — all DR-* as a table.

    When full_budget=False, only CRITICAL/HIGH rows are included.
    """
    lines: list[str] = [
        "## QUICK REFERENCE",
        "",
        "| 规则 | 严重度 |",
        "|------|--------|",
    ]

    severity_filter = None if full_budget else {"CRITICAL", "HIGH"}

    for meta, body in cards:
        if meta.get("card_type") != "decision_rule_card":
            continue
        if is_rejected(meta):
            continue
        sev = str(meta.get("severity", "-")).upper()
        if severity_filter and sev not in severity_filter:
            continue
        title = str(meta.get("title", meta.get("_filename", "")))
        prefix = weak_prefix(meta)
        lines.append(f"| {prefix}{title} | {sev} |")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers for content extraction
# ---------------------------------------------------------------------------

def _extract_section(body: str, heading: str) -> str:
    """
    Extract text under a markdown ## heading in the body.
    Returns the first non-empty paragraph (up to 300 chars).
    """
    pattern = re.compile(
        r'##\s+' + re.escape(heading) + r'\s*\n(.*?)(?=\n##|\Z)',
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(body)
    if not m:
        return ""
    content = m.group(1).strip()
    # Return first non-table, non-bullet paragraph
    for line in content.split("\n"):
        line = line.strip()
        if line and not line.startswith("|") and not line.startswith("-") and not line.startswith("#"):
            return line[:300]
    return content[:300]


def _first_sentence(text: str) -> str:
    """Return first non-empty, non-markdown line up to 200 chars."""
    for line in text.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("|") and not line.startswith("-"):
            return line[:200]
    return ""


def _extract_table_col(body: str, col_header: str, col: int) -> str:
    """
    Extract first data cell from a markdown table column.

    col_header: name to find in the header row.
    col: 0-indexed column index to extract from data rows.
    """
    for line in body.split("\n"):
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if col < len(cells):
            cell = cells[col]
            # Skip header and separator rows
            if col_header.lower() in cell.lower() or re.match(r'^[-:]+$', cell):
                continue
            if cell:
                return cell[:150]
    return ""


def _extract_steps(body: str) -> list[str]:
    """
    Extract numbered steps from a workflow body.
    Returns list of step descriptions (stripped).
    """
    steps: list[str] = []
    pattern = re.compile(r'^\d+\.\s+(.+)', re.MULTILINE)
    for m in pattern.finditer(body):
        step = m.group(1).strip()
        # Trim very long steps
        steps.append(step[:80])
    return steps


def _extract_soul_section(soul: str, markers: list[str]) -> str:
    """
    Extract a section from 00-soul.md by trying multiple possible headings.
    Returns the text content (up to ~400 chars).
    """
    for marker in markers:
        # Try ## heading
        pattern = re.compile(
            r'##\s+[^\n]*' + re.escape(marker) + r'[^\n]*\n(.*?)(?=\n##|\Z)',
            re.DOTALL | re.IGNORECASE,
        )
        m = pattern.search(soul)
        if m:
            return m.group(1).strip()[:600]
        # Try numbered item like "6. 设计哲学\n..."
        pattern2 = re.compile(
            r'(?:^|\n)' + re.escape(marker) + r'[^\n]*\n(.*?)(?=\n\d+\.|\n##|\Z)',
            re.DOTALL | re.IGNORECASE,
        )
        m2 = pattern2.search(soul)
        if m2:
            return m2.group(1).strip()[:600]
    return ""


# ---------------------------------------------------------------------------
# Token budget enforcement
# ---------------------------------------------------------------------------

def enforce_budget(sections: dict[str, str], budget: int) -> dict[str, str]:
    """
    If total tokens exceed budget, apply trimming in priority order:
    1. Drop MEDIUM/LOW rows from quick_reference (rebuild with only CRITICAL/HIGH).
       Note: critical_rules already only includes CRITICAL/HIGH.
    2. Trim QUICK REFERENCE entirely if still over.
    3. Trim WHY CHAINS to top-1 if still over.

    Philosophy / mental model / traps are NEVER trimmed (core value).
    Concepts / workflows reduced if necessary.

    This function receives pre-built sections and may replace them.
    """
    total = sum(estimate_tokens(v) for v in sections.values())
    if total <= budget:
        return sections

    # Step 1: quick_reference already built — rebuild without MEDIUM/LOW
    # We can't call build_quick_reference here without cards, so we parse
    # existing quick_reference to drop non-CRITICAL/HIGH rows.
    qr = sections.get("quick_reference", "")
    if qr:
        filtered_lines: list[str] = []
        for line in qr.split("\n"):
            # Keep header rows, separators, and CRITICAL/HIGH data rows
            if line.strip().startswith("| 规则") or line.strip().startswith("|---") or not line.strip().startswith("|"):
                filtered_lines.append(line)
            else:
                # Data row — check severity column (last |...|)
                parts = [c.strip() for c in line.split("|")]
                sev = parts[-1] if parts else ""
                if sev in ("CRITICAL", "HIGH"):
                    filtered_lines.append(line)
        sections["quick_reference"] = "\n".join(filtered_lines)

    total = sum(estimate_tokens(v) for v in sections.values())
    if total <= budget:
        return sections

    # Step 2: Drop quick_reference entirely
    sections["quick_reference"] = ""

    total = sum(estimate_tokens(v) for v in sections.values())
    if total <= budget:
        return sections

    # Step 3: Trim why_chains to only first entry
    wc = sections.get("why_chains", "")
    # Find second ### heading and truncate
    second_h3 = wc.find("###", wc.find("###") + 3) if wc.count("###") > 1 else -1
    if second_h3 != -1:
        sections["why_chains"] = wc[:second_h3].rstrip() + "\n"

    total = sum(estimate_tokens(v) for v in sections.values())
    if total <= budget:
        return sections

    # Step 4: Trim concepts to one line each (already one line — trim to first 5)
    concepts_lines = sections.get("concepts", "").split("\n")
    bullet_lines = [l for l in concepts_lines if l.startswith("- ")]
    if len(bullet_lines) > 5:
        non_bullet = [l for l in concepts_lines if not l.startswith("- ")]
        sections["concepts"] = "\n".join(non_bullet[:3] + bullet_lines[:5]) + "\n"

    return sections


# ---------------------------------------------------------------------------
# Main compiler
# ---------------------------------------------------------------------------

def compile_knowledge(output_dir: str, budget: int = DEFAULT_BUDGET) -> bool:
    """
    Main entry point.

    Reads from:
      <output_dir>/soul/cards/concepts/CC-*.md
      <output_dir>/soul/cards/workflows/WF-*.md
      <output_dir>/soul/cards/rules/DR-*.md
      <output_dir>/soul/00-soul.md
      <output_dir>/artifacts/repo_facts.json

    Writes to:
      <output_dir>/soul/compiled_knowledge.md
    """
    soul_dir = os.path.join(output_dir, "soul")
    artifacts_dir = os.path.join(output_dir, "artifacts")

    # Load inputs
    cards = load_cards(soul_dir)
    soul_content = load_text(os.path.join(soul_dir, "00-soul.md")) or ""
    repo_facts = load_json(os.path.join(artifacts_dir, "repo_facts.json"))

    if not cards and not soul_content:
        print("ERROR: No cards or soul content found.", file=sys.stderr)
        return False

    # Build all 9 sections (U-shaped order)
    sections: dict[str, str] = {}

    # 1 — CRITICAL RULES
    sections["critical_rules"] = build_critical_rules(cards, int(budget * SECTION_RATIOS["critical_rules"]))
    # 2 — CONCEPTS
    sections["concepts"] = build_concepts(cards, int(budget * SECTION_RATIOS["concepts"]))
    # 3 — WORKFLOWS
    sections["workflows"] = build_workflows(cards, int(budget * SECTION_RATIOS["workflows"]))
    # 4 — FEATURE INVENTORY
    sections["feature_inventory"] = build_feature_inventory(repo_facts)
    # 5 — DESIGN PHILOSOPHY
    sections["design_philosophy"] = build_design_philosophy(soul_content)
    # 6 — MENTAL MODEL
    sections["mental_model"] = build_mental_model(soul_content)
    # 7 — WHY CHAINS
    sections["why_chains"] = build_why_chains(cards, int(budget * SECTION_RATIOS["why_chains"]))
    # 8 — TRAPS
    sections["traps"] = build_traps(cards, int(budget * SECTION_RATIOS["traps"]))
    # 9 — QUICK REFERENCE
    sections["quick_reference"] = build_quick_reference(cards, full_budget=True)

    # Enforce token budget
    sections = enforce_budget(sections, budget)

    # Count statistics
    cc_count = sum(1 for m, _ in cards if str(m.get("card_id", "")).startswith("CC"))
    wf_count = sum(1 for m, _ in cards if str(m.get("card_id", "")).startswith("WF"))
    dr_count = sum(1 for m, _ in cards if str(m.get("card_id", "")).startswith("DR"))
    rejected_count = sum(1 for m, _ in cards if is_rejected(m))
    weak_count = sum(1 for m, _ in cards if is_weak(m))

    repo_name = repo_facts.get("repo_path", output_dir).rstrip("/").split("/")[-1] if repo_facts else os.path.basename(output_dir)

    # Compose header
    header = "\n".join([
        f"# {repo_name} — Compiled Knowledge",
        "<!-- Generated by Doramagic Knowledge Compiler (Stage 4.5) -->",
        f"<!-- Cards: {cc_count} concepts, {wf_count} workflows, {dr_count} rules -->",
        f"<!-- Filtered: {rejected_count} REJECTED, {weak_count} WEAK ([推测] annotated) -->",
        "<!-- Order: CRITICAL RULES → CONCEPTS → WORKFLOWS → FEATURE INVENTORY",
        "          → DESIGN PHILOSOPHY → MENTAL MODEL → WHY CHAINS → TRAPS → QUICK REFERENCE -->",
        "",
    ])

    # Assemble in U-shaped order
    ordered_keys = [
        "critical_rules",
        "concepts",
        "workflows",
        "feature_inventory",
        "design_philosophy",
        "mental_model",
        "why_chains",
        "traps",
        "quick_reference",
    ]

    body_parts = [header]
    for key in ordered_keys:
        content = sections.get(key, "")
        if content.strip():
            body_parts.append(content)

    final_content = "\n".join(body_parts)

    # Write output
    out_path = os.path.join(soul_dir, "compiled_knowledge.md")
    os.makedirs(soul_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(final_content)

    token_count = estimate_tokens(final_content)
    print(f"=== Knowledge Compiler Complete ===")
    print(f"output:  {out_path}")
    print(f"tokens:  ~{token_count} (budget: {budget})")
    print(f"cards:   CC={cc_count} WF={wf_count} DR={dr_count}")
    print(f"filtered: {rejected_count} REJECTED, {weak_count} WEAK annotated")

    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Doramagic Knowledge Compiler — Stage 4.5"
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Path to the extraction output directory",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=DEFAULT_BUDGET,
        help=f"Token budget (default: {DEFAULT_BUDGET})",
    )
    args = parser.parse_args()

    print(f"=== Knowledge Compiler: {os.path.basename(os.path.abspath(args.output_dir))} ===")
    success = compile_knowledge(args.output_dir, args.budget)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
