"""
Tests for Knowledge Compiler (Stage 4.5).

Uses a self-contained fixture directory built in-memory (tmp_path) so no
external files or LLM calls are needed.
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge_compiler import (
    DEFAULT_BUDGET,
    build_concepts,
    build_critical_rules,
    build_design_philosophy,
    build_feature_inventory,
    build_mental_model,
    build_quick_reference,
    build_traps,
    build_why_chains,
    build_workflows,
    compile_knowledge,
    enforce_budget,
    estimate_tokens,
    is_rejected,
    is_weak,
    parse_frontmatter,
)


# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def make_cc_card(tmp_path: Path, card_id: str, title: str, verdict: str = "") -> Path:
    verdict_line = f"verdict: {verdict}\n" if verdict else ""
    content = f"""\
---
card_type: concept_card
card_id: {card_id}
repo: test-repo
title: "{title}"
{verdict_line}---

## Identity
The {title} is the core domain concept.

## Is / Is Not

| IS | IS NOT |
|----|--------|
| A real thing | Not a fake thing |
"""
    p = tmp_path / "soul" / "cards" / "concepts" / f"{card_id}.md"
    _write(p, content)
    return p


def make_wf_card(tmp_path: Path, card_id: str, title: str, verdict: str = "") -> Path:
    verdict_line = f"verdict: {verdict}\n" if verdict else ""
    content = f"""\
---
card_type: workflow_card
card_id: {card_id}
repo: test-repo
title: "{title}"
{verdict_line}---

## Steps
1. Read user input
2. Process data
3. Persist result
4. Return response
"""
    p = tmp_path / "soul" / "cards" / "workflows" / f"{card_id}.md"
    _write(p, content)
    return p


def make_dr_card(
    tmp_path: Path,
    card_id: str,
    title: str,
    severity: str = "HIGH",
    verdict: str = "",
    is_community: bool = False,
    is_exception_path: bool = False,
    applicable_versions: str = "",
) -> Path:
    card_type = "COMMUNITY_GOTCHA" if is_community else "DEFAULT_BEHAVIOR"
    verdict_line = f"verdict: {verdict}\n" if verdict else ""
    exc_line = "is_exception_path: true\n" if is_exception_path else ""
    ver_line = f"applicable_versions: {applicable_versions}\n" if applicable_versions else ""
    content = f"""\
---
card_type: decision_rule_card
card_id: {card_id}
repo: test-repo
type: {card_type}
title: "{title}"
severity: {severity}
{verdict_line}{exc_line}{ver_line}rule: |
  If the condition is met, apply this rule carefully.
  The second line gives more detail.
do:
  - "Do the right thing"
  - "Check your assumptions"
dont:
  - "Don't ignore edge cases"
confidence: 0.85
sources:
  - "src/module.py line 42"
  - "GitHub Issue #123 (15 reactions)"
---

## 真实场景
A developer forgot about this rule and lost data permanently.
It took three days to diagnose.

## 影响范围
- 谁会遇到：all developers
- 什么时候：when the condition fires
- 多严重：{severity}
"""
    p = tmp_path / "soul" / "cards" / "rules" / f"{card_id}.md"
    _write(p, content)
    return p


def make_soul(tmp_path: Path) -> Path:
    content = """\
# test-repo — 灵魂

## 1. 解决什么问题？
Helps developers manage data efficiently.

## 2. 没有它会怎样？
Manual, error-prone processes dominate.

## 3. 核心承诺
Turn messy data into clean, reusable artifacts.

## 4. 兑现方式
Extract, transform, and store with minimal friction.

## 5. 一句话总结
The repo makes data management effortless.

## 6. 设计哲学
Favor simplicity over cleverness. Every abstraction must earn its place.
Prefer explicit over implicit. When in doubt, do less and document more.

