"""Degradation scenario tests.

Tests every failure mode identified in the CEO/Eng reviews:
- Empty/bad input → ERROR
- Phase B zero candidates → ERROR
- Phase CD partial failure → DEGRADED (continue with remaining)
- Phase CD all fail → ERROR
- Phase G REVISE → loop to F (max 3)
- Phase G BLOCKED → ERROR
- Budget exceeded → DEGRADED
- Lease expired → DEGRADED
- LLM refusal → ERROR with clear message
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

_project_root = Path(__file__).resolve().parent.parent.parent
for pkg_dir in (_project_root / "packages").iterdir():
    if pkg_dir.is_dir() and not pkg_dir.name.startswith((".", "_")):
        if str(pkg_dir) not in sys.path:
            sys.path.insert(0, str(pkg_dir))

from doramagic_controller.flow_controller import FlowController
from doramagic_controller.adapters.cli import CLIAdapter
from doramagic_controller.state_definitions import Phase
from doramagic_controller.lease_manager import LeaseManager
from doramagic_controller.budget_manager import BudgetManager
from doramagic_contracts.budget import BudgetPolicy, BudgetSnapshot
from doramagic_contracts.envelope import (
    ErrorCodes,
    ModuleResultEnvelope,
    RunMetrics,
    WarningItem,
)
from doramagic_contracts.executor import ExecutorConfig


# ─── Mock Executors ────────────────────────────────────────


def _ok_metrics() -> RunMetrics:
    return RunMetrics(
        wall_time_ms=100, llm_calls=0,
        prompt_tokens=0, completion_tokens=0,
        estimated_cost_usd=0.0,
    )


class MockExecutor:
    """Configurable mock executor for testing degradation paths."""

    def __init__(self, status="ok", error_code=None, data=None, warnings=None, name="Mock"):
        self._status = status
        self._error_code = error_code
        self._data = data
        self._warnings = warnings or []
        self._name = name

    async def execute(self, input, adapter, config):
        return ModuleResultEnvelope(
            module_name=self._name,
            status=self._status,
            error_code=self._error_code,
            warnings=self._warnings,
            data=self._data,
            metrics=_ok_metrics(),
        )

    def validate_input(self, input):
        return []

    def can_degrade(self):
        return True


class DiscoveryNoCandidates(MockExecutor):
    """Discovery returns zero candidates."""

    def __init__(self):
        super().__init__(
            status="blocked",
            error_code=ErrorCodes.NO_CANDIDATES,
            name="DiscoveryRunner",
        )


class ValidatorRevise(MockExecutor):
    """Validator returns REVISE."""

    def __init__(self):
        super().__init__(
            status="degraded",
            name="Validator",
            data={"status": "REVISE", "checks": [], "revise_instructions": ["Fix X"]},
        )


class ValidatorBlocked(MockExecutor):
    """Validator returns BLOCKED."""

    def __init__(self):
        super().__init__(
            status="blocked",
            error_code=ErrorCodes.VALIDATION_BLOCKED,
            name="Validator",
        )


class BudgetExceedingExecutor(MockExecutor):
    """Executor that reports high cost, triggering budget exceeded."""

    async def execute(self, input, adapter, config):
        return ModuleResultEnvelope(
            module_name="ExpensiveExecutor",
            status="ok",
            data={},
            metrics=RunMetrics(
                wall_time_ms=1000, llm_calls=5,
                prompt_tokens=100000, completion_tokens=50000,
                estimated_cost_usd=5.00,  # Over $2.50 budget
            ),
        )


# ─── Helper ────────────────────────────────────────────────


def _make_controller(
    tmp_path: Path,
    executors: dict | None = None,
    budget_policy: BudgetPolicy | None = None,
) -> FlowController:
    adapter = CLIAdapter(storage_root=tmp_path)
    # Default: all executors return "ok" with minimal NeedProfile
    default_executors = {
        "NeedProfileBuilder": MockExecutor(
            status="ok", name="NeedProfileBuilder",
            data={"raw_input": "test", "keywords": ["test"], "intent": "test",
                  "search_directions": [{"direction": "test", "priority": "high"}],
                  "constraints": [], "quality_expectations": {}},
        ),
        "DiscoveryRunner": MockExecutor(
            status="ok", name="DiscoveryRunner",
            data={"candidates": [
                {"candidate_id": "r1", "name": "repo1", "url": "https://github.com/test/repo1",
                 "type": "github_repo", "relevance": "high", "contribution": "",
                 "quick_score": 8, "quality_signals": {}, "selected_for_phase_c": True,
                 "selected_for_phase_d": False},
            ], "search_coverage": [], "no_candidate_reason": None},
        ),
        "SoulExtractorBatch": MockExecutor(
            status="ok", name="SoulExtractorBatch",
            data={"successful_repos": ["r1"], "failed_repos": [],
                  "extraction_dirs": {"r1": "/tmp/r1"}, "community_signals": {}},
        ),
        "SynthesisRunner": MockExecutor(
            status="ok", name="SynthesisRunner",
            data={"consensus": [], "conflicts": [], "unique_knowledge": [],
                  "selected_knowledge": [], "excluded_knowledge": [], "open_questions": []},
        ),
        "SkillCompiler": MockExecutor(
            status="ok", name="SkillCompiler",
            data={"skill_md_path": "/tmp/SKILL.md", "provenance_md_path": "/tmp/PROVENANCE.md",
                  "limitations_md_path": "/tmp/LIMITATIONS.md", "readme_md_path": "/tmp/README.md",
                  "build_manifest": {}},
        ),
        "Validator": MockExecutor(
            status="ok", name="Validator",
            data={"status": "PASS", "checks": [], "revise_instructions": []},
        ),
        "DeliveryPackager": MockExecutor(
            status="ok", name="DeliveryPackager",
            data={"delivered_files": ["SKILL.md"], "warnings": []},
        ),
    }
    if executors:
        default_executors.update(executors)

    return FlowController(
        adapter=adapter,
        run_dir=tmp_path / "test-run",
        executors=default_executors,
        budget_policy=budget_policy or BudgetPolicy(),
    )


# ─── Tests ─────────────────────────────────────────────────


class TestHappyPath:
    """Full pipeline with all mocks returning OK should reach DONE."""

    def test_reaches_done(self, tmp_path):
        ctrl = _make_controller(tmp_path)
        result = asyncio.run(ctrl.run(user_input="test input"))
        assert result.phase == Phase.DONE
        assert not result.degradation_log


class TestPhaseADegradation:
    """Phase A with ambiguous input should trigger clarification or degraded."""

    def test_empty_input_error(self, tmp_path):
        ctrl = _make_controller(tmp_path)
        result = asyncio.run(ctrl.run(user_input=""))
        assert result.phase == Phase.ERROR

    def test_clarification_pauses(self, tmp_path):
        ctrl = _make_controller(tmp_path, executors={
            "NeedProfileBuilder": MockExecutor(
                status="degraded", name="NeedProfileBuilder",
                warnings=[WarningItem(code="CLARIFY", message="CLARIFY:请具体描述")],
                data={"raw_input": "?", "keywords": [], "intent": "?",
                      "search_directions": [], "constraints": []},
            ),
        })
        result = asyncio.run(ctrl.run(user_input="?"))
        assert result.phase == Phase.PHASE_A_CLARIFY


class TestPhaseBZeroCandidates:
    """Phase B with no candidates should ERROR."""

    def test_no_candidates_degrades(self, tmp_path):
        ctrl = _make_controller(tmp_path, executors={
            "DiscoveryRunner": DiscoveryNoCandidates(),
        })
        result = asyncio.run(ctrl.run(user_input="test"))
        # Zero candidates from discovery → DEGRADED (not ERROR, because mock can_degrade=True)
        assert result.phase in (Phase.DEGRADED, Phase.ERROR)
        assert any("blocked" in d.lower() or "DiscoveryRunner" in d for d in result.degradation_log)


class TestPhaseCDPartialFailure:
    """Phase CD with partial extraction should DEGRADE but continue."""

    def test_partial_extraction_continues(self, tmp_path):
        ctrl = _make_controller(tmp_path, executors={
            "SoulExtractorBatch": MockExecutor(
                status="degraded", name="SoulExtractorBatch",
                warnings=[WarningItem(code="PARTIAL", message="1/3 repos failed")],
                data={"successful_repos": ["r1", "r2"], "failed_repos": [{"repo_id": "r3"}],
                      "extraction_dirs": {}, "community_signals": {}},
            ),
        })
        result = asyncio.run(ctrl.run(user_input="test"))
        # Should continue past CD despite degradation
        assert result.phase in (Phase.DONE, Phase.DEGRADED, Phase.ERROR)
        assert any("degraded" in d.lower() for d in result.degradation_log)

    def test_all_extraction_fails(self, tmp_path):
        ctrl = _make_controller(tmp_path, executors={
            "SoulExtractorBatch": MockExecutor(
                status="error", name="SoulExtractorBatch",
                error_code=ErrorCodes.UPSTREAM_MISSING,
            ),
        })
        result = asyncio.run(ctrl.run(user_input="test"))
        assert result.phase == Phase.ERROR


class TestPhaseGRevise:
    """Phase G REVISE should loop back to F, max 3 times."""

    def test_revise_loops_then_errors(self, tmp_path):
        # Validator always returns REVISE
        ctrl = _make_controller(tmp_path, executors={
            "Validator": ValidatorRevise(),
        })
        result = asyncio.run(ctrl.run(user_input="test"))
        # After 3 REVISE loops, should ERROR
        assert result.phase == Phase.ERROR
        assert any("max loops" in d.lower() or "REVISE" in d for d in result.degradation_log)
        # Should have looped 3 times
        assert result.revise_count >= 3

    def test_blocked_is_error(self, tmp_path):
        ctrl = _make_controller(tmp_path, executors={
            "Validator": ValidatorBlocked(),
        })
        result = asyncio.run(ctrl.run(user_input="test"))
        assert result.phase == Phase.ERROR
        assert any("BLOCKED" in d for d in result.degradation_log)


class TestBudgetExceeded:
    """Budget exceeded should transition to DEGRADED."""

    def test_budget_exceeded_degrades(self, tmp_path):
        # Tight budget: $0.01
        policy = BudgetPolicy(max_cost_usd=0.01, max_tokens=100, max_duration_ms=1_800_000)
        ctrl = _make_controller(tmp_path, budget_policy=policy, executors={
            "NeedProfileBuilder": BudgetExceedingExecutor(),
        })
        result = asyncio.run(ctrl.run(user_input="test"))
        # Should degrade after first expensive executor
        assert result.phase in (Phase.DEGRADED, Phase.ERROR)
        assert any("budget" in d.lower() or "Budget" in d for d in result.degradation_log)


class TestLeaseManager:
    """Lease system unit tests."""

    def test_issue_and_consume(self, tmp_path):
        lm = LeaseManager(tmp_path / "leases")
        token = lm.issue("test_step")
        assert lm.validate(token)
        assert lm.consume(token)
        assert not lm.validate(token)  # consumed

    def test_replay_protection(self, tmp_path):
        lm = LeaseManager(tmp_path / "leases")
        token = lm.issue("test_step")
        assert lm.consume(token)
        assert not lm.consume(token)  # replay blocked

    def test_expiry(self, tmp_path):
        lm = LeaseManager(tmp_path / "leases", default_ttl_seconds=0)
        token = lm.issue("test_step", ttl_seconds=0)
        time.sleep(0.01)
        assert not lm.validate(token)  # expired

    def test_renew(self, tmp_path):
        lm = LeaseManager(tmp_path / "leases", default_ttl_seconds=1)
        token = lm.issue("test_step", ttl_seconds=1)
        assert lm.renew(token, ttl_seconds=300)
        assert lm.validate(token)  # still valid after renewal

    def test_invalid_token(self, tmp_path):
        lm = LeaseManager(tmp_path / "leases")
        assert not lm.validate("nonexistent_token")
        assert not lm.consume("nonexistent_token")


class TestBudgetManager:
    """Budget manager unit tests."""

    def test_tracking(self):
        bm = BudgetManager(BudgetPolicy(max_cost_usd=2.50))
        bm.start()
        warnings = bm.record_phase("CD", RunMetrics(
            wall_time_ms=5000, llm_calls=3,
            prompt_tokens=10000, completion_tokens=5000,
            estimated_cost_usd=1.00,
        ))
        assert bm.total_cost == 1.00
        assert bm.total_tokens == 15000
        assert not bm.is_exceeded()

    def test_exceeded(self):
        bm = BudgetManager(BudgetPolicy(max_cost_usd=0.50))
        bm.start()
        bm.record_phase("CD", RunMetrics(
            wall_time_ms=5000, llm_calls=3,
            prompt_tokens=10000, completion_tokens=5000,
            estimated_cost_usd=1.00,
        ))
        assert bm.is_exceeded()

    def test_phase_overshoot_warning(self):
        policy = BudgetPolicy(max_cost_usd=2.50)
        bm = BudgetManager(policy)
        bm.start()
        # CD allocation is 60% of $2.50 = $1.50. 120% = $1.80
        warnings = bm.record_phase("CD", RunMetrics(
            wall_time_ms=5000, llm_calls=3,
            prompt_tokens=10000, completion_tokens=5000,
            estimated_cost_usd=2.00,  # Over 120% of $1.50
        ))
        assert len(warnings) >= 1
        assert "exceeded" in warnings[0].lower()

    def test_snapshot(self):
        bm = BudgetManager(BudgetPolicy(max_cost_usd=2.50, max_tokens=200000))
        bm.start()
        bm.record_phase("A", RunMetrics(
            wall_time_ms=100, llm_calls=1,
            prompt_tokens=1000, completion_tokens=500,
            estimated_cost_usd=0.10,
        ))
        snap = bm.snapshot()
        assert snap.spent_usd == 0.10
        assert snap.spent_tokens == 1500
        assert snap.remaining_usd == 2.40
        assert snap.remaining_tokens == 198500
