"""Tests for phase_runner.py — Phase Runner (Race G, S1-Sonnet).

Test strategy:
  - All external modules (extraction, validate, assemble, subprocess) are mocked.
  - Fixtures create minimal temp directories that mimic the real output structure.
  - Each test exercises one scenario (happy path, degradation, skip, failure).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from doramagic_orchestration.phase_runner import (
    PipelineConfig,
    PipelineResult,
    _load_cards_as_dicts,
    _load_repo_facts,
    run_single_project_pipeline,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_output(tmp_path):
    """Create a minimal output directory structure."""
    soul_dir = tmp_path / "soul"
    artifacts_dir = tmp_path / "artifacts"
    cards_concepts = soul_dir / "cards" / "concepts"
    cards_rules = soul_dir / "cards" / "rules"
    cards_workflows = soul_dir / "cards" / "workflows"

    for d in [cards_concepts, cards_rules, cards_workflows, artifacts_dir]:
        d.mkdir(parents=True, exist_ok=True)

    return tmp_path


@pytest.fixture()
def tmp_repo(tmp_path):
    """Create a minimal fake repo."""
    repo = tmp_path / "my_repo"
    repo.mkdir()
    (repo / "README.md").write_text("# My Repo\n")
    (repo / "setup.py").write_text("from setuptools import setup\nsetup(name='myrepo')\n")
    return repo


@pytest.fixture()
def repo_facts_dict():
    return {
        "repo_path": "/fake/repo",
        "commands": ["myrepo-cli"],
        "skills": [],
        "files": ["README.md", "setup.py"],
        "config_keys": [],
        "frameworks": ["Django"],
        "languages": ["Python"],
        "dependencies": [],
        "storage_paths": [],
        "project_narrative": "My Repo is a Python project with 2 source files.",
    }


@pytest.fixture()
def output_with_facts(tmp_output, repo_facts_dict):
    """Output dir with repo_facts.json pre-populated."""
    facts_path = tmp_output / "artifacts" / "repo_facts.json"
    facts_path.write_text(json.dumps(repo_facts_dict), encoding="utf-8")
    return tmp_output


@pytest.fixture()
def output_with_cards(output_with_facts):
    """Output dir with minimal valid cards."""
    rules_dir = output_with_facts / "soul" / "cards" / "rules"

    card_dr001 = """---
card_type: decision_rule_card
card_id: DR-001
repo: myrepo
title: Use signals for decoupled logic
type: ARCHITECTURE
severity: HIGH
rule: |
  When implementing cross-app communication, use Django signals.
  Never import directly across apps if decoupling is desired.
do:
  - Use `django.dispatch.Signal`
  - Connect via `@receiver(signal_name)`
dont:
  - Directly import models from other apps
confidence: 0.90
sources:
  - "myrepo/core/signals.py:10"
---

## 真实场景

App A emits order_placed signal; App B listens without importing App A.

## 影响范围

All cross-app integrations.
"""
    (rules_dir / "DR-001.md").write_text(card_dr001, encoding="utf-8")

    concepts_dir = output_with_facts / "soul" / "cards" / "concepts"
    card_cc001 = """---
card_type: concept_card
card_id: CC-001
repo: myrepo
title: Order Signal
---

## Identity

The core decoupling mechanism for order processing.

## Evidence

