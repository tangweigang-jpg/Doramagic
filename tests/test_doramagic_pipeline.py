"""
Tests for doramagic.py pipeline — uses mocked LLM calls so no API key needed.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

# Add packages to path
ROOT = Path(__file__).parent.parent
for pkg in [
    ROOT / "packages" / "contracts",
    ROOT / "packages" / "cross_project",
    ROOT / "packages" / "platform_openclaw",
]:
    sys.path.insert(0, str(pkg))

import doramagic
from doramagic_contracts import (
    NeedProfile,
    SearchDirection,
    RepoRef,
    EvidenceRef,
    KnowledgeAtom,
    CommunitySignals,
    ProjectFingerprint,
    DiscoveryCandidate,
    CandidateQualitySignals,
    DiscoveryResult,
    SearchCoverageItem,
    ExtractedProjectSummary,
    CommunityKnowledge,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_need_profile(raw: str = "I want a recipe manager skill") -> NeedProfile:
    return NeedProfile(
        raw_input=raw,
        keywords=["recipe", "meal", "food", "cooking", "ingredients"],
        intent="Manage home recipes with ingredients",
        search_directions=[
            SearchDirection(direction="recipe management app", priority="high"),
            SearchDirection(direction="meal planner python", priority="medium"),
        ],
        constraints=["single-user", "local storage"],
        quality_expectations={},
    )


def make_repo_ref(repo_id: str = "cand-01", full_name: str = "user/recipe-app") -> RepoRef:
    return RepoRef(
        repo_id=repo_id,
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        default_branch="main",
        commit_sha="abc123",
        local_path="/tmp/repo",
    )


def make_fingerprint(repo_id: str = "cand-01", full_name: str = "user/recipe-app") -> ProjectFingerprint:
    repo = make_repo_ref(repo_id, full_name)
    return ProjectFingerprint(
        project=repo,
        code_fingerprint={"repo_name": "recipe-app", "language": "Python", "stars": 100},
        knowledge_atoms=[
            KnowledgeAtom(
                atom_id=f"{repo_id}-atom-001",
                knowledge_type="capability",
                subject=repo_id,
                predicate="provides",
                object="Store recipes with ingredients and instructions",
                scope=repo_id,
                normative_force="observed",
                confidence="high",
                evidence_refs=[EvidenceRef(kind="file_line", path="models.py", start_line=10)],
                source_card_ids=[],
            )
        ],
        soul_graph={"eagle_eye_summary": "Recipe management with local JSON storage"},
        community_signals=CommunitySignals(sentiment="positive"),
    )


def make_mock_llm_response(for_phase: str) -> str:
    """Return appropriate mock LLM response for each phase."""
    if for_phase == "phase_a":
        return json.dumps({
            "keywords": ["recipe", "meal", "food", "cooking", "ingredients"],
            "intent": "Manage home recipes with ingredients and cooking instructions",
            "search_directions": [
                {"direction": "recipe management app", "priority": "high"},
                {"direction": "meal planner python", "priority": "medium"},
            ],
            "constraints": ["single-user", "local storage"],
            "quality_expectations": {
                "why_depth": "storage design decisions",
                "unsaid_focus": "encoding and file naming gotchas",
            },
        })
    elif for_phase == "phase_d":
        return json.dumps({
            "skills": [
                {
                    "name": "Recipe Manager Community Pattern",
                    "source": "https://github.com/community/recipes",
                    "kind": "skill",
                    "capabilities": ["store recipes", "search by ingredient"],
                    "reusable_knowledge": [
                        "Always use UTF-8 encoding for recipe names",
                        "JSON is preferred over SQLite for single-user apps",
                    ],
                }
            ],
            "tutorials": [],
            "use_cases": [
                {
                    "name": "Home Cook Recipe Tracker",
                    "source": "community forum",
                    "kind": "use_case",
                    "capabilities": ["organize family recipes"],
                    "reusable_knowledge": ["Tag recipes by cuisine type for easier discovery"],
                }
            ],
        })
    elif for_phase == "skill_content":
        return """---
name: recipe-manager-skill
description: Manage home recipes with ingredients and cooking instructions
version: "1.0"
allowed-tools: exec, read, write
---

# Recipe Manager Skill

> Store, organize, and retrieve your family recipes without ever losing them again.

