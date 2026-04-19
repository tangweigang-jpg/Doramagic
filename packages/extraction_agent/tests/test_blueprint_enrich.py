"""Tests for blueprint_enrich.py — SOP v3.4 deterministic patches.

Covers all 14 patch functions and the enrich_blueprint orchestrator.
No LLM calls; all test data is self-contained.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from doramagic_extraction_agent.sop.blueprint_enrich import (
    BD_TYPE_ENUM_FIX_MAP,
    _patch_audit_checklist,
    _patch_bd_injection,
    _patch_bd_type_enum_fix,
    _patch_commit_hash,
    _patch_evidence_format,
    _patch_execution_paradigm,
    _patch_id,
    _patch_relations,
    _patch_required_methods,
    _patch_resource_injection,
    _patch_sop_version,
    _patch_stage_id_validation,
    _patch_uc_merge,
    _patch_uc_normalize,
    _patch_vague_words,
    enrich_blueprint,
)
from doramagic_extraction_agent.sop.schemas_v5 import BDExtractionResult, BusinessDecision
from doramagic_extraction_agent.state.schema import AgentState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_bd(
    bd_id: str = "BD-001",
    content: str = "Use stop-loss at 2% max drawdown per position.",
    bd_type: str = "B",
    rationale: str = (
        "This approach was chosen to cap downside risk on individual positions. "
        "It breaks when market gaps cause slippage beyond the stop level."
    ),
    evidence: str = "trader/trader.py:42(on_stop_loss)",
    stage: str = "risk_management",
    status: str = "present",
    severity: str | None = None,
    impact: str | None = None,
    alternative_considered: str | None = None,
) -> BusinessDecision:
    """Helper to build a valid BusinessDecision without boilerplate."""
    return BusinessDecision(
        id=bd_id,
        content=content,
        type=bd_type,
        rationale=rationale,
        evidence=evidence,
        stage=stage,
        status=status,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        impact=impact,
        alternative_considered=alternative_considered,
    )


def make_bd_result(
    n_present: int = 5,
    n_missing: int = 3,
) -> BDExtractionResult:
    """Create a minimal BDExtractionResult with n_present + n_missing BDs."""
    decisions: list[BusinessDecision] = []

    for i in range(1, n_present + 1):
        decisions.append(
            make_bd(
                bd_id=f"BD-{i:03d}",
                stage="risk_management",
            )
        )

    missing: list[BusinessDecision] = []
    for i in range(n_present + 1, n_present + n_missing + 1):
        bd = make_bd(
            bd_id=f"BD-{i:03d}",
            stage="cost_modeling",
            status="missing",
            severity="medium",
            impact="May cause unexpected losses if not addressed.",
        )
        decisions.append(bd)
        missing.append(bd)

    return BDExtractionResult(
        decisions=decisions,
        type_summary={"B": n_present, "M": n_missing},
        missing_gaps=missing,
    )


def make_state(
    blueprint_id: str = "bp-test-001",
    commit_hash: str = "abc1234def5678",
    subdomain_labels: list[str] | None = None,
    run_dir: str = "/tmp/test_run",
    repo_path: str = "/tmp/test_repo",
) -> AgentState:
    """Create a minimal AgentState for testing."""
    return AgentState(
        blueprint_id=blueprint_id,
        commit_hash=commit_hash,
        subdomain_labels=subdomain_labels or ["TRD"],
        run_dir=run_dir,
        repo_path=repo_path,
    )


def make_blueprint(
    stages: list[dict[str, Any]] | None = None,
    business_decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a minimal blueprint dict."""
    if stages is None:
        stages = [
            {"id": "risk_management", "order": 1, "name": "Risk Management"},
            {"id": "cost_modeling", "order": 2, "name": "Cost Modeling"},
            {"id": "trading_signal", "order": 3, "name": "Trading Signal"},
        ]
    if business_decisions is None:
        business_decisions = [
            {
                "id": "BD-001",
                "type": "B",
                "content": "Use stop-loss mechanism.",
                "rationale": (
                    "Stop-loss caps downside risk. Breaks under extreme gap-down scenarios."
                ),
                "evidence": "trader/trader.py:42(on_stop_loss)",
                "stage": "risk_management",
            }
        ]
    return {
        "stages": stages,
        "business_decisions": business_decisions,
    }


# ---------------------------------------------------------------------------
# P0 _patch_id
# ---------------------------------------------------------------------------


class TestPatchId:
    def test_injects_when_absent(self) -> None:
        bp: dict[str, Any] = {}
        state = make_state(blueprint_id="bp-xyz-001")
        result = _patch_id(bp, state)
        assert result == 1
        assert bp["id"] == "bp-xyz-001"

    def test_leaves_existing_id(self) -> None:
        bp: dict[str, Any] = {"id": "already-set"}
        state = make_state(blueprint_id="bp-xyz-001")
        result = _patch_id(bp, state)
        assert result == 0
        assert bp["id"] == "already-set"


# ---------------------------------------------------------------------------
# P1 _patch_commit_hash
# ---------------------------------------------------------------------------


class TestPatchCommitHash:
    def test_injects_valid_hash(self) -> None:
        bp: dict[str, Any] = {}
        state = make_state(commit_hash="deadbeef1234")
        result = _patch_commit_hash(bp, state)
        assert result == 1
        assert bp["source"]["commit_hash"] == "deadbeef1234"

    def test_skips_head_sentinel(self) -> None:
        bp: dict[str, Any] = {}
        state = make_state(commit_hash="HEAD")
        result = _patch_commit_hash(bp, state)
        assert result == 0
        assert "source" not in bp

    def test_skips_empty_hash(self) -> None:
        bp: dict[str, Any] = {}
        state = make_state(commit_hash="")
        result = _patch_commit_hash(bp, state)
        assert result == 0

    def test_preserves_existing_source_dict(self) -> None:
        bp: dict[str, Any] = {"source": {"url": "https://github.com/example/repo"}}
        state = make_state(commit_hash="abc123")
        _patch_commit_hash(bp, state)
        assert bp["source"]["url"] == "https://github.com/example/repo"
        assert bp["source"]["commit_hash"] == "abc123"

    def test_creates_source_dict_when_absent(self) -> None:
        bp: dict[str, Any] = {}
        state = make_state(commit_hash="cafe1234")
        _patch_commit_hash(bp, state)
        assert isinstance(bp["source"], dict)


# ---------------------------------------------------------------------------
# P2 _patch_sop_version
# ---------------------------------------------------------------------------


class TestPatchSopVersion:
    def test_forces_version_34(self) -> None:
        bp: dict[str, Any] = {}
        result = _patch_sop_version(bp)
        assert result == 1
        assert bp["sop_version"] == "3.4"

    def test_overwrites_existing_version(self) -> None:
        bp: dict[str, Any] = {"sop_version": "2.0"}
        _patch_sop_version(bp)
        assert bp["sop_version"] == "3.4"


# ---------------------------------------------------------------------------
# P3 _patch_bd_injection
# ---------------------------------------------------------------------------


class TestPatchBdInjection:
    def test_injects_all_bds(self, tmp_path: Path) -> None:
        bp: dict[str, Any] = {}
        bd_result = make_bd_result(n_present=5, n_missing=3)
        result = _patch_bd_injection(bp, bd_result, tmp_path)
        assert result == 8  # 5 present + 3 missing
        assert len(bp["business_decisions"]) == 8

    def test_present_bds_no_status_field(self, tmp_path: Path) -> None:
        bp: dict[str, Any] = {}
        bd_result = make_bd_result(n_present=3, n_missing=3)
        _patch_bd_injection(bp, bd_result, tmp_path)
        present_bds = [d for d in bp["business_decisions"] if d.get("status") != "missing"]
        for bd in present_bds:
            assert "known_gap" not in bd

    def test_missing_bds_have_known_gap(self, tmp_path: Path) -> None:
        bp: dict[str, Any] = {}
        bd_result = make_bd_result(n_present=3, n_missing=3)
        _patch_bd_injection(bp, bd_result, tmp_path)
        missing_bds = [d for d in bp["business_decisions"] if d.get("status") == "missing"]
        assert len(missing_bds) == 3
        for bd in missing_bds:
            assert bd["known_gap"] is True

    def test_ensures_minimum_3_missing_gaps(self, tmp_path: Path) -> None:
        """When bd_result has fewer missing in decisions, still enforce minimum."""
        bd_result = make_bd_result(n_present=5, n_missing=3)
        bp: dict[str, Any] = {}
        _patch_bd_injection(bp, bd_result, tmp_path)
        missing_count = sum(1 for d in bp["business_decisions"] if d.get("status") == "missing")
        assert missing_count >= 3

    def test_no_duplicate_ids(self, tmp_path: Path) -> None:
        bp: dict[str, Any] = {}
        bd_result = make_bd_result(n_present=5, n_missing=3)
        _patch_bd_injection(bp, bd_result, tmp_path)
        ids = [d["id"] for d in bp["business_decisions"]]
        assert len(ids) == len(set(ids))

    def test_alternative_considered_preserved(self, tmp_path: Path) -> None:
        bd = make_bd(bd_id="BD-001", alternative_considered="We considered trailing stop instead.")
        bd_result = BDExtractionResult(
            decisions=[bd],
            type_summary={"B": 1},
            missing_gaps=[],
        )
        bp: dict[str, Any] = {}
        _patch_bd_injection(bp, bd_result, tmp_path)
        injected = bp["business_decisions"][0]
        assert injected["alternative_considered"] == "We considered trailing stop instead."


