"""Migration tests for Stage 1.5 provider-based strategy routing."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

from doramagic_contracts.envelope import ModuleResultEnvelope, RunMetrics
from doramagic_contracts.extraction import (
    Stage15AgenticInput,
    Stage15Budget,
    Stage15Toolset,
)
from doramagic_extraction import stage15_agentic as stage15_module
from doramagic_extraction.stage15_agentic import (
    resolve_stage15_agentic_strategy,
    run_stage15_agentic,
)
from doramagic_shared_utils.llm_adapter import LLMAdapter, MockLLMAdapter

FIXTURES_DIR = _REPO_ROOT / "data" / "fixtures"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_input(tmp_path: Path) -> Stage15AgenticInput:
    repo_payload = _load_json(FIXTURES_DIR / "example_calorie_repo_facts_calorie.json")
    stage1_payload = _load_json(FIXTURES_DIR / "example_calorie_stage1_output_calorie.json")

    repo_root = tmp_path / "ai-calorie-counter"
    repo_root.mkdir(parents=True, exist_ok=True)

    repo_payload["repo"]["local_path"] = str(repo_root)
    stage1_payload["repo"]["local_path"] = str(repo_root)

    return Stage15AgenticInput(
        repo=repo_payload["repo"],
        repo_facts=repo_payload,
        stage1_output=stage1_payload,
        budget=Stage15Budget(
            max_rounds=5,
            max_tool_calls=30,
            max_prompt_tokens=60000,
            stop_after_no_gain_rounds=2,
        ),
        toolset=Stage15Toolset(),
    )


def test_google_provider_routes_to_gemini_strategy(tmp_path: Path) -> None:
    input_data = _build_input(tmp_path)
    adapter = LLMAdapter(provider_override="google")
    adapter._default_model = "gemini-2.5-pro"

    dummy_result = ModuleResultEnvelope(
        module_name="extraction.stage15_agentic",
        status="ok",
        error_code=None,
        data=None,
        metrics=RunMetrics(
            wall_time_ms=1,
            llm_calls=0,
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost_usd=0.0,
            retries=0,
        ),
    )

    with (
        patch.object(
            stage15_module._GeminiStage15AgenticStrategy,
            "run",
            return_value=dummy_result,
        ) as gemini_run,
        patch.object(
            stage15_module._Stage15AgenticStrategy,
            "run",
            side_effect=AssertionError("default strategy should not be used"),
        ),
    ):
        result = run_stage15_agentic(input_data, adapter=adapter)

    assert result is dummy_result
    assert gemini_run.called
    assert resolve_stage15_agentic_strategy(adapter).name == "gemini"


def test_mock_provider_routes_to_default_strategy(tmp_path: Path) -> None:
    input_data = _build_input(tmp_path)
    adapter = MockLLMAdapter()

    dummy_result = ModuleResultEnvelope(
        module_name="extraction.stage15_agentic",
        status="ok",
        error_code=None,
        data=None,
        metrics=RunMetrics(
            wall_time_ms=1,
            llm_calls=0,
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost_usd=0.0,
            retries=0,
        ),
    )

    with (
        patch.object(
            stage15_module._Stage15AgenticStrategy,
            "run",
            return_value=dummy_result,
        ) as default_run,
        patch.object(
            stage15_module._GeminiStage15AgenticStrategy,
            "run",
            side_effect=AssertionError("gemini strategy should not be used"),
        ),
    ):
        result = run_stage15_agentic(input_data, adapter=adapter)

    assert result is dummy_result
    assert default_run.called
    assert resolve_stage15_agentic_strategy(adapter).name == "default"
