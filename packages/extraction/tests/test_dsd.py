"""
Tests for deceptive_source_detection.py

Includes:
  - Unit tests for each of the 8 DSD checks
  - Two integration fixtures:
      GOOD_PROJECT  — well-documented open project (should be CLEAN or low WARNING)
      DARK_TRAP     — deceptive/hallucinated knowledge base (should be WARNING/SUSPICIOUS)

Run with:  pytest tests/test_dsd.py -v
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from deceptive_source_detection import (
    DSDCheck,
    DSDReport,
    check_dsd1_rationale_support_ratio,
    check_dsd2_temporal_conflict,
    check_dsd3_exception_dominance,
    check_dsd4_support_desk_share,
    check_dsd5_public_context_completeness,
    check_dsd6_persona_divergence,
    check_dsd7_dependency_dominance,
    check_dsd8_narrative_evidence_tension,
    compute_overall_status,
    run_dsd_checks,
)


# ---------------------------------------------------------------------------
# Fixtures — Good Project (wger-style: open source, well-documented)
# ---------------------------------------------------------------------------

GOOD_CARDS = [
    {
        "card_id": "DR-001",
        "card_type": "decision_rule_card",
        "question_key": "Q2",  # rationale
        "knowledge_type": "rationale",
        "subject": "REST API versioning",
        "title": "Use /api/v2/ prefix for all endpoints",
        "statement": "The REST API must use versioned URL prefixes to maintain backward compatibility.",
        "evidence_refs": [
            {"kind": "file_line", "path": "wger/urls.py", "start_line": 42},
            {"kind": "artifact_ref", "path": "docs/api.rst"},
        ],
        "evidence_tags": ["CODE", "DOC"],
        "sources": ["wger/urls.py:42", "docs/api.rst"],
    },
    {
        "card_id": "DR-002",
        "card_type": "decision_rule_card",
        "question_key": "Q2",
        "knowledge_type": "rationale",
        "subject": "Exercise permission model",
        "title": "Public exercises are shared across all users",
        "statement": "Exercises with status ACCEPTED are visible to all users and should not be duplicated per user.",
        "evidence_refs": [
            {"kind": "file_line", "path": "wger/exercises/models.py", "start_line": 88},
            {"kind": "community_ref", "path": "https://github.com/wger-project/wger/issues/123"},
        ],
        "evidence_tags": ["CODE", "COMMUNITY"],
        "sources": ["wger/exercises/models.py:88", "Issue #123"],
    },
    {
        "card_id": "DR-003",
        "card_type": "decision_rule_card",
        "question_key": "Q1",  # capability
        "knowledge_type": "capability",
        "subject": "Nutrition logging",
        "title": "Nutritional values are per 100g",
        "statement": "All nutritional values must be stored per 100g to allow consistent calculation.",
        "evidence_refs": [
            {"kind": "file_line", "path": "wger/nutrition/models.py", "start_line": 55},
        ],
        "evidence_tags": ["CODE"],
    },
    {
        "card_id": "CC-001",
        "card_type": "concept_card",
        "question_key": "Q3",
        "knowledge_type": "constraint",
        "subject": "User muscle body map",
        "title": "SVG-based muscle visualization",
        "statement": "The body map is rendered using SVG overlays defined in the frontend templates.",
        "evidence_refs": [
            {"kind": "artifact_ref", "path": "templates/muscle/overview.html"},
            {"kind": "file_line", "path": "wger/muscles/views.py"},
        ],
        "evidence_tags": ["CODE", "CODE"],
    },
]

GOOD_COMMUNITY_SIGNALS = """
### SIG-001: Issue #123 — Exercise sharing model
reply: Confirmed by maintainer that ACCEPTED exercises are global.
comment: Makes sense for a public fitness database.

### SIG-002: Issue #456 — Nutritional data precision
comment: Using 100g as base unit is the standard.
comment: Agrees with international nutrition standards.