# ---------------------------------------------------------------------------
# P4 _patch_bd_type_enum_fix
# ---------------------------------------------------------------------------


class TestPatchBdTypeEnumFix:
    def _make_bp_with_types(self, *types: str) -> dict[str, Any]:
        return {
            "business_decisions": [
                {
                    "id": f"BD-{i:03d}",
                    "type": t,
                    "content": "x",
                    "rationale": "y",
                    "evidence": "f.py:1(fn)",
                    "stage": "s",
                }
                for i, t in enumerate(types, 1)
            ]
        }

    def test_bd_type_fixes_common_misspellings(self) -> None:
        bp = self._make_bp_with_types("Business", "Math", "Regulatory")
        count = _patch_bd_type_enum_fix(bp)
        assert count == 3
        types = [d["type"] for d in bp["business_decisions"]]
        assert types == ["B", "M", "RC"]

    def test_bd_type_fixes_lowercase_variants(self) -> None:
        bp = self._make_bp_with_types("business", "math", "technical")
        count = _patch_bd_type_enum_fix(bp)
        assert count == 3
        types = [d["type"] for d in bp["business_decisions"]]
        assert types == ["B", "M", "T"]

    def test_bd_type_fixes_precedence_combos(self) -> None:
        bp = self._make_bp_with_types("B/T", "T/B", "M/T", "T/M")
        count = _patch_bd_type_enum_fix(bp)
        assert count == 4
        types = [d["type"] for d in bp["business_decisions"]]
        assert types == ["B", "B", "M", "M"]

    def test_bd_type_fixes_domain_knowledge_variants(self) -> None:
        bp = self._make_bp_with_types("DomainKnowledge", "domain_knowledge")
        count = _patch_bd_type_enum_fix(bp)
        assert count == 2
        types = [d["type"] for d in bp["business_decisions"]]
        assert types == ["DK", "DK"]

    def test_bd_type_leaves_valid_types_untouched(self) -> None:
        valid_types = ["B", "BA", "M", "DK", "RC", "T", "B/BA", "M/DK", "B/BA/DK"]
        bp = self._make_bp_with_types(*valid_types)
        count = _patch_bd_type_enum_fix(bp)
        # None of the valid types should be in the fix map
        assert count == 0
        types = [d["type"] for d in bp["business_decisions"]]
        assert types == valid_types

    def test_bd_type_warns_on_unknown(self, caplog: pytest.LogCaptureFixture) -> None:
        """Unknown types not in fix map and not matching pattern: warn only, no modify."""
        bp = self._make_bp_with_types("TOTALLY_INVALID_TYPE")
        import logging

        with caplog.at_level(
            logging.WARNING, logger="doramagic_extraction_agent.sop.blueprint_enrich"
        ):
            count = _patch_bd_type_enum_fix(bp)
        assert count == 0
        # Type left untouched
        assert bp["business_decisions"][0]["type"] == "TOTALLY_INVALID_TYPE"
        # Warning logged
        assert any("unrecognised type" in record.message for record in caplog.records)

    def test_all_fix_map_entries_produce_valid_types(self) -> None:
        """Every mapped value in BD_TYPE_ENUM_FIX_MAP must be a canonical type."""
        import re

        valid_re = re.compile(r"^(T|B|BA|DK|RC|M)(/(?:T|B|BA|DK|RC|M))*$")
        for raw, fixed in BD_TYPE_ENUM_FIX_MAP.items():
            if fixed:  # empty string sentinels are skipped
                assert valid_re.match(fixed), (
                    f"Fix map value {fixed!r} (from {raw!r}) is not canonical"
                )

    def test_skips_non_dict_entries(self) -> None:
        bp: dict[str, Any] = {"business_decisions": ["not-a-dict", None, 42]}
        count = _patch_bd_type_enum_fix(bp)
        assert count == 0


# ---------------------------------------------------------------------------
# P5 _patch_evidence_format
# ---------------------------------------------------------------------------


class TestPatchEvidenceFormat:
    def _make_bp_with_evidence(self, *evidences: str) -> dict[str, Any]:
        return {
            "business_decisions": [
                {
                    "id": f"BD-{i:03d}",
                    "type": "B",
                    "content": "x",
                    "rationale": "y",
                    "evidence": ev,
                    "stage": "s",
                }
                for i, ev in enumerate(evidences, 1)
            ]
        }

    def test_evidence_already_valid(self) -> None:
        bp = self._make_bp_with_evidence("foo.py:42(bar)")
        count = _patch_evidence_format(bp)
        assert count == 0
        assert bp["business_decisions"][0]["evidence"] == "foo.py:42(bar)"

    def test_evidence_repairs_missing_fn(self) -> None:
        bp = self._make_bp_with_evidence("foo.py:42")
        count = _patch_evidence_format(bp)
        assert count == 1
        ev = bp["business_decisions"][0]["evidence"]
        assert ev == "foo.py:42(module)"

    def test_evidence_extracts_fn_from_trailing_parens(self) -> None:
        """file.py:42 (some_function) → file.py:42(some_function)."""
        bp = self._make_bp_with_evidence("foo.py:42 (my_func)")
        _patch_evidence_format(bp)
        ev = bp["business_decisions"][0]["evidence"]
        assert ev == "foo.py:42(my_func)"

    def test_evidence_extracts_fn_from_trailing_word(self) -> None:
        """file.py:42 — word_after_dash → file.py:42(word_after_dash)."""
        bp = self._make_bp_with_evidence("foo.py:42 — calc_return")
        _patch_evidence_format(bp)
        ev = bp["business_decisions"][0]["evidence"]
        assert ev == "foo.py:42(calc_return)"

    def test_evidence_replaces_non_py(self) -> None:
        bp = self._make_bp_with_evidence("some text without python reference")
        count = _patch_evidence_format(bp)
        assert count == 1
        ev = bp["business_decisions"][0]["evidence"]
        assert ev == "N/A:0(see_rationale)"

    def test_evidence_replaces_plain_description(self) -> None:
        bp = self._make_bp_with_evidence("Hardcoded in strategy logic")
        _patch_evidence_format(bp)
        ev = bp["business_decisions"][0]["evidence"]
        assert ev == "N/A:0(see_rationale)"

    def test_evidence_coverage_ratio_all_valid(self) -> None:
        bp = self._make_bp_with_evidence("a.py:1(fn1)", "b.py:2(fn2)", "c.py:3(fn3)")
        _patch_evidence_format(bp)
        ratio = bp["_enrich_meta"]["evidence_coverage_ratio"]
        assert ratio == 1.0

    def test_evidence_coverage_ratio_mixed(self) -> None:
        # 2 valid, 1 sentinel (case 3)
        bp = self._make_bp_with_evidence("a.py:1(fn1)", "b.py:2(fn2)", "not python ref")
        _patch_evidence_format(bp)
        ratio = bp["_enrich_meta"]["evidence_coverage_ratio"]
        # 2 valid out of 3 total; case-2 repairs count as valid
        assert ratio == pytest.approx(2 / 3, abs=0.01)

    def test_evidence_coverage_ratio_all_repaired(self) -> None:
        # Case 2: all have .py:line but missing fn → fixed, counted as valid
        bp = self._make_bp_with_evidence("a.py:10", "b.py:20", "c.py:30")
        _patch_evidence_format(bp)
        ratio = bp["_enrich_meta"]["evidence_coverage_ratio"]
        assert ratio == 1.0

    def test_evidence_coverage_ratio_none_valid(self) -> None:
        bp = self._make_bp_with_evidence("foo", "bar", "baz")
        _patch_evidence_format(bp)
        ratio = bp["_enrich_meta"]["evidence_coverage_ratio"]
        assert ratio == 0.0

    def test_evidence_coverage_ratio_empty_list(self) -> None:
        bp: dict[str, Any] = {"business_decisions": []}
        _patch_evidence_format(bp)
        ratio = bp["_enrich_meta"]["evidence_coverage_ratio"]
        assert ratio == 0.0

    def test_coverage_ratio_stored_rounded(self) -> None:
        """Ratio should be rounded to 3 decimal places."""
        bp = self._make_bp_with_evidence("a.py:1(f)", "b.py:2(g)", "bad text")
        _patch_evidence_format(bp)
        ratio = bp["_enrich_meta"]["evidence_coverage_ratio"]
        # 2/3 = 0.6666... → 0.667
        assert ratio == round(2 / 3, 3)


# ---------------------------------------------------------------------------
# P6 _patch_vague_words
# ---------------------------------------------------------------------------