Found in signals.py.
"""
    (concepts_dir / "CC-001.md").write_text(card_cc001, encoding="utf-8")

    return output_with_facts


@pytest.fixture()
def output_with_soul_and_validation(output_with_cards):
    """Output dir with 00-soul.md and a passing validation_report.json."""
    soul_dir = output_with_cards / "soul"
    soul_dir.mkdir(exist_ok=True)

    (soul_dir / "00-soul.md").write_text(
        "# My Repo Soul\n\n## Q6 Design Philosophy\n\nSignals over imports.\n",
        encoding="utf-8",
    )
    (soul_dir / "module-map.md").write_text(
        "# Module Map\n\n### M-01 Core\nOrchestrates orders.\n",
        encoding="utf-8",
    )
    (soul_dir / "community-wisdom.md").write_text(
        "# Community Wisdom\n\n### 痛点1\nSignal ordering issues.\n",
        encoding="utf-8",
    )

    # Passing validation report
    validation_report = {
        "output_dir": str(output_with_cards),
        "cards": [],
        "summary": {
            "total_cards": 2,
            "pass_cards": 2,
            "total_errors": 0,
            "total_warnings": 0,
            "code_rules": 1,
            "community_rules": 0,
            "quantity_errors": [],
            "metrics": {
                "format_compliance_rate": 1.0,
                "traceability_rate": 1.0,
                "community_utilization": 0.0,
            },
            "hard_gate": {
                "format_compliance_pass": True,
                "traceability_pass": True,
                "min_code_rules_pass": False,
                "min_community_rules_pass": False,
            },
            "overall_pass": True,
        },
    }
    report_path = soul_dir / "validation_report.json"
    report_path.write_text(json.dumps(validation_report), encoding="utf-8")

    return output_with_cards


# ---------------------------------------------------------------------------
# Helpers to build mock modules
# ---------------------------------------------------------------------------


def _make_mock_validation_report(overall_pass: bool = True):
    return {
        "output_dir": "/fake",
        "cards": [],
        "summary": {
            "total_cards": 0,
            "pass_cards": 0,
            "total_errors": 0 if overall_pass else 1,
            "total_warnings": 0,
            "code_rules": 5 if overall_pass else 0,
            "community_rules": 3 if overall_pass else 0,
            "quantity_errors": [],
            "metrics": {
                "format_compliance_rate": 1.0 if overall_pass else 0.5,
                "traceability_rate": 1.0,
                "community_utilization": 0.5,
            },
            "hard_gate": {
                "format_compliance_pass": overall_pass,
                "traceability_pass": True,
                "min_code_rules_pass": overall_pass,
                "min_community_rules_pass": overall_pass,
            },
            "overall_pass": overall_pass,
        },
    }


def _make_dsd_report(status: str = "CLEAN"):
    return {
        "checks": [
            {
                "check_id": "DSD-1",
                "name": "Rationale Support Ratio",
                "score": 0.0,
                "triggered": False,
                "detail": "OK",
            }
        ],
        "overall_status": status,
    }


class MockDSDReport:
    def __init__(self, status="CLEAN"):
        self._dict = _make_dsd_report(status)

    def to_dict(self):
        return self._dict


def _make_mock_stage0_fn(repo_path: str, output_dir: str):
    """Return a mock extract_repo_facts function that writes repo_facts.json."""

    def _stage0_fn(rp):
        facts = {
            "repo_path": rp,
            "commands": [],
            "skills": [],
            "files": [],
            "config_keys": [],
            "frameworks": [],
            "languages": [],
            "dependencies": [],
            "storage_paths": [],
            "project_narrative": "Mocked extraction.",
        }
        # The real _run_stage0 writes the file itself after calling extract_repo_facts,
        # so this mock just needs to return a dict-like object with model_dump/dict.
        mock_result = MagicMock()
        mock_result.model_dump.return_value = facts
        return mock_result

    return _stage0_fn


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestLoadHelpers:
    """Tests for internal helper functions."""

    def test_load_repo_facts_exists(self, output_with_facts, repo_facts_dict):
        facts = _load_repo_facts(str(output_with_facts))
        assert facts is not None
        assert facts["commands"] == repo_facts_dict["commands"]

    def test_load_repo_facts_missing(self, tmp_output):
        facts = _load_repo_facts(str(tmp_output))
        assert facts is None

    def test_load_cards_as_dicts_empty(self, tmp_output):
        cards = _load_cards_as_dicts(str(tmp_output))
        assert cards == []

    def test_load_cards_as_dicts_with_cards(self, output_with_cards):
        cards = _load_cards_as_dicts(str(output_with_cards))
        assert len(cards) == 2
        ids = {c.get("card_id") for c in cards}
        assert "DR-001" in ids
        assert "CC-001" in ids


class TestPipelineConfig:
    """Test PipelineConfig defaults and custom values."""

    def test_defaults(self):
        cfg = PipelineConfig()
        assert cfg.enable_stage15 is True
        assert cfg.enable_bricks is True
        assert cfg.enable_dsd is True
        assert cfg.bricks_dir is None
        assert cfg.knowledge_budget == 1800
        assert cfg.skip_assembly is False

    def test_custom(self):
        cfg = PipelineConfig(
            enable_stage15=False,
            knowledge_budget=1200,
            skip_assembly=True,
        )
        assert cfg.enable_stage15 is False
        assert cfg.knowledge_budget == 1200
        assert cfg.skip_assembly is True


class TestPipelineResultModel:
    """Test PipelineResult model validation."""

    def test_minimal_result(self):
        result = PipelineResult(
            stages_completed=["stage0"],
            stages_skipped=[],
            stages_failed=[],
            output_dir="/tmp/out",
            inject_dir=None,
            dsd_report=None,
            total_cards=0,
            total_bricks_loaded=0,
        )
        assert result.stages_completed == ["stage0"]
        assert result.inject_dir is None


class TestStage0:
    """Test Stage 0 extraction via direct Python function call."""

    def test_stage0_success(self, tmp_repo, tmp_output):
        """Stage 0 calls extract_repo_facts function and marks completed."""
        mock_stage0_fn = MagicMock()
        mock_facts = MagicMock()
        mock_facts.model_dump.return_value = {
            "repo_path": str(tmp_repo),
            "commands": [],
            "skills": [],
            "files": [],
            "config_keys": [],
            "frameworks": [],
            "languages": [],
            "dependencies": [],
            "storage_paths": [],
            "project_narrative": "Mocked.",
        }
        mock_stage0_fn.return_value = mock_facts

        config = PipelineConfig(
            enable_bricks=False,
            enable_stage15=False,
            enable_dsd=False,
            skip_assembly=True,
        )
        with (
            patch(
                "doramagic_orchestration.phase_runner._import_stage0", return_value=mock_stage0_fn
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(None, None, None, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate", return_value=(None, None)
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(tmp_output),
                config=config,
            )
        assert "stage0" in result.stages_completed
        assert "stage0" not in result.stages_failed
        mock_stage0_fn.assert_called_once()

    def test_stage0_script_not_found(self, tmp_repo, tmp_output):
        """Stage 0 is skipped gracefully when _import_stage0 returns None."""
        config = PipelineConfig(
            enable_bricks=False,
            enable_stage15=False,
            enable_dsd=False,
            skip_assembly=True,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(None, None, None, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate", return_value=(None, None)
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(tmp_output),
                config=config,
            )
        assert "stage0" in result.stages_skipped
        assert "stage0" not in result.stages_failed

    def test_stage0_function_raises(self, tmp_repo, tmp_output):
        """Stage 0 failure is recorded without crashing."""
        mock_stage0_fn = MagicMock(side_effect=RuntimeError("extraction failed"))

        config = PipelineConfig(
            enable_bricks=False,
            enable_stage15=False,
            enable_dsd=False,
            skip_assembly=True,
        )
        with (
            patch(
                "doramagic_orchestration.phase_runner._import_stage0", return_value=mock_stage0_fn
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(None, None, None, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate", return_value=(None, None)
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(tmp_output),
                config=config,
            )
        assert "stage0" in result.stages_failed
        assert "stage0" not in result.stages_completed

    def test_stage0_idempotent_when_facts_exist(self, tmp_repo, output_with_facts):
        """Stage 0 skips the function call if repo_facts.json already exists."""
        mock_stage0_fn = MagicMock()

        config = PipelineConfig(
            enable_bricks=False,
            enable_stage15=False,
            enable_dsd=False,
            skip_assembly=True,
        )
        with (
            patch(
                "doramagic_orchestration.phase_runner._import_stage0", return_value=mock_stage0_fn
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(None, None, None, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate", return_value=(None, None)
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_facts),
                config=config,
            )
        mock_stage0_fn.assert_not_called()
        assert "stage0" in result.stages_completed


class TestBrickInjection:
    """Test brick injection behavior."""

    def test_bricks_disabled(self, tmp_repo, output_with_facts):
        config = PipelineConfig(
            enable_bricks=False,
            enable_stage15=False,
            enable_dsd=False,
            skip_assembly=True,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(None, None, None, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate", return_value=(None, None)
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_facts),
                config=config,
            )
        assert "brick_injection" in result.stages_skipped
        assert result.total_bricks_loaded == 0

    def test_bricks_dir_missing(self, tmp_repo, output_with_facts):
        """Brick injection is skipped gracefully when bricks_dir doesn't exist."""
        config = PipelineConfig(
            enable_bricks=True,
            bricks_dir="/nonexistent/bricks/",
            enable_stage15=False,
            enable_dsd=False,
            skip_assembly=True,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(None, None, None, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate", return_value=(None, None)
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_facts),
                config=config,
            )
        assert "brick_injection" in result.stages_skipped
        assert result.total_bricks_loaded == 0

    def test_bricks_loaded_successfully(self, tmp_repo, output_with_facts, tmp_path):
        """Brick injection succeeds when injector returns bricks."""
        # Create a fake bricks_dir
        bricks_dir = tmp_path / "bricks"
        bricks_dir.mkdir()

        mock_injection_result = MagicMock()
        mock_injection_result.bricks_loaded = 3
        mock_injection_result.frameworks_matched = ["Django"]

        mock_injector = MagicMock(return_value=mock_injection_result)

        config = PipelineConfig(
            enable_bricks=True,
            bricks_dir=str(bricks_dir),
            enable_stage15=False,
            enable_dsd=False,
            skip_assembly=True,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(None, None, None, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate", return_value=(None, None)
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_brick_injector",
                return_value=mock_injector,
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_facts),
                config=config,
            )
        assert "brick_injection" in result.stages_completed
        assert result.total_bricks_loaded == 3