### SIG-003: PR #789 — API versioning
response: Merged without changes — versioning is well established.
"""

GOOD_REPO_FACTS = {
    "languages": ["Python", "JavaScript"],
    "frameworks": ["Django", "Vue.js"],
    "entrypoints": ["manage.py"],
    "commands": ["python manage.py runserver", "pytest"],
    "storage_paths": ["media/", "static/"],
    "dependencies": ["Django", "djangorestframework", "Pillow", "celery"],
    "repo_summary": "Open source workout manager",
}


# ---------------------------------------------------------------------------
# Fixtures — Dark Trap Project (hallucinated/deceptive knowledge base)
# ---------------------------------------------------------------------------

DARK_TRAP_CARDS = [
    {
        "card_id": "DR-001",
        "card_type": "decision_rule_card",
        "question_key": "Q2",  # rationale — but NO evidence
        "knowledge_type": "rationale",
        "subject": "Data sync strategy",
        "title": "Inferred sync approach",
        "statement": "It is likely that data is synced via the proprietary API. This is probably the best approach.",
        "evidence_refs": [],  # no evidence!
        "evidence_tags": ["INFERENCE"],
    },
    {
        "card_id": "DR-002",
        "card_type": "decision_rule_card",
        "question_key": "Q2",
        "knowledge_type": "rationale",
        "subject": "Auth mechanism",
        "title": "Authentication assumed to be OAuth2",
        "statement": "Authentication appears to use OAuth2 based on inferred patterns. Unclear if this is the only method.",
        "evidence_refs": [],
        "evidence_tags": ["INFERENCE"],
    },
    {
        "card_id": "DR-003",
        "card_type": "decision_rule_card",
        "question_key": "Q2",
        "knowledge_type": "rationale",
        "subject": "Caching layer",
        "title": "Possibly Redis-based caching",
        "statement": "It seems the caching layer is likely Redis. This is assumed from typical patterns.",
        "evidence_refs": [],
        "evidence_tags": ["INFERENCE"],
    },
    {
        "card_id": "DR-004",
        "card_type": "decision_rule_card",
        "question_key": "Q1",
        "knowledge_type": "capability",
        "subject": "Core data pipeline",
        "title": "Requires external paid SaaS service",
        "statement": "The core pipeline must use the paid API provided by ClosedVendor Inc. API key required.",
        "evidence_refs": [
            {"kind": "community_ref", "path": "https://forum.example.com/workaround-thread"},
        ],
        "evidence_tags": ["COMMUNITY"],
    },
    {
        "card_id": "DR-005",
        "card_type": "decision_rule_card",
        "question_key": "Q1",
        "knowledge_type": "capability",
        "subject": "Reporting engine",
        "title": "Enterprise-only reporting",
        "statement": "Reporting should only be used with the enterprise license. Always configure the proprietary connector.",
        "evidence_refs": [],
        "evidence_tags": ["INFERENCE"],
    },
    {
        "card_id": "DR-006",
        "card_type": "decision_rule_card",
        "question_key": "Q2",
        "knowledge_type": "rationale",
        "subject": "Data sync strategy",
        "title": "Version conflict: old docs say v1, new code says v3",
        "statement": "The sync protocol uses v1.x according to the guide, but runtime requires v3.x.",
        "evidence_refs": [
            {"kind": "artifact_ref", "path": "legacy-guide.md", "snippet": "sync v1.2"},
            {"kind": "file_line", "path": "src/sync.py", "snippet": "requires v3.5"},
        ],
        "evidence_tags": ["DOC", "CODE"],
    },
]

DARK_TRAP_COMMUNITY_SIGNALS = """
### SIG-001: Workaround for auth failure
workaround: Set the timeout to 0 to bypass auth check.
hack: Monkey-patch the session handler to avoid the bug.
edge case: This only works on Linux, not on macOS.

### SIG-002: Gotcha with data export
workaround: Use the undocumented API endpoint /export-v0.
edge case: Fails with > 1000 records — use pagination workaround.
hack: Patch the ORM layer with this monkey-patch.

