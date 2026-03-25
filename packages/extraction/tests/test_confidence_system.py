"""
Tests for confidence_system.py

Run with:  pytest tests/test_confidence_system.py -v
"""

import sys
import os

# Allow running from the racer directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from confidence_system import (
    tag_single_ref,
    tag_evidence_refs,
    compute_verdict,
    process_card,
    run_evidence_tagging,
    inject_verdict_into_frontmatter,
    _path_contains_doc_keyword,
)


# ---------------------------------------------------------------------------
# tag_single_ref
# ---------------------------------------------------------------------------


class TestTagSingleRef:
    def test_file_line_always_code(self):
        assert tag_single_ref("file_line", "src/app.py") == "CODE"

    def test_file_line_empty_path_still_code(self):
        assert tag_single_ref("file_line", "") == "CODE"

    def test_community_ref_always_community(self):
        assert tag_single_ref("community_ref", "https://github.com/foo/bar/issues/1") == "COMMUNITY"

    def test_community_ref_empty_path(self):
        assert tag_single_ref("community_ref", "") == "COMMUNITY"

    def test_artifact_ref_readme_is_doc(self):
        assert tag_single_ref("artifact_ref", "README.md") == "DOC"

    def test_artifact_ref_readme_in_subpath(self):
        assert tag_single_ref("artifact_ref", "docs/README.md") == "DOC"

    def test_artifact_ref_doc_dir(self):
        assert tag_single_ref("artifact_ref", "doc/architecture.md") == "DOC"

    def test_artifact_ref_docs_dir(self):
        assert tag_single_ref("artifact_ref", "docs/guide.rst") == "DOC"

    def test_artifact_ref_contributing(self):
        assert tag_single_ref("artifact_ref", "CONTRIBUTING.md") == "DOC"

    def test_artifact_ref_guide_in_name(self):
        assert tag_single_ref("artifact_ref", "setup-guide.txt") == "DOC"

    def test_artifact_ref_code_file(self):
        assert tag_single_ref("artifact_ref", "src/main.py") == "CODE"

    def test_artifact_ref_config_file(self):
        assert tag_single_ref("artifact_ref", "config/settings.yaml") == "CODE"

    def test_unknown_kind_is_inference(self):
        assert tag_single_ref("unknown_kind", "some/path") == "INFERENCE"

    def test_empty_kind_is_inference(self):
        assert tag_single_ref("", "some/path") == "INFERENCE"

    def test_case_insensitive_kind(self):
        assert tag_single_ref("FILE_LINE", "src/foo.py") == "CODE"
        assert tag_single_ref("Community_Ref", "url") == "COMMUNITY"


class TestPathDocKeyword:
    def test_md_extension(self):
        assert _path_contains_doc_keyword("foo/bar.md") is True

    def test_rst_extension(self):
        assert _path_contains_doc_keyword("foo/bar.rst") is True

    def test_html_extension(self):
        assert _path_contains_doc_keyword("index.html") is True

    def test_py_extension(self):
        assert _path_contains_doc_keyword("src/app.py") is False

    def test_yaml_extension(self):
        assert _path_contains_doc_keyword("config.yaml") is False

    def test_readme_segment(self):
        assert _path_contains_doc_keyword("project/README") is True

    def test_wiki_segment(self):
        assert _path_contains_doc_keyword("wiki/page") is True

    def test_changelog_segment(self):
        assert _path_contains_doc_keyword("CHANGELOG") is True


# ---------------------------------------------------------------------------
# tag_evidence_refs
# ---------------------------------------------------------------------------


class TestTagEvidenceRefs:
    def test_empty_list_yields_inference(self):
        assert tag_evidence_refs([]) == ["INFERENCE"]

    def test_single_file_line(self):
        refs = [{"kind": "file_line", "path": "src/foo.py", "start_line": 10}]
        assert tag_evidence_refs(refs) == ["CODE"]

    def test_multiple_refs_mixed(self):
        refs = [
            {"kind": "file_line", "path": "src/app.py"},
            {"kind": "community_ref", "path": "https://github.com/issues/5"},
            {"kind": "artifact_ref", "path": "README.md"},
        ]
        result = tag_evidence_refs(refs)
        assert result == ["CODE", "COMMUNITY", "DOC"]

    def test_none_refs_yields_inference(self):
        assert tag_evidence_refs(None) == ["INFERENCE"]