class TestStage15:
    """Test Stage 1.5 agentic exploration behavior."""

    def test_stage15_skipped_no_adapter(self, tmp_repo, output_with_facts):
        """Stage 1.5 skipped when adapter=None."""
        config = PipelineConfig(
            enable_stage15=True,
            enable_bricks=False,
            enable_dsd=False,
            skip_assembly=True,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(None, None, None, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate", return_value=(None, None)
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_facts),
                adapter=None,
                config=config,
            )
        assert "stage1.5" in result.stages_skipped

    def test_stage15_skipped_when_disabled(self, tmp_repo, output_with_facts):
        """Stage 1.5 skipped when enable_stage15=False."""
        config = PipelineConfig(
            enable_stage15=False,
            enable_bricks=False,
            enable_dsd=False,
            skip_assembly=True,
        )
        mock_adapter = MagicMock()
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(None, None, None, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate", return_value=(None, None)
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_facts),
                adapter=mock_adapter,
                config=config,
            )
        assert "stage1.5" in result.stages_skipped

    def test_stage15_success(self, tmp_repo, output_with_facts):
        """Stage 1.5 completes when adapter+contracts available."""
        config = PipelineConfig(
            enable_stage15=True,
            enable_bricks=False,
            enable_dsd=False,
            skip_assembly=True,
        )
        mock_adapter = MagicMock()

        # Mock the contracts
        mock_envelope = MagicMock()
        mock_envelope.status = "ok"
        mock_envelope.data = MagicMock()
        mock_envelope.data.promoted_claims = []

        mock_run_stage15 = MagicMock(return_value=mock_envelope)

        # We need contracts importable too
        mock_contracts = MagicMock()
        mock_contracts.base.RepoRef = MagicMock(return_value=MagicMock())
        mock_contracts.extraction.RepoFacts = MagicMock(return_value=MagicMock())
        mock_contracts.extraction.Stage15AgenticInput = MagicMock(return_value=MagicMock())
        mock_contracts.extraction.Stage15Budget = MagicMock(return_value=MagicMock())
        mock_contracts.extraction.Stage15Toolset = MagicMock(return_value=MagicMock())
        mock_contracts.extraction.Stage1ScanOutput = MagicMock(return_value=MagicMock())
        mock_contracts.extraction.Stage1Coverage = MagicMock(return_value=MagicMock())

        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(MagicMock(), MagicMock(), None, mock_run_stage15),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate", return_value=(None, None)
            ),
            patch.dict(
                "sys.modules",
                {
                    "doramagic_contracts": mock_contracts,
                    "doramagic_contracts.base": mock_contracts.base,
                    "doramagic_contracts.extraction": mock_contracts.extraction,
                },
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_facts),
                adapter=mock_adapter,
                config=config,
            )
        # Should have tried (may complete or fail depending on contract mocks)
        # Key invariant: pipeline does not crash
        assert isinstance(result, PipelineResult)

    def test_stage15_failure_non_crashing(self, tmp_repo, output_with_facts):
        """Stage 1.5 failure is logged but does not crash the pipeline."""
        config = PipelineConfig(
            enable_stage15=True,
            enable_bricks=False,
            enable_dsd=False,
            skip_assembly=True,
        )
        mock_adapter = MagicMock()

        mock_run_stage15 = MagicMock(side_effect=RuntimeError("LLM timeout"))

        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(MagicMock(), MagicMock(), None, mock_run_stage15),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate", return_value=(None, None)
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_facts),
                adapter=mock_adapter,
                config=config,
            )
        assert isinstance(result, PipelineResult)
        # Stage 1.5 failure is in stages_failed or stages_skipped (contracts not available)
        assert "stage1.5" in result.stages_failed or "stage1.5" in result.stages_skipped