### SIG-003: Footgun with permissions
workaround: Disable permission check in production.
pitfall: The public docs are wrong about permission scope.
hack: Use band-aid solution from issue #99.
comment: [reply] This workaround is confirmed by maintainer.
"""

DARK_TRAP_REPO_FACTS = {
    "languages": ["Python"],
    "frameworks": ["FastAPI"],
    "entrypoints": ["main.py"],
    "commands": ["uvicorn main:app"],
    "storage_paths": [],
    "dependencies": [
        "fastapi",
        "closed-source-saas-sdk",
        "enterprise-connector",
        "paid-api-client",
    ],
    "repo_summary": "Pipeline using multiple paid external services",
}


# ---------------------------------------------------------------------------
# Unit tests — DSD-1
# ---------------------------------------------------------------------------


class TestDSD1RationaleSupport:
    def test_no_rationale_cards_skipped(self):
        cards = [{"card_id": "X", "knowledge_type": "capability", "evidence_tags": ["CODE"]}]
        result = check_dsd1_rationale_support_ratio(cards)
        assert result.triggered is False
        assert result.score == 0.0

    def test_all_rationale_cards_have_evidence(self):
        cards = [
            {
                "card_id": "R1",
                "question_key": "Q2",
                "knowledge_type": "rationale",
                "evidence_tags": ["CODE"],
            },
            {
                "card_id": "R2",
                "question_key": "Q2",
                "knowledge_type": "rationale",
                "evidence_tags": ["DOC", "COMMUNITY"],
            },
        ]
        result = check_dsd1_rationale_support_ratio(cards)
        assert result.triggered is False
        assert result.score == 0.0  # ratio=1.0, score=1-1=0

    def test_zero_rationale_support_triggers(self):
        cards = [
            {
                "card_id": "R1",
                "question_key": "Q2",
                "knowledge_type": "rationale",
                "evidence_tags": ["INFERENCE"],
            },
            {
                "card_id": "R2",
                "question_key": "Q2",
                "knowledge_type": "rationale",
                "evidence_tags": ["INFERENCE"],
            },
            {
                "card_id": "R3",
                "question_key": "Q2",
                "knowledge_type": "rationale",
                "evidence_tags": ["INFERENCE"],
            },
        ]
        result = check_dsd1_rationale_support_ratio(cards)
        assert result.triggered is True
        assert result.score == pytest.approx(1.0)

    def test_below_threshold_triggers(self):
        # 1 out of 5 rationale cards has evidence → ratio=0.2 < 0.3
        cards = []
        for i in range(5):
            cards.append({
                "card_id": f"R{i}",
                "question_key": "Q2",
                "knowledge_type": "rationale",
                "evidence_tags": ["CODE"] if i == 0 else ["INFERENCE"],
            })
        result = check_dsd1_rationale_support_ratio(cards)
        assert result.triggered is True


# ---------------------------------------------------------------------------
# Unit tests — DSD-2
# ---------------------------------------------------------------------------


class TestDSD2TemporalConflict:
    def test_no_version_refs_no_trigger(self):
        cards = [{"subject": "auth", "evidence_refs": [{"path": "src/auth.py", "kind": "file_line"}]}]
        result = check_dsd2_temporal_conflict(cards)
        assert result.triggered is False

    def test_same_major_version_no_trigger(self):
        cards = [
            {
                "subject": "api",
                "evidence_refs": [
                    {"kind": "file_line", "path": "v2.3/api.py"},
                    {"kind": "file_line", "path": "v2.7/api.py"},
                ],
            }
        ]
        result = check_dsd2_temporal_conflict(cards)
        assert result.triggered is False

    def test_two_major_versions_apart_triggers(self):
        cards = [
            {
                "subject": "sync",
                "evidence_refs": [
                    {"kind": "artifact_ref", "path": "legacy-guide.md", "snippet": "uses v1.2"},
                    {"kind": "file_line", "path": "src/sync.py", "snippet": "requires v3.5"},
                ],
            }
        ]
        result = check_dsd2_temporal_conflict(cards)
        assert result.triggered is True

    def test_exactly_one_version_apart_no_trigger(self):
        cards = [
            {
                "subject": "db",
                "evidence_refs": [
                    {"kind": "file_line", "path": "v1.9/schema.sql"},
                    {"kind": "file_line", "path": "v2.0/schema.sql"},
                ],
            }
        ]
        result = check_dsd2_temporal_conflict(cards)
        # Gap = 1, threshold is >= 2
        assert result.triggered is False


# ---------------------------------------------------------------------------
# Unit tests — DSD-3
# ---------------------------------------------------------------------------


class TestDSD3ExceptionDominance:
    def test_no_community_signals_skipped(self):
        result = check_dsd3_exception_dominance([], "")
        assert result.triggered is False

    def test_clean_community_signals(self):
        signals = "Feature works as expected.\nGood documentation.\nEasy to use.\n"
        result = check_dsd3_exception_dominance([], signals)
        assert result.triggered is False

    def test_high_workaround_density_triggers(self):
        signals = (
            "workaround: use undocumented flag\n"
            "hack: patch the library\n"
            "edge case: only works on linux\n"
            "workaround: disable auth check\n"
            "pitfall: docs are wrong\n"
            "gotcha: broken in prod\n"
            "normal comment about something"
        )
        result = check_dsd3_exception_dominance([], signals)
        assert result.triggered is True
        assert result.score > 0.6

    def test_exactly_at_threshold_not_triggered(self):
        # 6 workaround lines out of 10 = 0.6 → not > 0.6
        lines = ["workaround line"] * 6 + ["clean line"] * 4
        signals = "\n".join(lines)
        result = check_dsd3_exception_dominance([], signals)
        assert result.triggered is False  # 0.6 is not > 0.6


# ---------------------------------------------------------------------------
# Unit tests — DSD-4
# ---------------------------------------------------------------------------


class TestDSD4SupportDeskShare:
    def test_no_signals_skipped(self):
        result = check_dsd4_support_desk_share("")
        assert result.triggered is False

    def test_no_reply_markers_skipped(self):
        signals = "This is documentation text with no replies."
        result = check_dsd4_support_desk_share(signals)
        assert result.triggered is False

    def test_balanced_community_ok(self):
        signals = (
            "comment: User asks about feature.\n"
            "reply: Community member explains.\n"
            "comment: Another user question.\n"
            "reply: Different community member helps.\n"
            "reply: maintainer clarifies one point.\n"
        )
        result = check_dsd4_support_desk_share(signals)
        assert result.triggered is False

    def test_maintainer_dominance_triggers(self):
        # 9 out of 10 replies are from maintainer
        maintainer_lines = ["reply: closed by maintainer"] * 9
        other_lines = ["reply: user comment"]
        signals = "\n".join(maintainer_lines + other_lines)
        result = check_dsd4_support_desk_share(signals)
        assert result.triggered is True


# ---------------------------------------------------------------------------
# Unit tests — DSD-5
# ---------------------------------------------------------------------------


class TestDSD5PublicContextCompleteness:
    def test_empty_cards_skipped(self):
        result = check_dsd5_public_context_completeness([])
        assert result.triggered is False

    def test_clean_factual_cards(self):
        cards = [
            {
                "title": "REST API uses JSON format",
                "statement": "All endpoints return JSON. The schema is defined in openapi.yaml.",
            }
        ]
        result = check_dsd5_public_context_completeness(cards)
        assert result.triggered is False

    def test_highly_speculative_cards_trigger(self):
        cards = [
            {
                "title": "Assumed cache layer",
                "statement": (
                    "This is inferred to likely use Redis. It appears to probably "
                    "be assumed from the configuration. This is likely the case "
                    "since it seems to match typical patterns. Probably inferred "
                    "from similar projects. It is unclear if this is accurate. "
                    "Possibly the assumption is wrong. Unknown if this is stable."
                ),
            }
        ]
        result = check_dsd5_public_context_completeness(cards)
        assert result.triggered is True

    def test_moderate_speculation_not_triggered(self):
        # A few inference words spread across a long factual text
        cards = [
            {
                "title": "System architecture",
                "statement": (
                    "The system uses Django for the backend. "
                    "It is likely using PostgreSQL for storage. "
                    "The frontend is React-based and served via CDN. "
                    "API authentication uses JWT tokens as defined in auth.py. "
                    "Rate limiting is applied per user account."
                ),
            }
        ]
        result = check_dsd5_public_context_completeness(cards)
        assert result.triggered is False


# ---------------------------------------------------------------------------
# Unit tests — DSD-6
# ---------------------------------------------------------------------------


class TestDSD6PersonaDivergence:
    def test_no_cards_no_trigger(self):
        result = check_dsd6_persona_divergence([])
        assert result.triggered is False

    def test_consistent_python_version(self):
        cards = [
            {"title": "A", "subject": "runtime", "statement": "Requires Python 3.10"},
            {"title": "B", "subject": "runtime", "statement": "Tested with Python 3.11"},
        ]
        result = check_dsd6_persona_divergence(cards)
        # Both Python 3 — no conflict
        assert result.triggered is False

    def test_python_version_conflict_triggers(self):
        cards = [
            {"title": "A", "subject": "runtime", "statement": "Requires Python 2.7"},
            {"title": "B", "subject": "runtime", "statement": "Tested with Python 3.10"},
        ]
        result = check_dsd6_persona_divergence(cards)
        assert result.triggered is True

    def test_no_env_patterns_no_trigger(self):
        cards = [
            {"title": "X", "subject": "api", "statement": "Uses REST API with JSON"}
        ]
        result = check_dsd6_persona_divergence(cards)
        assert result.triggered is False


# ---------------------------------------------------------------------------
# Unit tests — DSD-7
# ---------------------------------------------------------------------------


class TestDSD7DependencyDominance:
    def test_no_cards_no_facts_skipped(self):
        result = check_dsd7_dependency_dominance([], {})
        assert result.triggered is False

    def test_open_source_deps_no_trigger(self):
        repo_facts = {
            "dependencies": ["Django", "djangorestframework", "Pillow", "celery"]
        }
        result = check_dsd7_dependency_dominance([], repo_facts)
        assert result.triggered is False

    def test_closed_source_deps_trigger(self):
        repo_facts = {
            "dependencies": [
                "closed-vendor-sdk",
                "paid-api-client",
                "enterprise-connector",
                "open-source-lib",
            ]
        }
        result = check_dsd7_dependency_dominance([], repo_facts)
        assert result.triggered is True

    def test_half_closed_source_not_triggered(self):
        # 2 out of 4 = 0.5 → not > 0.5
        repo_facts = {
            "dependencies": [
                "paid-api-key-client",
                "saas-connector",
                "open-lib",
                "another-open-lib",
            ]
        }
        result = check_dsd7_dependency_dominance([], repo_facts)
        # score = 0.5, threshold is > 0.5
        assert result.triggered is False


# ---------------------------------------------------------------------------
# Unit tests — DSD-8
# ---------------------------------------------------------------------------


class TestDSD8NarrativeEvidenceTension:
    def test_no_cards_skipped(self):
        result = check_dsd8_narrative_evidence_tension([])
        assert result.triggered is False

    def test_cards_with_evidence_no_trigger(self):
        cards = [
            {
                "title": "Must validate input",
                "statement": "Input should always be validated before processing.",
                "evidence_refs": [{"kind": "file_line", "path": "src/validators.py"}],
            }
        ]
        result = check_dsd8_narrative_evidence_tension(cards)
        assert result.triggered is False

    def test_assertions_without_evidence_trigger(self):
        # Cards with strong assertions but no evidence_refs
        cards = [
            {
                "title": f"Rule {i}",
                "statement": "You must always use this approach. It is the best practice.",
                "evidence_refs": [],
            }
            for i in range(5)
        ]
        result = check_dsd8_narrative_evidence_tension(cards)
        assert result.triggered is True

    def test_no_assertive_language_no_trigger(self):
        cards = [
            {
                "title": "Overview",
                "statement": "This project handles fitness data and workout tracking.",
                "evidence_refs": [],
            }
        ]
        result = check_dsd8_narrative_evidence_tension(cards)
        # No strong modal verbs → no assertions counted
        assert result.triggered is False


# ---------------------------------------------------------------------------
# compute_overall_status
# ---------------------------------------------------------------------------


class TestComputeOverallStatus:
    def _make_check(self, triggered: bool) -> DSDCheck:
        return DSDCheck("X", "test", 0.5 if triggered else 0.0, triggered, "")

    def test_zero_triggered_clean(self):
        checks = [self._make_check(False)] * 8
        assert compute_overall_status(checks) == "CLEAN"

    def test_one_triggered_warning(self):
        checks = [self._make_check(False)] * 7 + [self._make_check(True)]
        assert compute_overall_status(checks) == "WARNING"

    def test_three_triggered_warning(self):
        checks = [self._make_check(True)] * 3 + [self._make_check(False)] * 5
        assert compute_overall_status(checks) == "WARNING"

    def test_four_triggered_suspicious(self):
        checks = [self._make_check(True)] * 4 + [self._make_check(False)] * 4
        assert compute_overall_status(checks) == "SUSPICIOUS"

    def test_all_triggered_suspicious(self):
        checks = [self._make_check(True)] * 8
        assert compute_overall_status(checks) == "SUSPICIOUS"


# ---------------------------------------------------------------------------
# Integration test — GOOD PROJECT
# ---------------------------------------------------------------------------


class TestGoodProjectIntegration:
    """A well-documented open-source project should score CLEAN or mild WARNING."""

    def test_good_project_overall_status(self):
        report = run_dsd_checks(
            cards=GOOD_CARDS,
            repo_facts=GOOD_REPO_FACTS,
            community_signals=GOOD_COMMUNITY_SIGNALS,
        )
        # Should not be SUSPICIOUS
        assert report.overall_status in ("CLEAN", "WARNING"), (
            f"Good project should not be SUSPICIOUS, got {report.overall_status}. "
            f"Triggered: {[c.check_id for c in report.checks if c.triggered]}"
        )

    def test_good_project_dsd1_not_triggered(self):
        """Rationale cards in good project all have evidence."""
        report = run_dsd_checks(GOOD_CARDS, GOOD_REPO_FACTS, GOOD_COMMUNITY_SIGNALS)
        dsd1 = next(c for c in report.checks if c.check_id == "DSD-1")
        assert dsd1.triggered is False, f"DSD-1 should not trigger: {dsd1.detail}"

    def test_good_project_dsd3_not_triggered(self):
        """Good community signals have minimal workarounds."""
        report = run_dsd_checks(GOOD_CARDS, GOOD_REPO_FACTS, GOOD_COMMUNITY_SIGNALS)
        dsd3 = next(c for c in report.checks if c.check_id == "DSD-3")
        assert dsd3.triggered is False, f"DSD-3 should not trigger: {dsd3.detail}"

    def test_good_project_dsd7_not_triggered(self):
        """Open-source dependencies should not trigger dependency dominance."""
        report = run_dsd_checks(GOOD_CARDS, GOOD_REPO_FACTS, GOOD_COMMUNITY_SIGNALS)
        dsd7 = next(c for c in report.checks if c.check_id == "DSD-7")
        assert dsd7.triggered is False, f"DSD-7 should not trigger: {dsd7.detail}"

    def test_good_project_returns_dsdreport(self):
        report = run_dsd_checks(GOOD_CARDS, GOOD_REPO_FACTS, GOOD_COMMUNITY_SIGNALS)
        assert isinstance(report, DSDReport)
        assert len(report.checks) == 8

    def test_good_project_to_dict(self):
        report = run_dsd_checks(GOOD_CARDS, GOOD_REPO_FACTS, GOOD_COMMUNITY_SIGNALS)
        d = report.to_dict()
        assert "checks" in d
        assert "overall_status" in d
        assert len(d["checks"]) == 8


# ---------------------------------------------------------------------------
# Integration test — DARK TRAP PROJECT
# ---------------------------------------------------------------------------


class TestDarkTrapProjectIntegration:
    """A deceptive/hallucinated knowledge base should trigger multiple DSD checks."""

    def test_dark_trap_overall_status(self):
        report = run_dsd_checks(
            cards=DARK_TRAP_CARDS,
            repo_facts=DARK_TRAP_REPO_FACTS,
            community_signals=DARK_TRAP_COMMUNITY_SIGNALS,
        )
        # Should be WARNING or SUSPICIOUS
        assert report.overall_status in ("WARNING", "SUSPICIOUS"), (
            f"Dark trap project should trigger warnings, got {report.overall_status}. "
            f"Triggered: {[c.check_id for c in report.checks if c.triggered]}"
        )

    def test_dark_trap_dsd1_triggered(self):
        """Most rationale cards have no evidence → DSD-1 should trigger."""
        report = run_dsd_checks(DARK_TRAP_CARDS, DARK_TRAP_REPO_FACTS, DARK_TRAP_COMMUNITY_SIGNALS)
        dsd1 = next(c for c in report.checks if c.check_id == "DSD-1")
        assert dsd1.triggered is True, f"DSD-1 should trigger for dark trap: {dsd1.detail}"

    def test_dark_trap_dsd3_triggered(self):
        """Community signals are dominated by workarounds → DSD-3 should trigger."""
        report = run_dsd_checks(DARK_TRAP_CARDS, DARK_TRAP_REPO_FACTS, DARK_TRAP_COMMUNITY_SIGNALS)
        dsd3 = next(c for c in report.checks if c.check_id == "DSD-3")
        assert dsd3.triggered is True, f"DSD-3 should trigger for dark trap: {dsd3.detail}"

    def test_dark_trap_dsd7_triggered(self):
        """Multiple closed-source dependencies → DSD-7 should trigger."""
        report = run_dsd_checks(DARK_TRAP_CARDS, DARK_TRAP_REPO_FACTS, DARK_TRAP_COMMUNITY_SIGNALS)
        dsd7 = next(c for c in report.checks if c.check_id == "DSD-7")
        assert dsd7.triggered is True, f"DSD-7 should trigger for dark trap: {dsd7.detail}"

    def test_dark_trap_at_least_3_checks_triggered(self):
        """Dark trap should trigger at least 3 checks."""
        report = run_dsd_checks(DARK_TRAP_CARDS, DARK_TRAP_REPO_FACTS, DARK_TRAP_COMMUNITY_SIGNALS)
        triggered = [c for c in report.checks if c.triggered]
        assert len(triggered) >= 3, (
            f"Expected ≥3 triggered checks for dark trap, got {len(triggered)}: "
            f"{[c.check_id for c in triggered]}"
        )

    def test_dark_trap_dsd_is_not_blocking(self):
        """DSD is WARNING not BLOCKING — report must not raise exceptions."""
        # This test ensures run_dsd_checks always returns a report, never raises
        report = run_dsd_checks(DARK_TRAP_CARDS, DARK_TRAP_REPO_FACTS, DARK_TRAP_COMMUNITY_SIGNALS)
        assert isinstance(report, DSDReport)
        assert report.overall_status != "BLOCKED"  # There is no BLOCKED status


# ---------------------------------------------------------------------------
# run_dsd_checks — API contract tests
# ---------------------------------------------------------------------------


class TestRunDsdChecksContract:
    def test_always_returns_8_checks(self):
        report = run_dsd_checks([], {}, "")
        assert len(report.checks) == 8

    def test_check_ids_are_dsd1_through_dsd8(self):
        report = run_dsd_checks([], {}, "")
        ids = {c.check_id for c in report.checks}
        assert ids == {"DSD-1", "DSD-2", "DSD-3", "DSD-4", "DSD-5", "DSD-6", "DSD-7", "DSD-8"}

    def test_scores_in_0_1_range(self):
        report = run_dsd_checks(DARK_TRAP_CARDS, DARK_TRAP_REPO_FACTS, DARK_TRAP_COMMUNITY_SIGNALS)
        for check in report.checks:
            assert 0.0 <= check.score <= 1.0, (
                f"{check.check_id} score {check.score} out of [0, 1]"
            )

    def test_none_args_handled_gracefully(self):
        # Should not raise even with None inputs
        report = run_dsd_checks([], None, None)
        assert isinstance(report, DSDReport)
        assert len(report.checks) == 8

    def test_empty_inputs_all_clean_or_skipped(self):
        report = run_dsd_checks([], {}, "")
        # Empty inputs: all checks should either be skipped or not triggered
        for check in report.checks:
            assert check.triggered is False, (
                f"{check.check_id} triggered on empty input: {check.detail}"
            )