class TestPatchVagueWords:
    def _make_bp_with_rationales(self, *rationales: str) -> dict[str, Any]:
        return {
            "business_decisions": [
                {
                    "id": f"BD-{i:03d}",
                    "rationale": r,
                    "type": "B",
                    "content": "x",
                    "evidence": "f.py:1(fn)",
                    "stage": "s",
                }
                for i, r in enumerate(rationales, 1)
            ]
        }

    def test_vague_words_chinese_jianyi(self) -> None:
        bp = self._make_bp_with_rationales("建议使用止损以控制风险，当市场剧烈波动时失效。")
        count = _patch_vague_words(bp)
        assert count == 1
        assert bp["business_decisions"][0]["vague_rationale"] is True

    def test_vague_words_chinese_kaolv(self) -> None:
        bp = self._make_bp_with_rationales("考虑市场流动性，流动性不足时会出现问题。")
        count = _patch_vague_words(bp)
        assert count == 1
        assert bp["business_decisions"][0].get("vague_rationale") is True

    def test_vague_words_chinese_zhengque(self) -> None:
        bp = self._make_bp_with_rationales("适当调整仓位，极端行情下可能失效。")
        count = _patch_vague_words(bp)
        assert count == 1

    def test_vague_words_english_try_to(self) -> None:
        """'try to' in rationale → vague_rationale=True."""
        bp = self._make_bp_with_rationales(
            "We try to minimise slippage. This breaks under high volatility."
        )
        count = _patch_vague_words(bp)
        assert count == 1
        assert bp["business_decisions"][0]["vague_rationale"] is True

    def test_vague_words_english_consider(self) -> None:
        bp = self._make_bp_with_rationales(
            "Consider market impact when sizing positions. Breaks at low liquidity."
        )
        count = _patch_vague_words(bp)
        assert count == 1

    def test_vague_words_english_if_possible(self) -> None:
        bp = self._make_bp_with_rationales(
            "Avoid overnight positions if possible. Fails on forced holds."
        )
        count = _patch_vague_words(bp)
        assert count == 1

    def test_vague_words_case_insensitive(self) -> None:
        """English vague words matched case-insensitively."""
        bp = self._make_bp_with_rationales(
            "TRY TO avoid holding during earnings. Breaks on surprise announcements."
        )
        count = _patch_vague_words(bp)
        assert count == 1

    def test_no_vague_words(self) -> None:
        bp = self._make_bp_with_rationales(
            "The 2% stop-loss cap was chosen to limit tail risk per position. "
            "It fails when intraday gaps exceed the threshold before the order fires."
        )
        count = _patch_vague_words(bp)
        assert count == 0
        assert "vague_rationale" not in bp["business_decisions"][0]

    def test_multiple_bds_only_vague_tagged(self) -> None:
        bp = self._make_bp_with_rationales(
            "建议使用止损以控制风险，当市场剧烈波动时失效。",  # vague
            "Fixed 2% threshold was chosen for regulatory compliance. Fails above max position.",  # clean
            "We try to size positions dynamically. Breaks under illiquid conditions.",  # vague
        )
        count = _patch_vague_words(bp)
        assert count == 2
        assert bp["business_decisions"][0].get("vague_rationale") is True
        assert "vague_rationale" not in bp["business_decisions"][1]
        assert bp["business_decisions"][2].get("vague_rationale") is True

    def test_empty_rationale_skipped(self) -> None:
        bp: dict[str, Any] = {"business_decisions": [{"id": "BD-001", "rationale": ""}]}
        count = _patch_vague_words(bp)
        assert count == 0

    def test_absent_rationale_skipped(self) -> None:
        bp: dict[str, Any] = {"business_decisions": [{"id": "BD-001"}]}
        count = _patch_vague_words(bp)
        assert count == 0


# ---------------------------------------------------------------------------
# P7 _patch_stage_id_validation
# ---------------------------------------------------------------------------