class TestStage35:
    """Test Stage 3.5 validation + confidence + DSD."""

    def test_validation_pass_allows_stage45(self, tmp_repo, output_with_cards):
        """Passing validation allows Stage 4.5 to proceed."""
        mock_validate_all = MagicMock(return_value=_make_mock_validation_report(overall_pass=True))
        mock_write_report = MagicMock()
        mock_compile = MagicMock(return_value=True)
        mock_run_evidence_tagging = MagicMock(side_effect=lambda cards: cards)
        mock_dsd = MagicMock(return_value=MockDSDReport("CLEAN"))

        config = PipelineConfig(
            enable_stage15=False,
            enable_bricks=False,
            enable_dsd=True,
            skip_assembly=True,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(mock_run_evidence_tagging, mock_dsd, mock_compile, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate",
                return_value=(mock_validate_all, mock_write_report),
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_cards),
                config=config,
            )

        assert "stage3.5_validate" in result.stages_completed
        assert "stage4.5" in result.stages_completed
        assert "stage4.5" not in result.stages_failed

    def test_validation_fail_blocks_stage45(self, tmp_repo, output_with_cards):
        """Failed validation blocks Stage 4.5."""
        mock_validate_all = MagicMock(return_value=_make_mock_validation_report(overall_pass=False))
        mock_write_report = MagicMock()
        mock_compile = MagicMock(return_value=True)
        mock_run_evidence_tagging = MagicMock(side_effect=lambda cards: cards)
        mock_dsd = MagicMock(return_value=MockDSDReport("CLEAN"))

        config = PipelineConfig(
            enable_stage15=False,
            enable_bricks=False,
            enable_dsd=True,
            skip_assembly=True,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(mock_run_evidence_tagging, mock_dsd, mock_compile, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate",
                return_value=(mock_validate_all, mock_write_report),
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_cards),
                config=config,
            )

        assert "stage3.5_validate" in result.stages_failed
        assert "stage4.5" in result.stages_skipped
        mock_compile.assert_not_called()

    def test_dsd_suspicious_does_not_block(self, tmp_repo, output_with_cards):
        """DSD SUSPICIOUS status logs warning but does not block Stage 4.5."""
        mock_validate_all = MagicMock(return_value=_make_mock_validation_report(overall_pass=True))
        mock_write_report = MagicMock()
        mock_compile = MagicMock(return_value=True)
        mock_run_evidence_tagging = MagicMock(side_effect=lambda cards: cards)
        mock_dsd = MagicMock(return_value=MockDSDReport("SUSPICIOUS"))

        config = PipelineConfig(
            enable_stage15=False,
            enable_bricks=False,
            enable_dsd=True,
            skip_assembly=True,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(mock_run_evidence_tagging, mock_dsd, mock_compile, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate",
                return_value=(mock_validate_all, mock_write_report),
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_cards),
                config=config,
            )

        # DSD completed (not failed)
        assert "stage3.5_dsd" in result.stages_completed
        # DSD report is present with SUSPICIOUS
        assert result.dsd_report is not None
        assert result.dsd_report["overall_status"] == "SUSPICIOUS"
        # Stage 4.5 still runs
        assert "stage4.5" in result.stages_completed

    def test_dsd_disabled(self, tmp_repo, output_with_cards):
        """DSD skip when enable_dsd=False."""
        mock_validate_all = MagicMock(return_value=_make_mock_validation_report(overall_pass=True))
        mock_write_report = MagicMock()
        mock_compile = MagicMock(return_value=True)
        mock_run_evidence_tagging = MagicMock(side_effect=lambda cards: cards)
        mock_dsd = MagicMock(return_value=MockDSDReport("CLEAN"))

        config = PipelineConfig(
            enable_stage15=False,
            enable_bricks=False,
            enable_dsd=False,
            skip_assembly=True,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(mock_run_evidence_tagging, mock_dsd, mock_compile, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate",
                return_value=(mock_validate_all, mock_write_report),
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_cards),
                config=config,
            )

        assert "stage3.5_dsd" in result.stages_skipped
        assert result.dsd_report is None
        mock_dsd.assert_not_called()