## Design Philosophy
Recipe storage should be invisible infrastructure — the cook thinks about food, not files.
JSON files are chosen over databases because single-user apps don't need concurrent access.

## Mental Model
Think of ~/clawd/recipes/ as your kitchen drawer — each recipe is a JSON card you can read, write, or search.

## Why This Design

**Decision**: Use JSON instead of SQLite
**Why**: Because single-user local skills don't need concurrent access. JSON is zero-dependency
and human-readable. Evidence from recipe-app/models.py.

**Decision**: Store images as base64 or links, not binary blobs
**Why**: Keeps the storage portable and git-friendly. Blobs break diffs.

## Core Capabilities

- Store recipes with ingredients, steps, and metadata
- Search recipes by name, ingredient, or tag
- Export recipes to Markdown for sharing
- Track cooking history

## Storage (~/clawd/ only)

```
~/clawd/recipes/
├── index.json           # Recipe index
└── <recipe-slug>.json   # Individual recipe files
```

## Gotchas

1. **File naming**: Use slugified names (no spaces, no Unicode in filenames) to avoid macOS/Linux encoding issues
2. **Backup**: ~/clawd/recipes/ is not auto-backed-up — remind users to export periodically
3. **Large images**: Don't store full-res images in JSON — link to files instead

## Quick Start

1. Create a recipe: exec `write ~/clawd/recipes/pasta-carbonara.json '{"name":"Pasta Carbonara",...}'`
2. List recipes: exec `read ~/clawd/recipes/index.json`
3. Search: exec `grep -r "chicken" ~/clawd/recipes/`

## Known Limitations

This skill does NOT automatically sync across devices.
"""
    else:
        return "## CAPABILITIES\n- Store recipes\n- Search recipes\n\n## CONSTRAINTS\n- Single user only\n\n## WHY_DECISIONS\n- Use JSON for zero-dependency storage\n\n## UNSAID_GOTCHAS\n- Use ASCII filenames to avoid encoding issues"


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------

class TestPhaseA(unittest.TestCase):
    """Phase A: Need Understanding."""

    def test_parse_need_profile_basic(self):
        """Phase A should produce a NeedProfile from raw text."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)

            with patch.object(doramagic, "_call_llm", return_value=make_mock_llm_response("phase_a")):
                profile = doramagic.phase_a_understand("我想做一个管理家庭菜谱的 skill", run_dir)

            self.assertIsInstance(profile, NeedProfile)
            self.assertIn("recipe", profile.keywords)
            self.assertTrue(len(profile.search_directions) >= 1)
            self.assertTrue(len(profile.intent) > 5)
            # Check file written (must check INSIDE tempdir context)
            np_path = run_dir / "need_profile.json"
            self.assertTrue(np_path.exists())

    def test_fallback_on_invalid_llm_response(self):
        """Phase A should fall back gracefully if LLM returns non-JSON."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            with patch.object(doramagic, "_call_llm", return_value="sorry i cannot help"):
                profile = doramagic.phase_a_understand("recipe skill", run_dir)

        self.assertIsInstance(profile, NeedProfile)
        self.assertTrue(len(profile.keywords) > 0)


class TestPhaseB(unittest.TestCase):
    """Phase B: Discovery."""

    def _make_mock_gh_response(self) -> List[Dict]:
        return [
            {
                "id": i + 1,
                "full_name": f"user/recipe-app-{i}",
                "html_url": f"https://github.com/user/recipe-app-{i}",
                "description": "A recipe management application",
                "stargazers_count": 100 * (i + 1),
                "forks_count": 10 * (i + 1),
                "updated_at": "2025-01-01T00:00:00Z",
                "language": "Python",
                "license": {"spdx_id": "MIT"},
            }
            for i in range(5)
        ]

    def test_discovery_produces_candidates(self):
        """Phase B should produce DiscoveryResult with candidates."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            profile = make_need_profile()

            with patch.object(doramagic, "_search_github", return_value=self._make_mock_gh_response()):
                result = doramagic.phase_b_discover(profile, run_dir)

        self.assertIsInstance(result, DiscoveryResult)
        self.assertGreater(len(result.candidates), 0)
        self.assertLessEqual(len(result.candidates), 5)
        # Top 3 should be selected for Phase C
        selected = [c for c in result.candidates if c.selected_for_phase_c]
        self.assertLessEqual(len(selected), 3)

    def test_discovery_handles_empty_github(self):
        """Phase B should handle empty GitHub results gracefully."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            profile = make_need_profile()

            with patch.object(doramagic, "_search_github", return_value=[]):
                result = doramagic.phase_b_discover(profile, run_dir)

        self.assertIsInstance(result, DiscoveryResult)
        # May have no candidates
        self.assertTrue(len(result.search_coverage) > 0)

    def test_discovery_file_written(self):
        """Phase B should write discovery_result.json."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            profile = make_need_profile()

            with patch.object(doramagic, "_search_github", return_value=self._make_mock_gh_response()):
                doramagic.phase_b_discover(profile, run_dir)

            dr_path = run_dir / "discovery_result.json"
            self.assertTrue(dr_path.exists())
            data = json.loads(dr_path.read_text())
            self.assertIn("candidates", data)


