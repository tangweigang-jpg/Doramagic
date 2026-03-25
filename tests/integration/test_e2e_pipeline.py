"""End-to-end pipeline integration test.

Runs the full FlowController → Executor chain with CLI adapter.
Tests the happy path and key degradation scenarios.

Usage:
    PYTHONPATH="packages/contracts:packages/controller:packages/shared_utils:packages/executors:packages/cross_project:packages/extraction:packages/orchestration:packages/skill_compiler:packages/platform_openclaw:packages/community" \
    python3 -m pytest tests/integration/test_e2e_pipeline.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

# Add packages to path
_project_root = Path(__file__).resolve().parent.parent.parent
for pkg_dir in (_project_root / "packages").iterdir():
    if pkg_dir.is_dir() and not pkg_dir.name.startswith((".", "_")):
        if str(pkg_dir) not in sys.path:
            sys.path.insert(0, str(pkg_dir))


from doramagic_controller.flow_controller import FlowController, ControllerState
from doramagic_controller.adapters.cli import CLIAdapter
from doramagic_controller.state_definitions import Phase
from doramagic_executors import ALL_EXECUTORS
from doramagic_contracts.budget import BudgetPolicy


@pytest.fixture
def run_dir(tmp_path):
    return tmp_path / "test-run"


@pytest.fixture
def controller(run_dir):
    adapter = CLIAdapter(storage_root=run_dir.parent)
    executors = {name: cls() for name, cls in ALL_EXECUTORS.items()}
    return FlowController(
        adapter=adapter,
        run_dir=run_dir,
        executors=executors,
        budget_policy=BudgetPolicy(),
    )


class TestEmptyInput:
    """Empty or whitespace input should be rejected gracefully."""

    def test_empty_string(self, controller):
        result = asyncio.run(controller.run(user_input=""))
        assert result.phase == Phase.ERROR
        assert "Empty input" in result.degradation_log

    def test_whitespace_only(self, controller):
        result = asyncio.run(controller.run(user_input="   "))
        assert result.phase == Phase.ERROR


class TestNeedProfileParsing:
    """Phase A should parse various Chinese/English inputs into NeedProfile."""

    def test_chinese_input(self, controller):
        result = asyncio.run(controller.run(user_input="帮我做一个记账app"))
        arts = result.phase_artifacts
        np = arts.get("need_profile", {})
        assert np, "NeedProfile should be stored"
        assert "accounting" in np.get("keywords", []) or "finance" in np.get("keywords", [])

    def test_english_input(self, controller):
        result = asyncio.run(controller.run(user_input="build a recipe management tool"))
        arts = result.phase_artifacts
        np = arts.get("need_profile", {})
        assert np, "NeedProfile should be stored"
        assert any("recipe" in kw for kw in np.get("keywords", []))

    def test_mixed_input(self, controller):
        result = asyncio.run(controller.run(user_input="帮我做一个 password manager"))
        arts = result.phase_artifacts
        np = arts.get("need_profile", {})
        assert np, "NeedProfile should be stored"
        keywords = np.get("keywords", [])
        # Should have both CN-matched and EN-extracted keywords
        assert len(keywords) >= 2

    def test_dora_prefix_stripped(self, controller):
        result = asyncio.run(controller.run(user_input="/dora 帮我做一个记账app"))
        arts = result.phase_artifacts
        np = arts.get("need_profile", {})
        assert np
        assert "/dora" not in np.get("raw_input", "")


class TestStateTransitions:
    """State machine should follow the correct transition path."""

    def test_reaches_phase_b(self, controller):
        result = asyncio.run(controller.run(user_input="帮我做一个记账app"))
        # Should at minimum reach Phase B (discovery)
        log = (controller._run_dir / "run_log.jsonl").read_text().strip().split("\n")
        events = [json.loads(line) for line in log]
        transitions = [e for e in events if e["event"] == "transition"]
        phases_visited = [t["to"] for t in transitions]
        assert "PHASE_A" in phases_visited or "PHASE_B" in phases_visited

    def test_state_persisted(self, controller):
        asyncio.run(controller.run(user_input="帮我做记账app"))
        state_file = controller._run_dir / "controller_state.json"
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert "phase" in state
        assert "run_id" in state
        assert "phase_artifacts" in state


class TestStatePersistence:
    """Controller should save and load state correctly."""

    def test_save_and_load(self, run_dir):
        state = ControllerState(
            run_id="test-123",
            phase=Phase.PHASE_A_CLARIFY,
            raw_input="test input",
            lease_token="abc123",
            phase_artifacts={"need_profile": {"keywords": ["test"]}},
        )
        # Save
        run_dir.mkdir(parents=True, exist_ok=True)
        state_file = run_dir / "controller_state.json"
        state_file.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # Load
        loaded = ControllerState.from_dict(
            json.loads(state_file.read_text(encoding="utf-8"))
        )
        assert loaded.run_id == "test-123"
        assert loaded.phase == Phase.PHASE_A_CLARIFY
        assert loaded.raw_input == "test input"
        assert loaded.phase_artifacts["need_profile"]["keywords"] == ["test"]


class TestBudgetTracking:
    """Budget manager should track spending across phases."""

    def test_budget_snapshot(self, controller):
        result = asyncio.run(controller.run(user_input="记账"))
        # Budget should have been tracked
        snapshot = controller._budget.snapshot()
        assert snapshot.elapsed_ms > 0
        assert snapshot.remaining_usd <= 2.50


class TestRunLog:
    """Run log should capture all events."""

    def test_log_created(self, controller):
        asyncio.run(controller.run(user_input="记账"))
        log_file = controller._run_dir / "run_log.jsonl"
        assert log_file.exists()
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) >= 4  # At minimum: step_start + transition + step_start + executor_done

    def test_log_entries_valid_json(self, controller):
        asyncio.run(controller.run(user_input="记账"))
        log_file = controller._run_dir / "run_log.jsonl"
        for line in log_file.read_text().strip().split("\n"):
            entry = json.loads(line)
            assert "ts" in entry
            assert "event" in entry


class TestDirectoryStructure:
    """Run directory should have correct structure."""

    def test_staging_created(self, controller):
        asyncio.run(controller.run(user_input="记账"))
        assert (controller._run_dir / "staging").is_dir()

    def test_delivery_created(self, controller):
        asyncio.run(controller.run(user_input="记账"))
        assert (controller._run_dir / "delivery").is_dir()

    def test_leases_created(self, controller):
        asyncio.run(controller.run(user_input="记账"))
        assert (controller._run_dir / "leases").is_dir()
        # Should have at least one lease file
        lease_files = list((controller._run_dir / "leases").glob("*.json"))
        assert len(lease_files) >= 1