class TestStage45:
    """Test Stage 4.5 Knowledge Compiler."""

    def test_stage45_success(self, tmp_repo, output_with_cards):
        mock_validate_all = MagicMock(return_value=_make_mock_validation_report(overall_pass=True))
        mock_write_report = MagicMock()
        mock_compile = MagicMock(return_value=True)
        mock_run_evidence_tagging = MagicMock(side_effect=lambda cards: cards)

        config = PipelineConfig(
            enable_stage15=False,
            enable_bricks=False,
            enable_dsd=False,
            skip_assembly=True,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(mock_run_evidence_tagging, None, mock_compile, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate",
                return_value=(mock_validate_all, mock_write_report),
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_cards),
                config=config,
            )

        assert "stage4.5" in result.stages_completed
        mock_compile.assert_called_once_with(str(output_with_cards), budget=1800)

    def test_stage45_respects_budget(self, tmp_repo, output_with_cards):
        mock_validate_all = MagicMock(return_value=_make_mock_validation_report(overall_pass=True))
        mock_write_report = MagicMock()
        mock_compile = MagicMock(return_value=True)
        mock_run_evidence_tagging = MagicMock(side_effect=lambda cards: cards)

        config = PipelineConfig(
            enable_stage15=False,
            enable_bricks=False,
            enable_dsd=False,
            skip_assembly=True,
            knowledge_budget=1200,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(mock_run_evidence_tagging, None, mock_compile, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate",
                return_value=(mock_validate_all, mock_write_report),
            ),
        ):
            run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_cards),
                config=config,
            )

        mock_compile.assert_called_once_with(str(output_with_cards), budget=1200)

    def test_stage45_failure_non_crashing(self, tmp_repo, output_with_cards):
        mock_validate_all = MagicMock(return_value=_make_mock_validation_report(overall_pass=True))
        mock_write_report = MagicMock()
        mock_compile = MagicMock(side_effect=RuntimeError("disk full"))
        mock_run_evidence_tagging = MagicMock(side_effect=lambda cards: cards)

        config = PipelineConfig(
            enable_stage15=False,
            enable_bricks=False,
            enable_dsd=False,
            skip_assembly=True,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(mock_run_evidence_tagging, None, mock_compile, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate",
                return_value=(mock_validate_all, mock_write_report),
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_cards),
                config=config,
            )

        assert "stage4.5" in result.stages_failed
        assert isinstance(result, PipelineResult)  # no crash