# ---------------------------------------------------------------------------
# compute_verdict
# ---------------------------------------------------------------------------


class TestComputeVerdict:
    # Rule 1: CODE + DOC
    def test_code_and_doc(self):
        verdict, action = compute_verdict(["CODE", "DOC"])
        assert verdict == "SUPPORTED"
        assert action == "ALLOW_CORE"

    def test_code_and_doc_with_community(self):
        verdict, action = compute_verdict(["CODE", "DOC", "COMMUNITY"])
        assert verdict == "SUPPORTED"
        assert action == "ALLOW_CORE"

    # Rule 2: CODE + COMMUNITY
    def test_code_and_community(self):
        verdict, action = compute_verdict(["CODE", "COMMUNITY"])
        assert verdict == "SUPPORTED"
        assert action == "ALLOW_CORE"

    # Rule 3: DOC + COMMUNITY (no CODE)
    def test_doc_and_community(self):
        verdict, action = compute_verdict(["DOC", "COMMUNITY"])
        assert verdict == "SUPPORTED"
        assert action == "ALLOW_STORY"

    # Rule 4: CODE only
    def test_code_only(self):
        verdict, action = compute_verdict(["CODE"])
        assert verdict == "SUPPORTED"
        assert action == "ALLOW_CORE"

    def test_multiple_code_tags(self):
        verdict, action = compute_verdict(["CODE", "CODE", "CODE"])
        assert verdict == "SUPPORTED"
        assert action == "ALLOW_CORE"

    # Rule 5: COMMUNITY only
    def test_community_only(self):
        verdict, action = compute_verdict(["COMMUNITY"])
        assert verdict == "CONTESTED"
        assert action == "ALLOW_STORY"

    # Rule 6: INFERENCE + 1 corroboration
    def test_inference_plus_code(self):
        verdict, action = compute_verdict(["INFERENCE", "CODE"])
        assert verdict == "WEAK"
        assert action == "ALLOW_STORY"

    def test_inference_plus_community(self):
        verdict, action = compute_verdict(["INFERENCE", "COMMUNITY"])
        assert verdict == "WEAK"
        assert action == "ALLOW_STORY"

    def test_inference_plus_doc(self):
        verdict, action = compute_verdict(["INFERENCE", "DOC"])
        assert verdict == "WEAK"
        assert action == "ALLOW_STORY"

    # Rule 7: INFERENCE only
    def test_inference_only(self):
        verdict, action = compute_verdict(["INFERENCE"])
        assert verdict == "REJECTED"
        assert action == "QUARANTINE"

    def test_multiple_inference(self):
        verdict, action = compute_verdict(["INFERENCE", "INFERENCE"])
        assert verdict == "REJECTED"
        assert action == "QUARANTINE"

    # Rule 8: Contradiction (INFERENCE + 2+ corroborating tags)
    def test_contradiction_inference_code_community(self):
        verdict, action = compute_verdict(["INFERENCE", "CODE", "COMMUNITY"])
        assert verdict == "CONTESTED"
        assert action == "ALLOW_STORY"

    def test_contradiction_inference_code_doc(self):
        verdict, action = compute_verdict(["INFERENCE", "CODE", "DOC"])
        assert verdict == "CONTESTED"
        assert action == "ALLOW_STORY"

    # Edge cases
    def test_empty_tags_rejected(self):
        verdict, action = compute_verdict([])
        assert verdict == "REJECTED"
        assert action == "QUARANTINE"

    def test_doc_only(self):
        # DOC only — no CODE, no COMMUNITY: falls through all rules → REJECTED
        verdict, action = compute_verdict(["DOC"])
        assert verdict == "REJECTED"
        assert action == "QUARANTINE"


# ---------------------------------------------------------------------------
# process_card
# ---------------------------------------------------------------------------