class TestPhaseC(unittest.TestCase):
    """Phase C: Soul Extraction."""

    def _make_candidate(self, i: int = 0) -> DiscoveryCandidate:
        return DiscoveryCandidate(
            candidate_id=f"cand-{i+1:02d}",
            name=f"user/recipe-app-{i}",
            url=f"https://github.com/user/recipe-app-{i}",
            type="github_repo",
            relevance="high",
            contribution="Recipe management app",
            quick_score=8.0,
            quality_signals=CandidateQualitySignals(stars=100, forks=10, license="MIT"),
            selected_for_phase_c=True,
        )

    def test_extraction_with_mock_download(self):
        """Phase C should extract fingerprints from downloaded repos."""
        # Use a response that has CAPABILITIES section (for _extract_soul_llm)
        extraction_response = (
            "## CAPABILITIES\n- Store recipes\n- Search by ingredient\n\n"
            "## CONSTRAINTS\n- Single user only\n\n"
            "## WHY_DECISIONS\n- JSON for zero-dependency storage\n\n"
            "## UNSAID_GOTCHAS\n- Filename encoding issues on macOS\n\n"
            "## DESIGN_PHILOSOPHY\n- Recipes should be invisible infrastructure\n"
        )
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            candidates = [self._make_candidate(i) for i in range(2)]
            profile = make_need_profile()

            # Create mock repo path
            mock_repo_path = Path(td) / "mock_repo"
            mock_repo_path.mkdir()
            (mock_repo_path / "README.md").write_text("# Recipe App\nA recipe manager.", encoding="utf-8")
            (mock_repo_path / "models.py").write_text("class Recipe:\n    pass\n", encoding="utf-8")

            with patch.object(doramagic, "_download_repo_zip", return_value=mock_repo_path), \
                 patch.object(doramagic, "_get_repo_info", return_value={"default_branch": "main", "language": "Python"}), \
                 patch.object(doramagic, "_call_llm", return_value=extraction_response):
                fingerprints, summaries = doramagic.phase_c_extract(candidates, profile, run_dir)

            self.assertEqual(len(fingerprints), 2)
            self.assertEqual(len(summaries), 2)
            for fp in fingerprints:
                self.assertIsInstance(fp, ProjectFingerprint)
                self.assertGreater(len(fp.knowledge_atoms), 0)

    def test_extraction_handles_download_failure(self):
        """Phase C should skip repos that fail to download."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            candidates = [self._make_candidate(0)]
            profile = make_need_profile()

            with patch.object(doramagic, "_download_repo_zip", return_value=None), \
                 patch.object(doramagic, "_get_repo_info", return_value={}):
                fingerprints, summaries = doramagic.phase_c_extract(candidates, profile, run_dir)

        # Should gracefully return empty lists
        self.assertEqual(len(fingerprints), 0)
        self.assertEqual(len(summaries), 0)


class TestPhaseD(unittest.TestCase):
    """Phase D: Community Knowledge."""

    def test_community_produces_knowledge(self):
        """Phase D should produce CommunityKnowledge."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            profile = make_need_profile()
            candidates = []

            with patch.object(doramagic, "_call_llm", return_value=make_mock_llm_response("phase_d")):
                ck = doramagic.phase_d_community(candidates, profile, run_dir)

        self.assertIsInstance(ck, CommunityKnowledge)
        total = len(ck.skills) + len(ck.tutorials) + len(ck.use_cases)
        self.assertGreater(total, 0)

    def test_community_file_written(self):
        """Phase D should write community_knowledge.json."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            profile = make_need_profile()

            with patch.object(doramagic, "_call_llm", return_value=make_mock_llm_response("phase_d")):
                doramagic.phase_d_community([], profile, run_dir)

            ck_path = run_dir / "community_knowledge.json"
            self.assertTrue(ck_path.exists())


class TestPhaseE(unittest.TestCase):
    """Phase E: Synthesis."""

    def test_minimal_synthesis_with_one_project(self):
        """Phase E should create minimal synthesis when only 1 project available."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            profile = make_need_profile()
            fp = make_fingerprint("cand-01")
            summary = ExtractedProjectSummary(
                project_id="cand-01",
                repo=fp.project,
                top_capabilities=["Store recipes", "Search by ingredient"],
                top_constraints=["Single user only"],
                top_failures=["Unicode filename issues"],
                evidence_refs=[],
            )
            community = CommunityKnowledge()
            discovery = DiscoveryResult(candidates=[], search_coverage=[])

            result = doramagic.phase_e_synthesize([fp], [summary], community, profile, discovery, run_dir)

        from doramagic_contracts.cross_project import SynthesisReportData
        self.assertIsInstance(result, SynthesisReportData)

    def test_synthesis_with_two_projects(self):
        """Phase E should run full compare+synthesis with 2 projects."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            profile = make_need_profile()
            fp1 = make_fingerprint("cand-01", "user/recipe-app-1")
            fp2 = make_fingerprint("cand-02", "user/recipe-app-2")
            summary1 = ExtractedProjectSummary(
                project_id="cand-01",
                repo=fp1.project,
                top_capabilities=["Store recipes"],
                top_constraints=[],
                top_failures=[],
                evidence_refs=[],
            )
            summary2 = ExtractedProjectSummary(
                project_id="cand-02",
                repo=fp2.project,
                top_capabilities=["Store recipes"],
                top_constraints=[],
                top_failures=[],
                evidence_refs=[],
            )
            community = CommunityKnowledge()
            discovery = DiscoveryResult(candidates=[], search_coverage=[])

            result = doramagic.phase_e_synthesize(
                [fp1, fp2], [summary1, summary2], community, profile, discovery, run_dir
            )

        from doramagic_contracts.cross_project import SynthesisReportData
        self.assertIsInstance(result, SynthesisReportData)


class TestPhaseFGH(unittest.TestCase):
    """Phase F-G-H: Forge, Validate, Deliver."""

    def _setup_synthesis(self) -> "SynthesisReportData":
        from doramagic_contracts.cross_project import SynthesisDecision, SynthesisReportData
        return SynthesisReportData(
            consensus=[],
            conflicts=[],
            unique_knowledge=[],
            selected_knowledge=[
                SynthesisDecision(
                    decision_id="dec-001",
                    statement="Store recipes as JSON files in ~/clawd/recipes/",
                    decision="include",
                    rationale="JSON is zero-dependency and human-readable",
                    source_refs=["cand-01"],
                    demand_fit="high",
                )
            ],
            excluded_knowledge=[],
            open_questions=[],
        )

    def _forge_delivery(self, td: str, synthesized_knowledge: Optional[str] = None) -> "tuple":
        """Helper: forge delivery files and return (delivery_dir, profile, synthesis, fingerprints)."""
        run_dir = Path(td)
        profile = make_need_profile()
        synthesis = self._setup_synthesis()
        fingerprints = [make_fingerprint("cand-01")]
        summaries = [
            ExtractedProjectSummary(
                project_id="cand-01",
                repo=fingerprints[0].project,
                top_capabilities=["Store recipes", "Search recipes"],
                top_constraints=["Single user"],
                top_failures=["Unicode filenames"],
                evidence_refs=[],
            )
        ]
        mock_resp = synthesized_knowledge or make_mock_llm_response("skill_content")
        with patch.object(doramagic, "_call_llm", return_value=mock_resp):
            delivery_dir = doramagic.phase_f_forge(
                profile, synthesis, fingerprints, summaries, run_dir
            )
        return delivery_dir, profile, synthesis, fingerprints

    def test_forge_creates_delivery_files(self):
        """Phase F should create SKILL.md, PROVENANCE.md, LIMITATIONS.md, README.md."""
        with tempfile.TemporaryDirectory() as td:
            delivery_dir, _, _, _ = self._forge_delivery(td)
            self.assertTrue((delivery_dir / "SKILL.md").exists())
            self.assertTrue((delivery_dir / "PROVENANCE.md").exists())
            self.assertTrue((delivery_dir / "LIMITATIONS.md").exists())
            self.assertTrue((delivery_dir / "README.md").exists())

    def test_skill_has_frontmatter(self):
        """SKILL.md should always start with YAML frontmatter."""
        with tempfile.TemporaryDirectory() as td:
            delivery_dir, _, _, _ = self._forge_delivery(td)
            skill_content = (delivery_dir / "SKILL.md").read_text()
            self.assertTrue(skill_content.strip().startswith("---"), "SKILL.md must start with frontmatter")
            self.assertIn("allowed-tools", skill_content)
            self.assertIn("description", skill_content)

    def test_provenance_has_urls(self):
        """PROVENANCE.md must contain traceable URLs."""
        with tempfile.TemporaryDirectory() as td:
            delivery_dir, _, _, _ = self._forge_delivery(td)
            provenance = (delivery_dir / "PROVENANCE.md").read_text()
            self.assertIn("https://", provenance)

    def test_limitations_is_honest(self):
        """LIMITATIONS.md should mention what the skill does NOT do."""
        with tempfile.TemporaryDirectory() as td:
            delivery_dir, _, _, _ = self._forge_delivery(td)
            limitations = (delivery_dir / "LIMITATIONS.md").read_text()
            self.assertIn("NOT", limitations.upper())

    def test_validation_runs_on_forged_skill(self):
        """Phase G should run validation and return a report."""
        with tempfile.TemporaryDirectory() as td:
            delivery_dir, profile, synthesis, _ = self._forge_delivery(td)
            report = doramagic.phase_g_validate(profile, synthesis, delivery_dir)
            from doramagic_contracts.skill import ValidationReport
            self.assertIsInstance(report, ValidationReport)
            self.assertIn(report.status, ("PASS", "REVISE", "BLOCKED"))
            self.assertGreater(len(report.checks), 0)


class TestFallback(unittest.TestCase):
    """Test fallback behavior when no repos available."""

    def test_fallback_fingerprints_created(self):
        """Should create fallback fingerprints from LLM knowledge."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            profile = make_need_profile()
            mock_resp = "## CAPABILITIES\n- Store recipes\n- Search recipes\n\n## CONSTRAINTS\n- Single user\n\n## WHY_DECISIONS\n- JSON for simplicity\n\n## UNSAID_GOTCHAS\n- Filename encoding"

            with patch.object(doramagic, "_call_llm", return_value=mock_resp):
                fps, summaries = doramagic._create_fallback_fingerprints(profile, run_dir)

        self.assertEqual(len(fps), 1)
        self.assertEqual(len(summaries), 1)
        self.assertGreater(len(fps[0].knowledge_atoms), 0)


class TestHelpers(unittest.TestCase):
    """Test helper functions."""

    def test_slug(self):
        self.assertEqual(doramagic._slug("Hello World!"), "hello-world")
        self.assertEqual(doramagic._slug("我想做菜谱 skill"), "skill")  # non-ASCII stripped

    def test_extract_section(self):
        text = "## CAPABILITIES\n- Store recipes\n- Search by ingredient\n\n## CONSTRAINTS\n- Single user"
        caps = doramagic._extract_section(text, "CAPABILITIES")
        self.assertEqual(len(caps), 2)
        # Items have leading bullets stripped
        self.assertIn("Store recipes", caps)
        self.assertIn("Search by ingredient", caps)

    def test_extract_section_missing(self):
        result = doramagic._extract_section("no sections here", "CAPABILITIES")
        self.assertEqual(result, [])

    def test_run_id_unique(self):
        id1 = doramagic._run_id()
        time.sleep(0.002)
        id2 = doramagic._run_id()
        self.assertNotEqual(id1, id2)
        self.assertTrue(id1.startswith("run-"))


if __name__ == "__main__":
    unittest.main()