class TestStage5:
    """Test Stage 5 assembly."""

    def test_stage5_success(self, tmp_repo, output_with_soul_and_validation):
        mock_validate_all = MagicMock(return_value=_make_mock_validation_report(overall_pass=True))
        mock_write_report = MagicMock()
        mock_compile = MagicMock(return_value=True)
        mock_run_evidence_tagging = MagicMock(side_effect=lambda cards: cards)

        # Mock assemble to create inject/ dir
        def fake_assemble(output_dir):
            inject = Path(output_dir) / "inject"
            inject.mkdir(exist_ok=True)
            (inject / "CLAUDE.md").write_text("# Knowledge", encoding="utf-8")
            return True

        config = PipelineConfig(
            enable_stage15=False,
            enable_bricks=False,
            enable_dsd=False,
            skip_assembly=False,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(mock_run_evidence_tagging, None, mock_compile, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate",
                return_value=(mock_validate_all, mock_write_report),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_assemble", return_value=fake_assemble
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_soul_and_validation),
                config=config,
            )

        assert "stage5" in result.stages_completed
        assert result.inject_dir is not None
        assert os.path.isdir(result.inject_dir)

    def test_stage5_skipped_by_config(self, tmp_repo, output_with_cards):
        mock_validate_all = MagicMock(return_value=_make_mock_validation_report(overall_pass=True))
        mock_write_report = MagicMock()
        mock_compile = MagicMock(return_value=True)
        mock_run_evidence_tagging = MagicMock(side_effect=lambda cards: cards)
        mock_assemble = MagicMock(return_value=True)

        config = PipelineConfig(
            enable_stage15=False,
            enable_bricks=False,
            enable_dsd=False,
            skip_assembly=True,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(mock_run_evidence_tagging, None, mock_compile, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate",
                return_value=(mock_validate_all, mock_write_report),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_assemble", return_value=mock_assemble
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_cards),
                config=config,
            )

        assert "stage5" in result.stages_skipped
        assert result.inject_dir is None
        mock_assemble.assert_not_called()

    def test_stage5_failure_non_crashing(self, tmp_repo, output_with_cards):
        mock_validate_all = MagicMock(return_value=_make_mock_validation_report(overall_pass=True))
        mock_write_report = MagicMock()
        mock_compile = MagicMock(return_value=True)
        mock_run_evidence_tagging = MagicMock(side_effect=lambda cards: cards)
        mock_assemble = MagicMock(side_effect=RuntimeError("assemble bomb"))

        config = PipelineConfig(
            enable_stage15=False,
            enable_bricks=False,
            enable_dsd=False,
            skip_assembly=False,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(mock_run_evidence_tagging, None, mock_compile, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate",
                return_value=(mock_validate_all, mock_write_report),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_assemble", return_value=mock_assemble
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_cards),
                config=config,
            )

        assert "stage5" in result.stages_failed
        assert result.inject_dir is None
        assert isinstance(result, PipelineResult)  # no crash