class TestProcessCard:
    def test_card_with_code_refs(self):
        card = {
            "card_id": "DR-001",
            "evidence_refs": [
                {"kind": "file_line", "path": "src/main.py", "start_line": 42}
            ],
        }
        result = process_card(card)
        assert result["evidence_tags"] == ["CODE"]
        assert result["verdict"] == "SUPPORTED"
        assert result["policy_action"] == "ALLOW_CORE"

    def test_card_no_evidence_refs(self):
        card = {"card_id": "DR-002", "evidence_refs": []}
        result = process_card(card)
        assert result["verdict"] == "REJECTED"
        assert result["policy_action"] == "QUARANTINE"

    def test_card_missing_evidence_refs_key(self):
        card = {"card_id": "DR-003"}
        result = process_card(card)
        assert result["verdict"] == "REJECTED"

    def test_card_community_only(self):
        card = {
            "card_id": "DR-101",
            "evidence_refs": [
                {"kind": "community_ref", "path": "https://github.com/issues/42"}
            ],
        }
        result = process_card(card)
        assert result["verdict"] == "CONTESTED"
        assert result["policy_action"] == "ALLOW_STORY"

    def test_card_mutated_in_place(self):
        card = {"card_id": "X", "evidence_refs": [{"kind": "file_line", "path": "a.py"}]}
        original_id = id(card)
        result = process_card(card)
        assert id(result) == original_id  # same object


# ---------------------------------------------------------------------------
# run_evidence_tagging
# ---------------------------------------------------------------------------


class TestRunEvidenceTagging:
    def test_empty_list(self):
        result = run_evidence_tagging([])
        assert result == []

    def test_single_card(self):
        cards = [{"card_id": "C1", "evidence_refs": [{"kind": "file_line", "path": "x.py"}]}]
        result = run_evidence_tagging(cards)
        assert len(result) == 1
        assert result[0]["verdict"] == "SUPPORTED"

    def test_multiple_cards_all_tagged(self):
        cards = [
            {"card_id": "C1", "evidence_refs": [{"kind": "file_line", "path": "a.py"}]},
            {"card_id": "C2", "evidence_refs": []},
            {
                "card_id": "C3",
                "evidence_refs": [
                    {"kind": "artifact_ref", "path": "README.md"},
                    {"kind": "community_ref", "path": "url"},
                ],
            },
        ]
        result = run_evidence_tagging(cards)
        assert result[0]["verdict"] == "SUPPORTED"
        assert result[1]["verdict"] == "REJECTED"
        assert result[2]["verdict"] == "SUPPORTED"
        assert result[2]["policy_action"] == "ALLOW_STORY"

    def test_returns_same_list_object(self):
        cards = [{"card_id": "X", "evidence_refs": []}]
        original_id = id(cards)
        result = run_evidence_tagging(cards)
        assert id(result) == original_id


# ---------------------------------------------------------------------------
# inject_verdict_into_frontmatter
# ---------------------------------------------------------------------------


class TestInjectVerdictIntoFrontmatter:
    def _make_card(self, verdict="SUPPORTED", policy="ALLOW_CORE", tags=None):
        return {
            "verdict": verdict,
            "policy_action": policy,
            "evidence_tags": tags or ["CODE"],
        }

    def test_basic_injection(self):
        text = "---\ncard_id: DR-001\ntitle: Test\n---\n\n## Body"
        card = self._make_card()
        result = inject_verdict_into_frontmatter(text, card)
        assert "verdict: SUPPORTED" in result
        assert "policy_action: ALLOW_CORE" in result
        assert "evidence_tags: [CODE]" in result

    def test_body_preserved(self):
        text = "---\ncard_id: DR-001\n---\n\n## Body content here"
        card = self._make_card()
        result = inject_verdict_into_frontmatter(text, card)
        assert "## Body content here" in result

    def test_existing_verdict_replaced(self):
        text = "---\ncard_id: DR-001\nverdict: REJECTED\npolicy_action: QUARANTINE\n---\n"
        card = self._make_card(verdict="SUPPORTED", policy="ALLOW_CORE")
        result = inject_verdict_into_frontmatter(text, card)
        assert "verdict: SUPPORTED" in result
        assert "verdict: REJECTED" not in result

    def test_multiple_evidence_tags(self):
        text = "---\ncard_id: DR-001\n---\n"
        card = self._make_card(tags=["CODE", "COMMUNITY"])
        result = inject_verdict_into_frontmatter(text, card)
        assert "evidence_tags: [CODE, COMMUNITY]" in result

    def test_quarantine_card(self):
        text = "---\ncard_id: DR-INF\n---\n"
        card = self._make_card(verdict="REJECTED", policy="QUARANTINE", tags=["INFERENCE"])
        result = inject_verdict_into_frontmatter(text, card)
        assert "verdict: REJECTED" in result
        assert "policy_action: QUARANTINE" in result