## 7. 心智模型
Think of this system as a pipeline: raw input enters one end, clean
output exits the other. Each stage has a single responsibility.
"""
    p = tmp_path / "soul" / "00-soul.md"
    _write(p, content)
    return p


def make_repo_facts(tmp_path: Path) -> Path:
    facts = {
        "repo_path": "/some/path/test-repo",
        "commands": ["npm run build", "npm test", "npm run lint"],
        "skills": ["skill-a", "skill-b"],
        "config_keys": ["API_KEY", "DEBUG_MODE"],
    }
    p = tmp_path / "artifacts" / "repo_facts.json"
    _write(p, json.dumps(facts, indent=2))
    return p


# ---------------------------------------------------------------------------
# parse_frontmatter tests
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    def test_basic_scalar(self):
        text = "---\ncard_type: concept_card\ntitle: Hello World\n---\n\nbody text"
        meta, body = parse_frontmatter(text)
        assert meta["card_type"] == "concept_card"
        assert meta["title"] == "Hello World"
        assert "body text" in body

    def test_list_value(self):
        text = "---\nsources:\n  - item one\n  - item two\n---\nbody"
        meta, body = parse_frontmatter(text)
        assert meta["sources"] == ["item one", "item two"]

    def test_block_scalar(self):
        text = "---\nrule: |\n  If X, then Y.\n  More detail here.\ntitle: Test\n---\nbody"
        meta, body = parse_frontmatter(text)
        assert "If X, then Y." in meta["rule"]
        assert "More detail here." in meta["rule"]

    def test_no_frontmatter(self):
        text = "Just plain body text\nNo frontmatter here"
        meta, body = parse_frontmatter(text)
        assert meta == {}
        assert "plain body" in body

    def test_quoted_title(self):
        text = '---\ntitle: "Quoted Title with spaces"\n---\nbody'
        meta, body = parse_frontmatter(text)
        assert meta["title"] == "Quoted Title with spaces"

    def test_empty_value_becomes_list(self):
        text = "---\nsources:\n---\nbody"
        meta, body = parse_frontmatter(text)
        # Empty list or empty string — both acceptable
        assert "sources" in meta

    def test_verdict_field(self):
        text = "---\ncard_type: concept_card\nverdict: REJECTED\n---\nbody"
        meta, body = parse_frontmatter(text)
        assert meta["verdict"] == "REJECTED"

    def test_is_exception_path(self):
        text = "---\ncard_type: decision_rule_card\nis_exception_path: true\n---\nbody"
        meta, body = parse_frontmatter(text)
        assert meta["is_exception_path"] == "true"


# ---------------------------------------------------------------------------
# Verdict filtering tests
# ---------------------------------------------------------------------------

class TestVerdictFiltering:
    def test_rejected_excluded_from_critical_rules(self, tmp_path):
        make_dr_card(tmp_path, "DR-001", "Normal Rule", severity="CRITICAL")
        make_dr_card(tmp_path, "DR-002", "Rejected Rule", severity="CRITICAL", verdict="REJECTED")
        cards = _load_cards_from(tmp_path)
        result = build_critical_rules(cards, 500)
        assert "Normal Rule" in result
        assert "Rejected Rule" not in result

    def test_weak_annotated_with_tag(self, tmp_path):
        make_dr_card(tmp_path, "DR-001", "Weak Rule", severity="HIGH", verdict="WEAK")
        cards = _load_cards_from(tmp_path)
        result = build_critical_rules(cards, 500)
        assert "[推测]" in result
        assert "Weak Rule" in result

    def test_no_verdict_passes_through(self, tmp_path):
        make_dr_card(tmp_path, "DR-001", "No Verdict Rule", severity="HIGH")
        cards = _load_cards_from(tmp_path)
        result = build_critical_rules(cards, 500)
        assert "No Verdict Rule" in result
        assert "[推测]" not in result

    def test_rejected_concept_excluded(self, tmp_path):
        make_cc_card(tmp_path, "CC-001", "Good Concept")
        make_cc_card(tmp_path, "CC-002", "Bad Concept", verdict="REJECTED")
        cards = _load_cards_from(tmp_path)
        result = build_concepts(cards, 500)
        assert "Good Concept" in result
        assert "Bad Concept" not in result

    def test_weak_concept_annotated(self, tmp_path):
        make_cc_card(tmp_path, "CC-001", "Uncertain Concept", verdict="WEAK")
        cards = _load_cards_from(tmp_path)
        result = build_concepts(cards, 500)
        assert "[推测]" in result

    def test_rejected_workflow_excluded(self, tmp_path):
        make_wf_card(tmp_path, "WF-001", "Good Workflow")
        make_wf_card(tmp_path, "WF-002", "Bad Workflow", verdict="REJECTED")
        cards = _load_cards_from(tmp_path)
        result = build_workflows(cards, 500)
        assert "Good Workflow" in result
        assert "Bad Workflow" not in result


# ---------------------------------------------------------------------------
# Section format tests
# ---------------------------------------------------------------------------

class TestSectionFormats:
    def test_critical_rules_format(self, tmp_path):
        make_dr_card(tmp_path, "DR-001", "Use HTTPS always", severity="CRITICAL")
        cards = _load_cards_from(tmp_path)
        result = build_critical_rules(cards, 500)
        assert "## CRITICAL RULES" in result
        assert "[CRITICAL]" in result
        assert "Use HTTPS always" in result
        # Should contain rule summary
        assert "If the condition is met" in result

    def test_critical_before_high_ordering(self, tmp_path):
        make_dr_card(tmp_path, "DR-001", "High Rule", severity="HIGH")
        make_dr_card(tmp_path, "DR-002", "Critical Rule", severity="CRITICAL")
        cards = _load_cards_from(tmp_path)
        result = build_critical_rules(cards, 500)
        assert result.index("Critical Rule") < result.index("High Rule")

    def test_concepts_format(self, tmp_path):
        make_cc_card(tmp_path, "CC-001", "Core Domain")
        cards = _load_cards_from(tmp_path)
        result = build_concepts(cards, 500)
        assert "## CONCEPTS" in result
        assert "**Core Domain**" in result

    def test_workflows_arrow_format(self, tmp_path):
        make_wf_card(tmp_path, "WF-001", "Main Flow")
        cards = _load_cards_from(tmp_path)
        result = build_workflows(cards, 500)
        assert "## WORKFLOWS" in result
        assert "→" in result
        # Steps should be joined with arrows
        assert "Read user input" in result

    def test_feature_inventory_structure(self):
        facts = {
            "skills": ["skill-a", "skill-b"],
            "commands": ["cmd-x", "cmd-y"],
            "config_keys": ["KEY_A"],
        }
        result = build_feature_inventory(facts)
        assert "## FEATURE INVENTORY" in result
        assert "skill-a" in result
        assert "cmd-x" in result
        assert "KEY_A" in result

    def test_feature_inventory_empty(self):
        result = build_feature_inventory(None)
        assert result == ""

    def test_design_philosophy_extracted(self):
        soul = "## 6. 设计哲学\nFavor simplicity over cleverness.\n\n## 7. 心智模型\nThink pipeline.\n"
        result = build_design_philosophy(soul)
        assert "## DESIGN PHILOSOPHY" in result
        assert "simplicity" in result

    def test_mental_model_extracted(self):
        soul = "## 6. 设计哲学\nFavor simplicity.\n\n## 7. 心智模型\nThink pipeline.\n"
        result = build_mental_model(soul)
        assert "## MENTAL MODEL" in result
        assert "pipeline" in result

    def test_traps_warning_format(self, tmp_path):
        make_dr_card(tmp_path, "DR-101", "Community Gotcha", severity="HIGH", is_community=True)
        cards = _load_cards_from(tmp_path)
        result = build_traps(cards, 500)
        assert "## TRAPS" in result
        assert "⚠️" in result
        assert "Community Gotcha" in result

    def test_quick_reference_table_format(self, tmp_path):
        make_dr_card(tmp_path, "DR-001", "Rule Alpha", severity="CRITICAL")
        make_dr_card(tmp_path, "DR-002", "Rule Beta", severity="MEDIUM")
        cards = _load_cards_from(tmp_path)
        result = build_quick_reference(cards)
        assert "## QUICK REFERENCE" in result
        assert "| 规则 | 严重度 |" in result
        assert "Rule Alpha" in result
        assert "CRITICAL" in result
        assert "Rule Beta" in result

    def test_quick_reference_crit_only(self, tmp_path):
        make_dr_card(tmp_path, "DR-001", "Rule Alpha", severity="CRITICAL")
        make_dr_card(tmp_path, "DR-002", "Rule Beta", severity="MEDIUM")
        cards = _load_cards_from(tmp_path)
        result = build_quick_reference(cards, full_budget=False)
        assert "Rule Alpha" in result
        assert "Rule Beta" not in result


# ---------------------------------------------------------------------------
# Exception path ordering
# ---------------------------------------------------------------------------

class TestExceptionPathOrdering:
    def test_exception_after_normal_same_severity(self, tmp_path):
        make_dr_card(tmp_path, "DR-001", "Normal High", severity="HIGH", is_exception_path=False)
        make_dr_card(tmp_path, "DR-002", "Exception High", severity="HIGH", is_exception_path=True)
        cards = _load_cards_from(tmp_path)
        result = build_critical_rules(cards, 1000)
        assert result.index("Normal High") < result.index("Exception High")

    def test_exception_path_trap_ordering(self, tmp_path):
        make_dr_card(tmp_path, "DR-101", "Normal Trap", severity="HIGH", is_community=True)
        make_dr_card(tmp_path, "DR-102", "Exception Trap", severity="HIGH", is_community=True, is_exception_path=True)
        cards = _load_cards_from(tmp_path)
        result = build_traps(cards, 1000)
        assert result.index("Normal Trap") < result.index("Exception Trap")


# ---------------------------------------------------------------------------
# Applicable versions annotation
# ---------------------------------------------------------------------------

class TestVersionAnnotation:
    def test_version_note_in_critical_rules(self, tmp_path):
        make_dr_card(tmp_path, "DR-001", "Versioned Rule", severity="HIGH", applicable_versions=">=2.0")
        cards = _load_cards_from(tmp_path)
        result = build_critical_rules(cards, 500)
        assert "适用: >=2.0" in result

    def test_version_note_in_traps(self, tmp_path):
        make_dr_card(tmp_path, "DR-101", "Versioned Trap", severity="HIGH", is_community=True, applicable_versions="<3.0")
        cards = _load_cards_from(tmp_path)
        result = build_traps(cards, 500)
        assert "适用: <3.0" in result


# ---------------------------------------------------------------------------
# WHY CHAINS tests
# ---------------------------------------------------------------------------

class TestWhyChains:
    def test_top_3_selected(self, tmp_path):
        # Create 5 rules with different body lengths
        for i in range(1, 6):
            body_extra = "x" * (i * 50)  # rule i has more content than rule i-1
            make_dr_card(tmp_path, f"DR-00{i}", f"Rule {i}", severity="HIGH")
            # Append extra body content to enrich the file
            card_path = tmp_path / "soul" / "cards" / "rules" / f"DR-00{i}.md"
            existing = card_path.read_text(encoding="utf-8")
            card_path.write_text(existing + f"\n## Extra\n{body_extra}\n", encoding="utf-8")

        cards = _load_cards_from(tmp_path)
        result = build_why_chains(cards, 500)
        # Should contain at most 3 ### headings
        assert result.count("###") <= 3

    def test_why_chains_contains_narrative(self, tmp_path):
        make_dr_card(tmp_path, "DR-001", "Important Rule", severity="CRITICAL")
        cards = _load_cards_from(tmp_path)
        result = build_why_chains(cards, 500)
        assert "## WHY CHAINS" in result
        assert "Important Rule" in result
        assert "设计原因" in result


# ---------------------------------------------------------------------------
# Token budget enforcement
# ---------------------------------------------------------------------------

class TestTokenBudget:
    def test_estimate_tokens(self):
        text = "a" * 400
        assert estimate_tokens(text) == 100

    def test_within_budget_untouched(self):
        sections = {
            "critical_rules": "small content",
            "quick_reference": "also small",
        }
        result = enforce_budget(sections, 10000)
        assert result["quick_reference"] == "also small"

    def test_over_budget_drops_medium_low_from_qr(self):
        # Build a quick_reference with MEDIUM rows
        qr = "## QUICK REFERENCE\n\n| 规则 | 严重度 |\n|------|--------|\n| Rule A | CRITICAL |\n| Rule B | MEDIUM |\n| Rule C | HIGH |\n"
        sections = {
            "quick_reference": qr,
            "critical_rules": "x" * 400,   # ~100 tokens
            "concepts": "x" * 400,
            "workflows": "x" * 400,
            "feature_inventory": "x" * 400,
            "design_philosophy": "x" * 400,
            "mental_model": "x" * 400,
            "why_chains": "x" * 400,
            "traps": "x" * 400,
        }
        # Total ~900 tokens + qr. With budget=850 it should trim qr.
        result = enforce_budget(sections, 850)
        # Either qr is reduced or removed
        new_qr = result.get("quick_reference", "")
        assert "MEDIUM" not in new_qr or new_qr == ""

    def test_philosophy_never_trimmed(self):
        # Even with tiny budget, design_philosophy must survive
        sections = {
            "design_philosophy": "Very important philosophy text. " * 20,
            "quick_reference": "## QUICK REFERENCE\n\n| R | S |\n|---|---|\n| Rule A | MEDIUM |\n",
            "critical_rules": "",
            "concepts": "",
            "workflows": "",
            "feature_inventory": "",
            "mental_model": "",
            "why_chains": "### Title\n**设计原因**: reason 1\n### Title2\n**设计原因**: reason 2\n",
            "traps": "",
        }
        result = enforce_budget(sections, 50)  # Tiny budget
        # Philosophy should not be emptied
        assert result["design_philosophy"].strip() != ""
        # Traps should not be emptied
        assert result["traps"] == ""  # was already empty

    def test_why_chains_trimmed_to_one_when_very_over(self):
        # Force deep trimming
        sections = {
            "why_chains": "### Title1\n**设计原因**: reason\n\n### Title2\n**设计原因**: reason2\n\n### Title3\n**设计原因**: r3\n",
            "quick_reference": "",
            "critical_rules": "x" * 2000,
            "concepts": "x" * 2000,
            "workflows": "x" * 2000,
            "feature_inventory": "x" * 2000,
            "design_philosophy": "x" * 2000,
            "mental_model": "x" * 2000,
            "traps": "x" * 2000,
        }
        result = enforce_budget(sections, 100)
        # why_chains should only have one ### heading
        wc = result.get("why_chains", "")
        assert wc.count("###") <= 1


# ---------------------------------------------------------------------------
# Full integration test
# ---------------------------------------------------------------------------

class TestFullCompile:
    def test_compile_produces_output(self, tmp_path):
        make_cc_card(tmp_path, "CC-001", "Core Domain")
        make_cc_card(tmp_path, "CC-002", "Storage Pattern")
        make_wf_card(tmp_path, "WF-001", "Main Workflow")
        make_dr_card(tmp_path, "DR-001", "Critical Safety Rule", severity="CRITICAL")
        make_dr_card(tmp_path, "DR-002", "High Rule", severity="HIGH")
        make_dr_card(tmp_path, "DR-003", "Medium Rule", severity="MEDIUM")
        make_dr_card(tmp_path, "DR-101", "Community Trap", severity="HIGH", is_community=True)
        make_soul(tmp_path)
        make_repo_facts(tmp_path)

        result = compile_knowledge(str(tmp_path))
        assert result is True

        out_path = tmp_path / "soul" / "compiled_knowledge.md"
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")

        # Check all 9 sections are present
        assert "## CRITICAL RULES" in content
        assert "## CONCEPTS" in content
        assert "## WORKFLOWS" in content
        assert "## FEATURE INVENTORY" in content
        assert "## DESIGN PHILOSOPHY" in content
        assert "## MENTAL MODEL" in content
        assert "## WHY CHAINS" in content
        assert "## TRAPS" in content
        assert "## QUICK REFERENCE" in content

        # Check U-shaped order (critical first, quick ref last)
        assert content.index("## CRITICAL RULES") < content.index("## CONCEPTS")
        assert content.index("## TRAPS") < content.index("## QUICK REFERENCE")

    def test_compile_within_token_budget(self, tmp_path):
        make_cc_card(tmp_path, "CC-001", "Concept A")
        make_wf_card(tmp_path, "WF-001", "Flow A")
        make_dr_card(tmp_path, "DR-001", "Rule A", severity="HIGH")
        make_soul(tmp_path)
        make_repo_facts(tmp_path)

        compile_knowledge(str(tmp_path), budget=DEFAULT_BUDGET)
        out_path = tmp_path / "soul" / "compiled_knowledge.md"
        content = out_path.read_text(encoding="utf-8")
        tokens = estimate_tokens(content)
        assert tokens <= DEFAULT_BUDGET * 1.1  # Allow 10% slack

    def test_compile_rejected_cards_excluded(self, tmp_path):
        make_cc_card(tmp_path, "CC-001", "Good Concept")
        make_cc_card(tmp_path, "CC-002", "Rejected Concept", verdict="REJECTED")
        make_dr_card(tmp_path, "DR-001", "Good Rule", severity="HIGH")
        make_dr_card(tmp_path, "DR-002", "Rejected Rule", severity="CRITICAL", verdict="REJECTED")
        make_soul(tmp_path)

        compile_knowledge(str(tmp_path))
        out_path = tmp_path / "soul" / "compiled_knowledge.md"
        content = out_path.read_text(encoding="utf-8")

        assert "Good Concept" in content
        assert "Rejected Concept" not in content
        assert "Good Rule" in content
        assert "Rejected Rule" not in content

    def test_compile_weak_cards_annotated(self, tmp_path):
        make_dr_card(tmp_path, "DR-001", "Uncertain Rule", severity="HIGH", verdict="WEAK")
        make_soul(tmp_path)

        compile_knowledge(str(tmp_path))
        out_path = tmp_path / "soul" / "compiled_knowledge.md"
        content = out_path.read_text(encoding="utf-8")
        assert "[推测]" in content
        assert "Uncertain Rule" in content

    def test_compile_missing_soul(self, tmp_path):
        # No soul file, but has cards — should still succeed
        make_dr_card(tmp_path, "DR-001", "Some Rule", severity="HIGH")
        make_repo_facts(tmp_path)

        result = compile_knowledge(str(tmp_path))
        assert result is True
        out_path = tmp_path / "soul" / "compiled_knowledge.md"
        assert out_path.exists()

    def test_compile_no_cards_no_soul_fails(self, tmp_path):
        result = compile_knowledge(str(tmp_path))
        assert result is False

    def test_compile_header_metadata(self, tmp_path):
        make_cc_card(tmp_path, "CC-001", "Concept")
        make_wf_card(tmp_path, "WF-001", "Flow")
        make_dr_card(tmp_path, "DR-001", "Rule", severity="HIGH")
        make_soul(tmp_path)

        compile_knowledge(str(tmp_path))
        out_path = tmp_path / "soul" / "compiled_knowledge.md"
        content = out_path.read_text(encoding="utf-8")
        # Header comment should include card counts
        assert "concepts" in content
        assert "workflows" in content
        assert "rules" in content

    def test_compile_u_shaped_section_order(self, tmp_path):
        """Verify strict U-shaped ordering: dangerous→useful→deep→reference."""
        make_cc_card(tmp_path, "CC-001", "Concept")
        make_wf_card(tmp_path, "WF-001", "Flow")
        make_dr_card(tmp_path, "DR-001", "Rule", severity="HIGH")
        make_dr_card(tmp_path, "DR-101", "Trap", severity="HIGH", is_community=True)
        make_soul(tmp_path)
        make_repo_facts(tmp_path)

        compile_knowledge(str(tmp_path))
        out_path = tmp_path / "soul" / "compiled_knowledge.md"
        content = out_path.read_text(encoding="utf-8")

        # Build position list from content for present sections
        section_order = [
            "CRITICAL RULES",
            "CONCEPTS",
            "WORKFLOWS",
            "FEATURE INVENTORY",
            "DESIGN PHILOSOPHY",
            "MENTAL MODEL",
            "WHY CHAINS",
            "TRAPS",
            "QUICK REFERENCE",
        ]
        found = [s for s in section_order if f"## {s}" in content]
        positions_list = [content.index(f"## {s}") for s in found]
        # Verify positions are strictly increasing (U-shaped order preserved)
        for i in range(len(positions_list) - 1):
            assert positions_list[i] < positions_list[i + 1], (
                f"{found[i]} should appear before {found[i+1]}"
            )


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_cards_without_verdict_pass(self, tmp_path):
        """Cards without verdict field should be treated as normal (no filter)."""
        make_dr_card(tmp_path, "DR-001", "Legacy Rule", severity="HIGH")
        # Verify file has no verdict field
        card_path = tmp_path / "soul" / "cards" / "rules" / "DR-001.md"
        content = card_path.read_text(encoding="utf-8")
        assert "verdict" not in content

        cards = _load_cards_from(tmp_path)
        meta = cards[0][0]
        assert not is_rejected(meta)
        assert not is_weak(meta)

        result = build_critical_rules(cards, 500)
        assert "Legacy Rule" in result

    def test_concepts_without_verdict_pass(self, tmp_path):
        make_cc_card(tmp_path, "CC-001", "Old Style Concept")
        cards = _load_cards_from(tmp_path)
        result = build_concepts(cards, 500)
        assert "Old Style Concept" in result


# ---------------------------------------------------------------------------
# Helper: load cards from tmp_path using compiler's logic
# ---------------------------------------------------------------------------

def _load_cards_from(tmp_path: Path) -> list[tuple[dict, str]]:
    from knowledge_compiler import load_cards
    return load_cards(str(tmp_path / "soul"))