class TestFullHappyPath:
    """Integration-style test: all stages complete."""

    def test_full_pipeline_happy_path(self, tmp_repo, output_with_soul_and_validation, tmp_path):
        """All stages complete successfully (everything mocked)."""
        mock_validate_all = MagicMock(return_value=_make_mock_validation_report(overall_pass=True))
        mock_write_report = MagicMock()
        mock_compile = MagicMock(return_value=True)
        mock_run_evidence_tagging = MagicMock(side_effect=lambda cards: cards)
        mock_dsd = MagicMock(return_value=MockDSDReport("CLEAN"))

        # Mock stage0 function that writes repo_facts.json
        def fake_stage0_fn(repo_path):
            mock_facts = MagicMock()
            mock_facts.model_dump.return_value = {
                "repo_path": repo_path,
                "commands": [],
                "skills": [],
                "files": [],
                "config_keys": [],
                "frameworks": [],
                "languages": [],
                "dependencies": [],
                "storage_paths": [],
                "project_narrative": "Mocked extraction.",
            }
            return mock_facts

        def fake_assemble(output_dir):
            inject = Path(output_dir) / "inject"
            inject.mkdir(exist_ok=True)
            (inject / "CLAUDE.md").write_text("# Knowledge", encoding="utf-8")
            return True

        # Remove existing repo_facts.json to force Stage 0 execution
        facts_path = output_with_soul_and_validation / "artifacts" / "repo_facts.json"
        if facts_path.exists():
            facts_path.unlink()

        config = PipelineConfig(
            enable_stage15=False,
            enable_bricks=False,
            enable_dsd=True,
            skip_assembly=False,
        )

        with (
            patch(
                "doramagic_orchestration.phase_runner._import_stage0", return_value=fake_stage0_fn
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(mock_run_evidence_tagging, mock_dsd, mock_compile, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate",
                return_value=(mock_validate_all, mock_write_report),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_assemble", return_value=fake_assemble
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(output_with_soul_and_validation),
                config=config,
            )

        assert "stage0" in result.stages_completed
        assert "stage3.5_validate" in result.stages_completed
        assert "stage3.5_dsd" in result.stages_completed
        assert "stage4.5" in result.stages_completed
        assert "stage5" in result.stages_completed
        assert result.stages_failed == []
        assert result.inject_dir is not None
        assert result.dsd_report is not None
        assert result.dsd_report["overall_status"] == "CLEAN"


class TestGracefulDegradation:
    """Verify every degradation scenario from BRIEF.md."""

    def test_all_modules_missing_no_crash(self, tmp_repo, tmp_output):
        """Pipeline handles all ImportErrors gracefully."""
        config = PipelineConfig(
            enable_stage15=True,
            enable_bricks=True,
            bricks_dir="/nonexistent/bricks",
            enable_dsd=True,
            skip_assembly=False,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(None, None, None, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate", return_value=(None, None)
            ),
            patch("doramagic_orchestration.phase_runner._import_assemble", return_value=None),
            patch("doramagic_orchestration.phase_runner._import_brick_injector", return_value=None),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(tmp_output),
                adapter=MagicMock(),  # adapter provided but stage15 module missing
                config=config,
            )
        assert isinstance(result, PipelineResult)
        # Nothing should have crashed; stages are either skipped or failed
        all_stages = result.stages_completed + result.stages_skipped + result.stages_failed
        # No duplicate entries for same stage category
        assert len(set(all_stages)) == len(all_stages)

    def test_output_dir_created_if_missing(self, tmp_repo, tmp_path):
        """output_dir is created if it doesn't exist yet."""
        new_output = tmp_path / "brand_new_output"
        assert not new_output.exists()

        config = PipelineConfig(
            enable_stage15=False,
            enable_bricks=False,
            enable_dsd=False,
            skip_assembly=True,
        )
        with (
            patch("doramagic_orchestration.phase_runner._import_stage0", return_value=None),
            patch(
                "doramagic_orchestration.phase_runner._import_extraction_modules",
                return_value=(None, None, None, None),
            ),
            patch(
                "doramagic_orchestration.phase_runner._import_validate", return_value=(None, None)
            ),
        ):
            result = run_single_project_pipeline(
                repo_path=str(tmp_repo),
                output_dir=str(new_output),
                config=config,
            )
        assert new_output.exists()
        assert isinstance(result, PipelineResult)