class TestPatchStageIdValidation:
    def test_dedup_stage_ids(self) -> None:
        bp: dict[str, Any] = {
            "stages": [
                {"id": "risk_management", "order": 1},
                {"id": "risk_management", "order": 2},  # duplicate
                {"id": "cost_modeling", "order": 3},
            ],
            "business_decisions": [],
        }
        count = _patch_stage_id_validation(bp)
        assert count >= 1
        ids = [s["id"] for s in bp["stages"]]
        assert "risk_management" in ids
        assert "risk_management_2" in ids
        assert ids.count("risk_management") == 1

    def test_dedup_triple_duplicate(self) -> None:
        bp: dict[str, Any] = {
            "stages": [
                {"id": "trading_signal", "order": 1},
                {"id": "trading_signal", "order": 2},
                {"id": "trading_signal", "order": 3},
            ],
            "business_decisions": [],
        }
        _patch_stage_id_validation(bp)
        ids = [s["id"] for s in bp["stages"]]
        assert "trading_signal" in ids
        assert "trading_signal_2" in ids
        assert "trading_signal_3" in ids

    def test_reorder_stages_non_increasing(self) -> None:
        bp: dict[str, Any] = {
            "stages": [
                {"id": "a", "order": 3},
                {"id": "b", "order": 1},  # out of order
                {"id": "c", "order": 2},
            ],
            "business_decisions": [],
        }
        count = _patch_stage_id_validation(bp)
        assert count >= 1
        orders = [s["order"] for s in bp["stages"]]
        assert orders == [1, 2, 3]

    def test_reorder_stages_with_equal_orders(self) -> None:
        bp: dict[str, Any] = {
            "stages": [
                {"id": "a", "order": 1},
                {"id": "b", "order": 1},  # equal, not strictly increasing
                {"id": "c", "order": 2},
            ],
            "business_decisions": [],
        }
        _patch_stage_id_validation(bp)
        orders = [s["order"] for s in bp["stages"]]
        # Should be renumbered to strictly increasing
        for i in range(len(orders) - 1):
            assert orders[i] < orders[i + 1]

    def test_bd_stage_mapping_via_stage_mapping(self) -> None:
        """BD referencing a known alias gets mapped to canonical stage id."""
        bp: dict[str, Any] = {
            "stages": [
                {"id": "risk_management", "order": 1},
            ],
            "business_decisions": [
                {
                    "id": "BD-001",
                    "stage": "position_control",  # alias → risk_management
                    "type": "B",
                    "content": "x",
                    "rationale": "y",
                    "evidence": "f.py:1(fn)",
                }
            ],
        }
        count = _patch_stage_id_validation(bp)
        assert count >= 1
        assert bp["business_decisions"][0]["stage"] == "risk_management"

    def test_bd_stage_mapping_signal_to_signal(self) -> None:
        bp: dict[str, Any] = {
            "stages": [{"id": "trading_signal", "order": 1}],
            "business_decisions": [
                {
                    "id": "BD-001",
                    "stage": "signal_generation",  # alias → trading_signal
                    "type": "B",
                    "content": "x",
                    "rationale": "y",
                    "evidence": "f.py:1(fn)",
                }
            ],
        }
        _patch_stage_id_validation(bp)
        assert bp["business_decisions"][0]["stage"] == "trading_signal"

    def test_bd_stage_valid_no_change(self) -> None:
        bp: dict[str, Any] = {
            "stages": [{"id": "risk_management", "order": 1}],
            "business_decisions": [
                {
                    "id": "BD-001",
                    "stage": "risk_management",  # already valid
                    "type": "B",
                    "content": "x",
                    "rationale": "y",
                    "evidence": "f.py:1(fn)",
                }
            ],
        }
        count = _patch_stage_id_validation(bp)
        assert count == 0
        assert bp["business_decisions"][0]["stage"] == "risk_management"

    def test_bd_stage_unknown_warns_and_leaves_untouched(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A stage ref that cannot be resolved via STAGE_MAPPING → warning only."""
        bp: dict[str, Any] = {
            "stages": [{"id": "risk_management", "order": 1}],
            "business_decisions": [
                {
                    "id": "BD-999",
                    "stage": "completely_made_up_stage",
                    "type": "B",
                    "content": "x",
                    "rationale": "y",
                    "evidence": "f.py:1(fn)",
                }
            ],
        }
        import logging

        with caplog.at_level(
            logging.WARNING, logger="doramagic_extraction_agent.sop.blueprint_enrich"
        ):
            _patch_stage_id_validation(bp)
        # Stage left unchanged
        assert bp["business_decisions"][0]["stage"] == "completely_made_up_stage"
        # Warning logged
        assert any("unresolvable stage" in record.message for record in caplog.records)

    def test_empty_stages_returns_zero(self) -> None:
        bp: dict[str, Any] = {"stages": [], "business_decisions": []}
        count = _patch_stage_id_validation(bp)
        assert count == 0

    def test_non_list_stages_returns_zero(self) -> None:
        bp: dict[str, Any] = {"stages": "not-a-list", "business_decisions": []}
        count = _patch_stage_id_validation(bp)
        assert count == 0


# ---------------------------------------------------------------------------
# P8 _patch_required_methods
# ---------------------------------------------------------------------------


class TestPatchRequiredMethods:
    def test_populates_placeholder_when_no_methods(self) -> None:
        bp: dict[str, Any] = {"stages": [{"id": "s1", "order": 1}]}
        count = _patch_required_methods(bp)
        assert count == 1
        assert bp["stages"][0]["required_methods"] == [
            {
                "name": "N/A",
                "description": "No user-facing methods identified by assembly",
                "evidence": "N/A",
            }
        ]

    def test_skips_when_instructor_populated(self) -> None:
        """P8 should NOT overwrite methods that Instructor already populated."""
        bp: dict[str, Any] = {
            "stages": [
                {
                    "id": "s1",
                    "order": 1,
                    "required_methods": [
                        {
                            "name": "Factor.compute",
                            "description": "Main compute",
                            "evidence": "src/f.py:42(compute)",
                        }
                    ],
                    "key_behaviors": [
                        {
                            "behavior": "Entity isolation",
                            "description": "Each entity independent",
                            "evidence": "src/f.py:50",
                        }
                    ],
                }
            ]
        }
        count = _patch_required_methods(bp)
        assert count == 0
        assert bp["stages"][0]["required_methods"][0]["name"] == "Factor.compute"

    def test_populates_key_behaviors_placeholder(self) -> None:
        bp: dict[str, Any] = {"stages": [{"id": "s1", "order": 1}]}
        _patch_required_methods(bp)
        assert bp["stages"][0]["key_behaviors"] == [
            {
                "behavior": "N/A",
                "description": "No observable behaviors identified by assembly",
                "evidence": "N/A",
            }
        ]

    def test_parses_acceptance_hints(self) -> None:
        bp: dict[str, Any] = {
            "stages": [
                {
                    "id": "s1",
                    "order": 1,
                    "acceptance_hints": "✓ Position size capped at 5% of portfolio\n- Stop-loss fires within 100ms",
                }
            ]
        }
        _patch_required_methods(bp)
        behaviors = bp["stages"][0]["key_behaviors"]
        behavior_texts = [b["behavior"] for b in behaviors]
        assert any("Position size" in t or "Stop-loss" in t for t in behavior_texts)

    def test_skips_stages_with_existing_methods(self) -> None:
        existing_methods = [{"name": "my_method", "description": "existing", "evidence": "x"}]
        bp: dict[str, Any] = {
            "stages": [{"id": "s1", "order": 1, "required_methods": existing_methods}]
        }
        _patch_required_methods(bp)
        assert bp["stages"][0]["required_methods"] == existing_methods

    def test_empty_stages_returns_zero(self) -> None:
        bp: dict[str, Any] = {"stages": []}
        count = _patch_required_methods(bp)
        assert count == 0


# ---------------------------------------------------------------------------
# P9 _patch_uc_merge
# ---------------------------------------------------------------------------


class TestPatchUcMerge:
    def test_merges_new_ucs_from_file(self, tmp_path: Path) -> None:
        uc_list = [
            {"source": "examples/strat_a.py", "name": "Strategy A", "uc_type": "trading_strategy"},
            {"source": "examples/strat_b.py", "name": "Strategy B", "uc_type": "screening"},
        ]
        (tmp_path / "uc_list.json").write_text(json.dumps(uc_list), encoding="utf-8")
        bp: dict[str, Any] = {"known_use_cases": []}
        count = _patch_uc_merge(bp, tmp_path)
        assert count == 2
        assert len(bp["known_use_cases"]) == 2

    def test_deduplicates_by_source(self, tmp_path: Path) -> None:
        uc_list = [{"source": "examples/strat_a.py", "name": "Strategy A"}]
        (tmp_path / "uc_list.json").write_text(json.dumps(uc_list), encoding="utf-8")
        bp: dict[str, Any] = {
            "known_use_cases": [{"source": "examples/strat_a.py", "name": "Already there"}]
        }
        count = _patch_uc_merge(bp, tmp_path)
        assert count == 0
        assert len(bp["known_use_cases"]) == 1

    def test_skips_missing_uc_list(self, tmp_path: Path) -> None:
        bp: dict[str, Any] = {"known_use_cases": []}
        count = _patch_uc_merge(bp, tmp_path)
        assert count == 0

    def test_handles_malformed_json(self, tmp_path: Path) -> None:
        (tmp_path / "uc_list.json").write_text("{not valid json}", encoding="utf-8")
        bp: dict[str, Any] = {}
        count = _patch_uc_merge(bp, tmp_path)
        assert count == 0

    def test_coerces_null_known_use_cases(self, tmp_path: Path) -> None:
        uc_list = [{"source": "examples/a.py", "name": "A"}]
        (tmp_path / "uc_list.json").write_text(json.dumps(uc_list), encoding="utf-8")
        bp: dict[str, Any] = {"known_use_cases": None}
        count = _patch_uc_merge(bp, tmp_path)
        assert count == 1
        assert isinstance(bp["known_use_cases"], list)

    def test_supports_legacy_source_file_key_for_dedup(self, tmp_path: Path) -> None:
        uc_list = [{"source": "examples/strat_a.py", "name": "A"}]
        (tmp_path / "uc_list.json").write_text(json.dumps(uc_list), encoding="utf-8")
        bp: dict[str, Any] = {
            "known_use_cases": [{"source_file": "examples/strat_a.py", "name": "Already"}]
        }
        count = _patch_uc_merge(bp, tmp_path)
        assert count == 0


# ---------------------------------------------------------------------------
# P10 _patch_uc_normalize
# ---------------------------------------------------------------------------


class TestPatchUcNormalize:
    def test_renames_source_file_to_source(self) -> None:
        bp: dict[str, Any] = {
            "known_use_cases": [
                {"source_file": "examples/a.py", "name": "Strategy A", "intent_keywords": ["kw"]}
            ]
        }
        count = _patch_uc_normalize(bp)
        assert count == 1
        uc = bp["known_use_cases"][0]
        assert "source" in uc
        assert "source_file" not in uc
        assert uc["source"] == "examples/a.py"

    def test_auto_generates_intent_keywords(self) -> None:
        bp: dict[str, Any] = {
            "known_use_cases": [
                {
                    "source": "examples/macd_strategy.py",
                    "name": "MACD Trading Strategy",
                    "business_problem": "Identify trend reversals",
                }
            ]
        }
        count = _patch_uc_normalize(bp)
        assert count == 1
        keywords = bp["known_use_cases"][0]["intent_keywords"]
        assert isinstance(keywords, list)
        assert len(keywords) >= 1

    def test_does_not_overwrite_existing_intent_keywords(self) -> None:
        bp: dict[str, Any] = {
            "known_use_cases": [
                {
                    "source": "examples/a.py",
                    "name": "Strategy",
                    "intent_keywords": ["custom", "keywords"],
                }
            ]
        }
        count = _patch_uc_normalize(bp)
        assert count == 0
        assert bp["known_use_cases"][0]["intent_keywords"] == ["custom", "keywords"]

    def test_keywords_capped_at_five(self) -> None:
        bp: dict[str, Any] = {
            "known_use_cases": [
                {
                    "source": "examples/a.py",
                    "name": "MACD RSI Bollinger Strategy Alpha",
                    "business_problem": "Combine multiple signals momentum reversal breakout",
                }
            ]
        }
        _patch_uc_normalize(bp)
        keywords = bp["known_use_cases"][0]["intent_keywords"]
        assert len(keywords) <= 5

    def test_empty_uc_list(self) -> None:
        bp: dict[str, Any] = {"known_use_cases": []}
        count = _patch_uc_normalize(bp)
        assert count == 0


# ---------------------------------------------------------------------------
# P11 _patch_audit_checklist
# ---------------------------------------------------------------------------


class TestPatchAuditChecklist:
    def test_generates_when_absent(self, tmp_path: Path) -> None:
        bp: dict[str, Any] = {}
        state = make_state(subdomain_labels=["TRD", "QNT"])
        count = _patch_audit_checklist(bp, state, tmp_path)
        assert count == 1
        assert "audit_checklist_summary" in bp
        assert bp["audit_checklist_summary"]["sop_version"] == "3.4"
        assert bp["audit_checklist_summary"]["subdomain_labels"] == ["TRD", "QNT"]

    def test_skips_when_present(self, tmp_path: Path) -> None:
        bp: dict[str, Any] = {"audit_checklist_summary": {"already": "here"}}
        state = make_state()
        count = _patch_audit_checklist(bp, state, tmp_path)
        assert count == 0
        assert bp["audit_checklist_summary"] == {"already": "here"}

    def test_uses_default_subdomain_when_none(self, tmp_path: Path) -> None:
        bp: dict[str, Any] = {}
        state = make_state(subdomain_labels=[])
        _patch_audit_checklist(bp, state, tmp_path)
        labels = bp["audit_checklist_summary"]["subdomain_labels"]
        assert labels == ["TRD"]

    def test_parses_real_audit_data(self, tmp_path: Path) -> None:
        """When worker_audit.md exists, parse pass/warn/fail counts from it."""
        audit_md = (
            "| 1 | as-of time | ✅ | file:1 |\n"
            "| 2 | calendar | ⚠️ | file:2 |\n"
            "| 3 | timezone | ❌ | not found |\n"
        )
        (tmp_path / "worker_audit.md").write_text(audit_md, encoding="utf-8")
        bp: dict[str, Any] = {}
        state = make_state(subdomain_labels=["TRD"])
        count = _patch_audit_checklist(bp, state, tmp_path)
        assert count == 1
        summary = bp["audit_checklist_summary"]
        assert summary["finance_universal"]["pass"] == 1
        assert summary["finance_universal"]["warn"] == 1
        assert summary["finance_universal"]["fail"] == 1
        assert summary["note"] == "Parsed from worker_audit.md"


# ---------------------------------------------------------------------------
# P12 _patch_relations
# ---------------------------------------------------------------------------


class TestPatchRelations:
    def test_injects_placeholder_when_absent(self) -> None:
        bp: dict[str, Any] = {}
        count = _patch_relations(bp)
        assert count == 1
        assert isinstance(bp["relations"], list)
        assert len(bp["relations"]) == 1
        assert bp["relations"][0]["type"] == "pending"

    def test_skips_when_already_present(self) -> None:
        existing = [{"target": "other-bp", "type": "depends_on"}]
        bp: dict[str, Any] = {"relations": existing}
        count = _patch_relations(bp)
        assert count == 0
        assert bp["relations"] == existing

    def test_injects_when_empty_list(self) -> None:
        bp: dict[str, Any] = {"relations": []}
        count = _patch_relations(bp)
        assert count == 1


# ---------------------------------------------------------------------------
# P13 _patch_execution_paradigm
# ---------------------------------------------------------------------------


class TestPatchExecutionParadigm:
    def test_injects_placeholder_when_absent(self) -> None:
        bp: dict[str, Any] = {}
        count = _patch_execution_paradigm(bp)
        assert count == 1
        assert "execution_paradigm" in bp
        assert bp["execution_paradigm"]["live"] == "unknown"
        assert bp["execution_paradigm"]["backtest"] == "unknown"

    def test_skips_when_already_present(self) -> None:
        existing = {"live": "event-driven", "backtest": "vectorised"}
        bp: dict[str, Any] = {"execution_paradigm": existing}
        count = _patch_execution_paradigm(bp)
        assert count == 0
        assert bp["execution_paradigm"] == existing

    def test_injects_when_empty_dict(self) -> None:
        bp: dict[str, Any] = {"execution_paradigm": {}}
        count = _patch_execution_paradigm(bp)
        assert count == 1


# ---------------------------------------------------------------------------
# enrich_blueprint — end-to-end tests
# ---------------------------------------------------------------------------


class TestEnrichBlueprint:
    def test_enrich_full_pipeline(self, tmp_path: Path) -> None:
        """Run the full enrichment pipeline and verify all patches executed."""
        bp = make_blueprint()
        bd_result = make_bd_result(n_present=5, n_missing=3)
        state = make_state()

        enriched_bp, patch_stats = enrich_blueprint(bp, bd_result, state, tmp_path)

        # Returns the same object modified in-place
        assert enriched_bp is bp

        # All patch keys present
        expected_keys = {
            "p0_id",
            "p1_commit_hash",
            "p2_sop_version",
            "p3_bd_injection",
            "p4_bd_type_enum_fix",
            "p5_evidence_format",
            "p6_vague_words",
            "p7_stage_id_validation",
            "p8_required_methods",
            "p9_uc_merge",
            "p10_uc_normalize",
            "p11_audit_checklist",
            "p12_relations",
            "p13_execution_paradigm",
            "p14_resource_injection",
            "p15_missing_gaps",
            "p16_multi_type",
            "p17_absolute_words",
            "p18_uc_from_examples",
        }
        # v6: p5_5_evidence_verify is conditional (requires repo_path)
        actual_keys = set(patch_stats.keys())
        optional_keys = {"p5_5_evidence_verify"}
        assert (
            expected_keys == actual_keys - optional_keys
            or expected_keys | optional_keys == actual_keys
        )

        # P2 always fires
        assert patch_stats["p2_sop_version"] == 1
        # P3 injects BDs
        assert patch_stats["p3_bd_injection"] > 0
        # P0: id was absent → injected
        assert patch_stats["p0_id"] == 1
        # P1: valid commit_hash → injected
        assert patch_stats["p1_commit_hash"] == 1
        # P11, P12, P13: no pre-existing fields
        assert patch_stats["p11_audit_checklist"] == 1
        assert patch_stats["p12_relations"] == 1
        assert patch_stats["p13_execution_paradigm"] == 1

    def test_enrich_sets_sop_version(self, tmp_path: Path) -> None:
        bp = make_blueprint()
        bd_result = make_bd_result()
        state = make_state()
        enrich_blueprint(bp, bd_result, state, tmp_path)
        assert bp["sop_version"] == "3.4"

    def test_enrich_injects_id(self, tmp_path: Path) -> None:
        bp = make_blueprint()
        bd_result = make_bd_result()
        state = make_state(blueprint_id="bp-finance-007")
        enrich_blueprint(bp, bd_result, state, tmp_path)
        assert bp["id"] == "bp-finance-007"

    def test_enrich_preserves_existing_fields(self, tmp_path: Path) -> None:
        """Fields already set in bp must not be overwritten by scaffolding patches."""
        existing_relations = [{"target": "bp-finance-001", "type": "sibling"}]
        existing_paradigm = {"live": "event-driven", "backtest": "vectorised"}
        existing_audit = {"sop_version": "3.3", "note": "manual"}

        bp = make_blueprint()
        bp["relations"] = existing_relations
        bp["execution_paradigm"] = existing_paradigm
        bp["audit_checklist_summary"] = existing_audit
        bp["id"] = "pre-existing-id"

        bd_result = make_bd_result()
        state = make_state(blueprint_id="new-id")
        _, patch_stats = enrich_blueprint(bp, bd_result, state, tmp_path)

        # Existing values preserved
        assert bp["relations"] == existing_relations
        assert bp["execution_paradigm"] == existing_paradigm
        assert bp["audit_checklist_summary"] == existing_audit
        assert bp["id"] == "pre-existing-id"

        # Scaffolding patches should return 0
        assert patch_stats["p0_id"] == 0
        assert patch_stats["p12_relations"] == 0
        assert patch_stats["p13_execution_paradigm"] == 0
        assert patch_stats["p11_audit_checklist"] == 0

    def test_enrich_returns_patch_stats_dict(self, tmp_path: Path) -> None:
        bp = make_blueprint()
        bd_result = make_bd_result()
        state = make_state()
        result = enrich_blueprint(bp, bd_result, state, tmp_path)
        assert isinstance(result, tuple)
        assert len(result) == 2
        _, patch_stats = result
        assert isinstance(patch_stats, dict)
        assert all(isinstance(v, int) for v in patch_stats.values())

    def test_enrich_with_uc_merge(self, tmp_path: Path) -> None:
        """P9 picks up uc_list.json when present in artifacts_dir."""
        uc_list = [
            {"source": "examples/macd.py", "name": "MACD Strategy"},
        ]
        (tmp_path / "uc_list.json").write_text(json.dumps(uc_list), encoding="utf-8")

        bp = make_blueprint()
        bd_result = make_bd_result()
        state = make_state()
        _, patch_stats = enrich_blueprint(bp, bd_result, state, tmp_path)

        assert patch_stats["p9_uc_merge"] == 1
        assert len(bp["known_use_cases"]) == 1

    def test_enrich_commit_hash_injected(self, tmp_path: Path) -> None:
        bp = make_blueprint()
        bd_result = make_bd_result()
        state = make_state(commit_hash="deadbeef0123456")
        enrich_blueprint(bp, bd_result, state, tmp_path)
        assert bp["source"]["commit_hash"] == "deadbeef0123456"

    def test_enrich_audit_checklist_uses_state_labels(self, tmp_path: Path) -> None:
        bp = make_blueprint()
        bd_result = make_bd_result()
        state = make_state(subdomain_labels=["TRD", "FUT", "OPT"])
        enrich_blueprint(bp, bd_result, state, tmp_path)
        assert bp["audit_checklist_summary"]["subdomain_labels"] == ["TRD", "FUT", "OPT"]

    def test_enrich_evidence_coverage_ratio_in_meta(self, tmp_path: Path) -> None:
        """_enrich_meta.evidence_coverage_ratio must be present after enrichment."""
        bp = make_blueprint()
        bd_result = make_bd_result()
        state = make_state()
        enrich_blueprint(bp, bd_result, state, tmp_path)
        assert "_enrich_meta" in bp
        assert "evidence_coverage_ratio" in bp["_enrich_meta"]
        ratio = bp["_enrich_meta"]["evidence_coverage_ratio"]
        assert 0.0 <= ratio <= 1.0

    def test_enrich_required_methods_populated_on_stages(self, tmp_path: Path) -> None:
        bp = make_blueprint()
        bd_result = make_bd_result()
        state = make_state()
        enrich_blueprint(bp, bd_result, state, tmp_path)
        for stage in bp["stages"]:
            assert "required_methods" in stage
            assert "key_behaviors" in stage


# ---------------------------------------------------------------------------
# Codex-identified bug regression tests
# ---------------------------------------------------------------------------


class TestCodexRegressions:
    """Tests for bugs found during Codex code review."""

    def test_stage_dedup_avoids_suffix_collision(self) -> None:
        """Bug: dedup could produce duplicate _2 suffixes when _2 already exists."""
        bp: dict[str, Any] = {
            "stages": [
                {"id": "risk_management", "order": 1},
                {"id": "risk_management", "order": 2},
                {"id": "risk_management_2", "order": 3},
            ],
            "business_decisions": [],
        }
        count = _patch_stage_id_validation(bp)
        ids = [s["id"] for s in bp["stages"]]
        # All ids must be unique
        assert len(ids) == len(set(ids)), f"Duplicate ids after dedup: {ids}"
        assert "risk_management" in ids
        assert "risk_management_2" in ids
        # The second duplicate should get _3 (since _2 is taken)
        assert "risk_management_3" in ids
        assert count >= 1

    def test_cross_stage_sentinel_promotes_to_global(self) -> None:
        """Bug: cross_stage mapped to '' but was treated as 'unresolvable'."""
        bp: dict[str, Any] = {
            "stages": [{"id": "risk_management", "order": 1}],
            "business_decisions": [
                {"id": "BD-001", "stage": "cross_stage"},
            ],
        }
        count = _patch_stage_id_validation(bp)
        assert bp["business_decisions"][0]["stage"] == "global"
        assert count >= 1

    def test_global_sentinel_promotes_to_global(self) -> None:
        """Bug: 'global' mapped to '' but was treated as 'unresolvable'."""
        bp: dict[str, Any] = {
            "stages": [{"id": "risk_management", "order": 1}],
            "business_decisions": [
                {"id": "BD-001", "stage": "global"},
            ],
        }
        count = _patch_stage_id_validation(bp)
        assert bp["business_decisions"][0]["stage"] == "global"

    def test_cross_substring_promotes_to_global(self) -> None:
        """Any stage containing 'cross' should be promoted to global."""
        bp: dict[str, Any] = {
            "stages": [{"id": "risk_management", "order": 1}],
            "business_decisions": [
                {"id": "BD-001", "stage": "cross_cutting_concern"},
            ],
        }
        _patch_stage_id_validation(bp)
        assert bp["business_decisions"][0]["stage"] == "global"

    def test_bd_injection_warns_on_insufficient_gaps(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Bug: second pass could never add gaps because seen_ids was exhausted."""
        import logging

        bd_result = make_bd_result(n_present=5, n_missing=1)
        bp: dict[str, Any] = {"business_decisions": []}
        with caplog.at_level(logging.WARNING):
            _patch_bd_injection(bp, bd_result, Path("/tmp"))
        missing = [d for d in bp["business_decisions"] if d.get("status") == "missing"]
        # Only 1 missing gap available — should warn, not pretend 3
        assert len(missing) == 1
        assert "only 1 missing gaps" in caplog.text


# ---------------------------------------------------------------------------
# P14 — resource_injection Bug A fix: replaceable_component → replaceable_slots
# ---------------------------------------------------------------------------


class TestPatchResourceInjectionBugA:
    """Bug A fix: replaceable_component entries must NOT appear in resources[].

    They are architecture decision points (LLM/API/DB provider choices) and
    belong in bp["replaceable_slots"], not bp["resources"].

    Ref: PRODUCT_CONSTITUTION §1.3; blueprint-extraction-sop.md L897.
    """

    def _make_worker_resource_json(self, tmp_path: Path) -> Path:
        """Write a minimal worker_resource.json with one replaceable slot
        and one external_service data source."""
        data = {
            "replaceable_resource_matrix": [
                {
                    "slot_name": "llm_provider",
                    "selection_criteria": "Choose based on cost and rate limits",
                    "default": "Gemini (GEMINI_API_KEY)",
                    "options": [
                        {
                            "name": "Gemini",
                            "traits": ["free_tier", "multilingual"],
                            "fit_for": "prototyping",
                            "not_fit_for": "production",
                        },
                        {
                            "name": "DeepSeek",
                            "traits": ["low_cost"],
                            "fit_for": "",
                            "not_fit_for": "",
                        },
                    ],
                }
            ],
            "data_sources": [
                {
                    "provider": "Yahoo Finance",
                    "data_type": "OHLCV",
                    "coverage": "US equities",
                    "auth_requirements": "none",
                }
            ],
            "external_services": [],
            "dependencies": [],
        }
        p = tmp_path / "worker_resource.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return tmp_path

    def test_replaceable_component_goes_to_replaceable_slots_not_resources(
        self, tmp_path: Path
    ) -> None:
        """Core assertion: after P14, resources[] has NO type=replaceable_component entry."""
        artifacts_dir = self._make_worker_resource_json(tmp_path)
        bp: dict[str, Any] = {"stages": []}

        injected = _patch_resource_injection(bp, artifacts_dir)

        assert injected > 0, "P14 should inject at least one entry"

        # --- resources[] must NOT contain replaceable_component ---
        resources = bp.get("resources", [])
        rc_in_resources = [r for r in resources if r.get("type") == "replaceable_component"]
        assert rc_in_resources == [], (
            f"Bug A regression: found replaceable_component entries in resources[]: "
            f"{rc_in_resources}"
        )

    def test_replaceable_component_appears_in_replaceable_slots(self, tmp_path: Path) -> None:
        """replaceable_slots[] must contain the slot injected from worker_resource.json."""
        artifacts_dir = self._make_worker_resource_json(tmp_path)
        bp: dict[str, Any] = {"stages": []}

        _patch_resource_injection(bp, artifacts_dir)

        slots = bp.get("replaceable_slots", [])
        assert slots, "bp['replaceable_slots'] should be populated by P14"
        names = [s["name"] for s in slots]
        assert "llm_provider" in names, (
            f"Expected 'llm_provider' slot in replaceable_slots, got: {names}"
        )

    def test_slot_entry_has_correct_shape(self, tmp_path: Path) -> None:
        """Each replaceable_slot entry must have: id, name, description, options, default."""
        artifacts_dir = self._make_worker_resource_json(tmp_path)
        bp: dict[str, Any] = {"stages": []}

        _patch_resource_injection(bp, artifacts_dir)

        slot = bp["replaceable_slots"][0]
        assert slot["name"] == "llm_provider"
        assert slot["description"] == "Choose based on cost and rate limits"
        assert slot["default"] == "Gemini (GEMINI_API_KEY)"
        assert len(slot["options"]) == 2
        assert slot["options"][0]["name"] == "Gemini"
        assert "free_tier" in slot["options"][0]["traits"]
        assert slot.get("id", "").startswith("slot-"), (
            f"id should start with 'slot-', got: {slot.get('id')}"
        )
        # Must NOT have 'type' key (that was the bug)
        assert "type" not in slot, (
            f"Slot entry must not carry a 'type' field (was 'replaceable_component'): {slot}"
        )

    def test_external_service_data_source_still_goes_to_resources(self, tmp_path: Path) -> None:
        """data_sources in worker_resource.json must still land in resources[] as external_service."""
        artifacts_dir = self._make_worker_resource_json(tmp_path)
        bp: dict[str, Any] = {"stages": []}

        _patch_resource_injection(bp, artifacts_dir)

        resources = bp.get("resources", [])
        ext_services = [r for r in resources if r.get("type") == "external_service"]
        assert ext_services, "data_sources should produce external_service entries in resources[]"
        names = [r["name"] for r in ext_services]
        assert "Yahoo Finance" in names

    def test_no_double_injection_when_slot_already_exists(self, tmp_path: Path) -> None:
        """If a slot name already appears in replaceable_slots, P14 must not duplicate it."""
        artifacts_dir = self._make_worker_resource_json(tmp_path)
        bp: dict[str, Any] = {
            "stages": [],
            "replaceable_slots": [
                {"id": "slot-000", "name": "llm_provider", "description": "pre-existing"}
            ],
        }

        _patch_resource_injection(bp, artifacts_dir)

        llm_slots = [s for s in bp["replaceable_slots"] if s["name"] == "llm_provider"]
        assert len(llm_slots) == 1, f"Expected exactly 1 llm_provider slot, got {len(llm_slots)}"

    def test_missing_worker_resource_json_returns_zero(self, tmp_path: Path) -> None:
        """When worker_resource.json is absent, P14 returns 0 and touches nothing."""
        bp: dict[str, Any] = {"stages": []}
        result = _patch_resource_injection(bp, tmp_path)
        assert result == 0
        assert "replaceable_slots" not in bp
        assert "resources" not in bp


# ---------------------------------------------------------------------------
# Bug B: code_example and technique_document injection
# ---------------------------------------------------------------------------


class TestPatchResourceInjectionBugB:
    """Bug B fix: resources[] must include code_example and technique_document
    entries, not only external_service and python_package.

    Sources:
      - code_example  ← uc_list.json (UC phase output, .py / .ipynb sources)
      - technique_document ← repo_index.json document_sources
    """

    def _make_worker_resource_json(self, tmp_path: Path) -> None:
        """Write a minimal worker_resource.json with empty matrix but
        non-empty external_services so the function doesn't short-circuit."""
        data: dict[str, Any] = {
            "replaceable_resource_matrix": [],
            "data_sources": [],
            "external_services": [
                {
                    "name": "SomeAPI",
                    "description": "Some external API",
                }
            ],
            "dependencies": [],
        }
        (tmp_path / "worker_resource.json").write_text(json.dumps(data), encoding="utf-8")

    def _make_uc_list_json(self, tmp_path: Path) -> None:
        """Write a uc_list.json with .py and .ipynb examples."""
        uc_list = [
            {
                "id": "UC-001",
                "name": "Stock Trading Example",
                "source": "examples/stock_trading.py",
                "type": "trading_strategy",
                "business_problem": "Automated stock trading using DRL",
                "intent_keywords": ["trading"],
                "stage": "model_training",
            },
            {
                "id": "UC-002",
                "name": "Portfolio Demo",
                "source": "examples/portfolio_demo.ipynb",
                "type": "portfolio",
                "business_problem": "Portfolio optimization demo",
                "intent_keywords": ["portfolio"],
                "stage": "risk_management",
            },
            {
                "id": "UC-003",
                "name": "Non-file UC",
                "source": "",  # empty source — should be skipped
                "type": "other",
                "business_problem": "No file source",
                "intent_keywords": [],
                "stage": "data_collection",
            },
        ]
        (tmp_path / "uc_list.json").write_text(json.dumps(uc_list), encoding="utf-8")

    def _make_repo_index_json(self, tmp_path: Path) -> None:
        """Write a repo_index.json with document_sources."""
        repo_index = {
            "files": [],
            "entry_points": [],
            "examples": [],
            "document_sources": {
                "skill_files": ["SKILL.md"],
                "claude_md": ["CLAUDE.md"],
                "agent_files": [],
            },
            "stats": {},
        }
        (tmp_path / "repo_index.json").write_text(json.dumps(repo_index), encoding="utf-8")

    def test_code_example_injected_from_uc_list(self, tmp_path: Path) -> None:
        """code_example entries must appear in resources[] from uc_list.json."""
        self._make_worker_resource_json(tmp_path)
        self._make_uc_list_json(tmp_path)
        bp: dict[str, Any] = {"stages": []}

        _patch_resource_injection(bp, tmp_path)

        resources = bp.get("resources", [])
        code_examples = [r for r in resources if r.get("type") == "code_example"]
        assert len(code_examples) == 2, (
            f"Expected 2 code_example resources (.py + .ipynb), got {len(code_examples)}"
        )

    def test_code_example_has_correct_fields(self, tmp_path: Path) -> None:
        """Each code_example resource must have id, type, name, path, description,
        used_in_stages and _source='uc_list'."""
        self._make_worker_resource_json(tmp_path)
        self._make_uc_list_json(tmp_path)
        bp: dict[str, Any] = {"stages": []}

        _patch_resource_injection(bp, tmp_path)

        resources = bp.get("resources", [])
        examples = [r for r in resources if r.get("type") == "code_example"]
        ex = examples[0]
        assert ex["id"].startswith("res-")
        assert ex["path"] == "examples/stock_trading.py"
        assert ex["name"] == "Stock Trading Example"
        assert ex["description"] == "Automated stock trading using DRL"
        assert ex["used_in_stages"] == ["model_training"]
        assert ex["_source"] == "uc_list"

    def test_empty_source_uc_not_injected(self, tmp_path: Path) -> None:
        """A use case with an empty source must NOT be converted to code_example."""
        self._make_worker_resource_json(tmp_path)
        self._make_uc_list_json(tmp_path)
        bp: dict[str, Any] = {"stages": []}

        _patch_resource_injection(tmp_path.parent if False else bp, tmp_path)

        resources = bp.get("resources", [])
        code_examples = [r for r in resources if r.get("type") == "code_example"]
        # UC-003 has empty source — must be excluded
        paths = [r["path"] for r in code_examples]
        assert "" not in paths

    def test_technique_document_injected_from_repo_index(self, tmp_path: Path) -> None:
        """technique_document entries must appear from repo_index.json document_sources."""
        self._make_worker_resource_json(tmp_path)
        self._make_repo_index_json(tmp_path)
        bp: dict[str, Any] = {"stages": []}

        _patch_resource_injection(bp, tmp_path)

        resources = bp.get("resources", [])
        tech_docs = [r for r in resources if r.get("type") == "technique_document"]
        assert len(tech_docs) == 2, (
            f"Expected 2 technique_document entries (SKILL.md + CLAUDE.md), "
            f"got {len(tech_docs)}: {tech_docs}"
        )
        paths = {r["path"] for r in tech_docs}
        assert "SKILL.md" in paths
        assert "CLAUDE.md" in paths

    def test_technique_document_has_correct_fields(self, tmp_path: Path) -> None:
        """technique_document must have id/type/name/path/description/_source."""
        self._make_worker_resource_json(tmp_path)
        self._make_repo_index_json(tmp_path)
        bp: dict[str, Any] = {"stages": []}

        _patch_resource_injection(bp, tmp_path)

        resources = bp.get("resources", [])
        td = next(r for r in resources if r.get("type") == "technique_document")
        assert td["id"].startswith("res-")
        assert td["_source"] == "repo_index"
        assert td["name"] in ("SKILL.md", "CLAUDE.md")
        assert "technique_document" in [r["type"] for r in resources]

    def test_no_duplicate_code_examples_if_already_in_resources(self, tmp_path: Path) -> None:
        """If a code_example path is already in resources[], don't re-inject it."""
        self._make_worker_resource_json(tmp_path)
        self._make_uc_list_json(tmp_path)
        pre_existing = {
            "id": "res-001",
            "type": "code_example",
            "path": "examples/stock_trading.py",
            "name": "pre-existing",
            "description": "",
            "used_in_stages": [],
        }
        bp: dict[str, Any] = {"stages": [], "resources": [pre_existing]}

        _patch_resource_injection(bp, tmp_path)

        py_examples = [r for r in bp["resources"] if r.get("path") == "examples/stock_trading.py"]
        assert len(py_examples) == 1, (
            f"Expected exactly 1 entry for stock_trading.py, got {len(py_examples)}"
        )

    def test_missing_uc_list_and_repo_index_gracefully_skipped(self, tmp_path: Path) -> None:
        """If uc_list.json and repo_index.json are absent, P14 still works."""
        self._make_worker_resource_json(tmp_path)
        # Don't create uc_list.json or repo_index.json
        bp: dict[str, Any] = {"stages": []}

        result = _patch_resource_injection(bp, tmp_path)

        # Should still inject the external_service from worker_resource.json
        assert result > 0
        resources = bp.get("resources", [])
        assert any(r.get("type") == "external_service" for r in resources)
        # Must not crash
        assert "code_example" not in {r.get("type") for r in resources}


# ---------------------------------------------------------------------------
# Bug C: resources field must not be absent when matrix is empty
# ---------------------------------------------------------------------------


class TestPatchResourceInjectionBugC:
    """Bug C fix: when replaceable_resource_matrix is empty or absent, the
    function must still populate resources[] with data_sources / external_services
    / dependencies.  Previously an empty matrix caused an early return.
    """

    def test_resources_populated_when_matrix_empty(self, tmp_path: Path) -> None:
        """Empty replaceable_resource_matrix must NOT prevent resources[] injection."""
        data: dict[str, Any] = {
            "replaceable_resource_matrix": [],  # empty — was causing early return
            "data_sources": [
                {
                    "provider": "Yahoo Finance",
                    "data_type": "OHLCV",
                    "coverage": "US equities",
                    "auth_requirements": "none",
                }
            ],
            "external_services": [],
            "dependencies": [],
        }
        (tmp_path / "worker_resource.json").write_text(json.dumps(data), encoding="utf-8")
        bp: dict[str, Any] = {"stages": []}

        result = _patch_resource_injection(bp, tmp_path)

        assert result > 0, "Injected count must be > 0 when data_sources are present"
        assert "resources" in bp, "Bug C regression: resources field absent when matrix is empty"
        ext_services = [r for r in bp["resources"] if r.get("type") == "external_service"]
        assert ext_services, "data_source entries must become external_service resources"

    def test_resources_populated_when_matrix_missing(self, tmp_path: Path) -> None:
        """Missing replaceable_resource_matrix key must not prevent resources[]."""
        data: dict[str, Any] = {
            # No 'replaceable_resource_matrix' key at all
            "data_sources": [
                {
                    "provider": "FRED",
                    "data_type": "Macroeconomic data",
                    "coverage": "US",
                    "auth_requirements": "API key",
                }
            ],
            "external_services": [{"name": "Polygon.io", "description": "US equities"}],
            "dependencies": [],
        }
        (tmp_path / "worker_resource.json").write_text(json.dumps(data), encoding="utf-8")
        bp: dict[str, Any] = {"stages": []}

        result = _patch_resource_injection(bp, tmp_path)

        assert result > 0
        assert "resources" in bp
        names = {r.get("name") for r in bp["resources"]}
        assert "FRED" in names or "Polygon.io" in names

    def test_external_services_injected_without_matrix(self, tmp_path: Path) -> None:
        """external_services must be injected even if matrix is absent/empty."""
        data: dict[str, Any] = {
            "replaceable_resource_matrix": [],
            "data_sources": [],
            "external_services": [
                {"name": "Alpaca", "description": "Trading API"},
                {"service": "IB Gateway", "purpose": "Order routing"},
            ],
            "dependencies": [],
        }
        (tmp_path / "worker_resource.json").write_text(json.dumps(data), encoding="utf-8")
        bp: dict[str, Any] = {"stages": []}

        _patch_resource_injection(bp, tmp_path)

        resources = bp.get("resources", [])
        ext = [r for r in resources if r.get("type") == "external_service"]
        assert len(ext) == 2, f"Expected 2 external_service entries, got {len(ext)}"

    def test_replaceable_slots_absent_when_matrix_empty(self, tmp_path: Path) -> None:
        """When matrix is empty, bp['replaceable_slots'] should not be set."""
        data: dict[str, Any] = {
            "replaceable_resource_matrix": [],
            "data_sources": [],
            "external_services": [],
            "dependencies": [],
        }
        (tmp_path / "worker_resource.json").write_text(json.dumps(data), encoding="utf-8")
        bp: dict[str, Any] = {"stages": []}

        _patch_resource_injection(bp, tmp_path)

        # Empty matrix → no replaceable_slots should be added
        assert bp.get("replaceable_slots", []) == []


# ---------------------------------------------------------------------------
# Bug D: audit_checklist coverage metric fix
# ---------------------------------------------------------------------------


class TestPatchAuditChecklistBugD:
    """Bug D fix: audit coverage must count EXAMINED items (pass+warn+fail),
    not only PASSED items.

    Previously: coverage = pass / total → "3/71 (4%)" for bp-009
    Correctly:  coverage = examined / total = total / total = "71/71 (100%)"
    The pass_rate field is added separately to preserve the original metric.
    """

    def _write_audit_md(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "worker_audit.md"
        p.write_text(content, encoding="utf-8")
        return p

    def test_coverage_counts_examined_not_pass_only(self, tmp_path: Path) -> None:
        """coverage = (pass+warn+fail)/total — all rows with a status are examined."""
        audit_md = (
            "## Universal Finance Checklist\n"
            "| # | Item | Status | Evidence |\n"
            "|---|------|--------|----------|\n"
            "| 1 | item1 | ✅ | file:1 |\n"
            "| 2 | item2 | ⚠️ | file:2 |\n"
            "| 3 | item3 | ❌ | not found |\n"
        )
        self._write_audit_md(tmp_path, audit_md)
        bp: dict[str, Any] = {}
        state = make_state(subdomain_labels=["TRD"])

        _patch_audit_checklist(bp, state, tmp_path)

        summary = bp["audit_checklist_summary"]
        # 3 examined out of 3 total → coverage 100%
        assert summary["coverage"] == "3/3 (100%)", (
            f"Bug D: coverage should be examined/total, got: {summary['coverage']}"
        )

    def test_pass_rate_field_added(self, tmp_path: Path) -> None:
        """pass_rate must be present and reflect only ✅ items."""
        audit_md = (
            "## Universal Finance Checklist\n"
            "| # | Item | Status | Evidence |\n"
            "|---|------|--------|----------|\n"
            "| 1 | item1 | ✅ | file:1 |\n"
            "| 2 | item2 | ⚠️ | file:2 |\n"
            "| 3 | item3 | ❌ | not found |\n"
        )
        self._write_audit_md(tmp_path, audit_md)
        bp: dict[str, Any] = {}
        state = make_state(subdomain_labels=["TRD"])

        _patch_audit_checklist(bp, state, tmp_path)

        summary = bp["audit_checklist_summary"]
        assert "pass_rate" in summary, "pass_rate field must be added by Bug D fix"
        assert summary["pass_rate"] == "1/3 (33%)", (
            f"pass_rate should be pass/total, got: {summary['pass_rate']}"
        )

    def test_coverage_not_misleadingly_low_like_zvt(self, tmp_path: Path) -> None:
        """Simulate bp-009 (zvt) scenario: 3 pass / 71 total.

        Old behavior: coverage = '3/71 (4%)' (misleadingly low)
        New behavior: coverage = '71/71 (100%)' (all items examined)
        pass_rate = '3/71 (4%)' (preserved separately)
        """
        lines = ["## Universal Finance Checklist\n"]
        lines.append("| # | Item | Status | Evidence |\n")
        lines.append("|---|------|--------|----------|\n")
        # 3 pass, 11 warn, 8 fail (universal: mimics bp-009)
        for _ in range(3):
            lines.append("| x | item | ✅ | file:1 |\n")
        for _ in range(11):
            lines.append("| x | item | ⚠️ | file:1 |\n")
        for _ in range(8):
            lines.append("| x | item | ❌ | file:1 |\n")
        # subdomain: 2 pass, 21 warn, 26 fail
        lines.append("## TRD 交易与执行\n")
        lines.append("| # | Item | Status | Evidence |\n")
        lines.append("|---|------|--------|----------|\n")
        for _ in range(2):
            lines.append("| x | item | ✅ | file:1 |\n")
        for _ in range(21):
            lines.append("| x | item | ⚠️ | file:1 |\n")
        for _ in range(26):
            lines.append("| x | item | ❌ | file:1 |\n")
        audit_content = "".join(lines)
        self._write_audit_md(tmp_path, audit_content)
        bp: dict[str, Any] = {}
        state = make_state(subdomain_labels=["TRD"])

        _patch_audit_checklist(bp, state, tmp_path)

        summary = bp["audit_checklist_summary"]
        total = 3 + 11 + 8 + 2 + 21 + 26  # 71
        assert summary["coverage"] == f"{total}/{total} (100%)", (
            f"Bug D: coverage should be 71/71 (100%), got: {summary['coverage']}"
        )
        assert "pass_rate" in summary
        total_pass = 3 + 2  # 5
        assert summary["pass_rate"] == f"{total_pass}/{total} ({total_pass * 100 // total}%)"


# ---------------------------------------------------------------------------
# P0-A fix-forward: BLOCKER 1 + CONCERN 1 + CONCERN 6 guard tests
# ---------------------------------------------------------------------------


class TestPatchResourceInjectionP0AGuards:
    """P0-A fix-forward guards: skill_files dict entries, uc_list.source non-str,
    and audit coverage 0/0 boundary.
    """

    def _make_worker_resource_json(self, tmp_path: Path) -> None:
        """Write a minimal worker_resource.json with no matrix but a placeholder service."""
        data: dict[str, Any] = {
            "replaceable_resource_matrix": [],
            "data_sources": [],
            "external_services": [{"name": "TestAPI", "description": "test"}],
            "dependencies": [],
        }
        (tmp_path / "worker_resource.json").write_text(json.dumps(data), encoding="utf-8")

    def test_skill_files_with_dict_entries_skipped_gracefully(self, tmp_path: Path) -> None:
        """BLOCKER fix: repo_index.json skill_files dict entries are skipped by isinstance guard.

        21.6% of real repo_index.json files have skill_files as list[dict].
        The isinstance guard must let str entries through and skip dicts,
        so the loop does NOT silently abort — valid str paths still produce technique_document entries.
        """
        self._make_worker_resource_json(tmp_path)
        repo_index = {
            "files": [],
            "entry_points": [],
            "examples": [],
            "document_sources": {
                # Mix: one dict (must be skipped), one str (must be injected)
                "skill_files": [{"path": "SKILL.md", "type": "doc"}, "valid_skill.md"],
                "claude_md": [],
                "agent_files": [],
            },
            "stats": {},
        }
        (tmp_path / "repo_index.json").write_text(json.dumps(repo_index), encoding="utf-8")
        bp: dict[str, Any] = {"stages": []}

        _patch_resource_injection(bp, tmp_path)

        resources = bp.get("resources", [])
        tech_docs = [r for r in resources if r.get("type") == "technique_document"]
        paths = {r["path"] for r in tech_docs}

        # dict entry skipped, str entry injected → exactly 1 technique_document
        assert len(tech_docs) == 1, (
            f"BLOCKER: expected 1 technique_document (str entry only), got {len(tech_docs)}: {tech_docs}"
        )
        assert "valid_skill.md" in paths, (
            f"BLOCKER: valid_skill.md must be injected as technique_document, got paths={paths}"
        )

    def test_uc_source_non_string_skipped_gracefully(self, tmp_path: Path) -> None:
        """CONCERN 1 fix: uc_list.source of type dict/list/None must be skipped without AttributeError.

        The isinstance(src, str) guard must prevent AttributeError on .endswith() when source
        is a non-string type (e.g. dict or list from malformed uc_list.json).
        Only str sources that end with .py or .ipynb should produce code_example entries.
        """
        self._make_worker_resource_json(tmp_path)
        uc_list = [
            {
                "id": "UC-001",
                "name": "Good Example",
                "source": "good_example.py",
                "business_problem": "Valid",
                "stage": "training",
            },
            {
                "id": "UC-002",
                "name": "Dict Source",
                "source": {"path": "bad_example.py", "type": "file"},  # dict — must be skipped
                "business_problem": "Malformed",
                "stage": "training",
            },
            {
                "id": "UC-003",
                "name": "List Source",
                "source": ["list_item.py"],  # list — must be skipped
                "business_problem": "Also malformed",
                "stage": "training",
            },
            {
                "id": "UC-004",
                "name": "None Source",
                "source": None,  # None — must be skipped
                "business_problem": "None source",
                "stage": "training",
            },
        ]
        (tmp_path / "uc_list.json").write_text(json.dumps(uc_list), encoding="utf-8")
        bp: dict[str, Any] = {"stages": []}

        # Must not raise AttributeError or TypeError
        _patch_resource_injection(bp, tmp_path)

        resources = bp.get("resources", [])
        code_examples = [r for r in resources if r.get("type") == "code_example"]
        assert len(code_examples) == 1, (
            f"CONCERN 1: expected exactly 1 code_example (good_example.py only), got {len(code_examples)}"
        )
        assert code_examples[0]["path"] == "good_example.py"

    def _write_audit_md(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "worker_audit.md"
        p.write_text(content, encoding="utf-8")
        return p

    def test_audit_coverage_total_zero_boundary(self, tmp_path: Path) -> None:
        """CONCERN 6 fix: when total_all == 0, coverage and pass_rate must be '0/0 (0%)'.

        An empty audit file with no status rows must not cause ZeroDivisionError.
        Both coverage and pass_rate must degrade gracefully to '0/0 (0%)'.
        """
        # Write audit with headers but no data rows
        audit_md = (
            "## Universal Finance Checklist\n"
            "| # | Item | Status | Evidence |\n"
            "|---|------|--------|----------|\n"
            # No data rows → total = 0
        )
        self._write_audit_md(tmp_path, audit_md)
        bp: dict[str, Any] = {}
        state = make_state(subdomain_labels=[])

        # Must not raise ZeroDivisionError
        _patch_audit_checklist(bp, state, tmp_path)

        summary = bp.get("audit_checklist_summary", {})
        coverage = summary.get("coverage", "")
        pass_rate = summary.get("pass_rate", "")

        assert coverage == "0/0 (0%)", (
            f"CONCERN 6: zero-total coverage must be '0/0 (0%)', got: {coverage!r}"
        )
        assert pass_rate == "0/0 (0%)", (
            f"CONCERN 6: zero-total pass_rate must be '0/0 (0%)', got: {pass_rate!r}"
        )
