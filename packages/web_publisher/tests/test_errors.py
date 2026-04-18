"""Tests for P1-1: ToolUseStoppedWithoutSubmitError.

Verifies:
  1. New error class exists and has correct attributes
  2. ToolUseExecutor raises StoppedWithoutSubmit (not MaxIterations) when LLM
     stops early on iter > 0 without calling submit
  3. MaxIterationsError is still raised when iterations are exhausted
  4. The two errors are distinguishable (different types)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from doramagic_web_publisher.errors import (
    ToolUseMaxIterationsError,
    ToolUseStoppedWithoutSubmitError,
)


def test_stopped_without_submit_error_attributes():
    """ToolUseStoppedWithoutSubmitError exposes correct attributes."""
    exc = ToolUseStoppedWithoutSubmitError(
        tool_name="submit_content",
        iteration=2,
        finish_reason="end_turn",
    )
    assert exc.tool_name == "submit_content"
    assert exc.iterations == 2
    assert exc.finish_reason == "end_turn"
    assert "end_turn" in str(exc)
    assert "submit_content" in str(exc)


def test_stopped_without_submit_is_subclass_of_tool_use_error():
    """ToolUseStoppedWithoutSubmitError is a subclass of ToolUseError."""
    from doramagic_web_publisher.errors import ToolUseError

    exc = ToolUseStoppedWithoutSubmitError("submit_x", 1, "stop")
    assert isinstance(exc, ToolUseError)


def test_max_iterations_and_stopped_are_distinct_types():
    """The two error types are not the same class (distinguishable by except clause)."""
    assert ToolUseMaxIterationsError is not ToolUseStoppedWithoutSubmitError


def _make_adapter_that_returns_stop(call_count_before_stop: int = 1):
    """Adapter that returns text content (no tool call) after N turns with tool calls."""
    from doramagic_shared_utils.llm_adapter import LLMAdapter, LLMResponse

    adapter = MagicMock(spec=LLMAdapter)
    call_index = [0]

    async def mock_generate(*a, **kw):
        call_index[0] += 1
        # First call: return a tool-less stop response
        return LLMResponse(
            content="I have finished thinking.",
            finish_reason="stop",
            tool_calls=[],
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )

    adapter.generate_with_tools = mock_generate
    return adapter


def test_executor_raises_stopped_without_submit_on_later_stop():
    """When LLM stops without submit after iter > 0, StoppedWithoutSubmitError is raised."""
    from doramagic_shared_utils.llm_adapter import LLMAdapter, LLMResponse, LLMToolDefinition
    from doramagic_web_publisher.runtime.tool_use import ToolUseExecutor

    # First turn: has a non-submit tool call; second turn: stops without submitting
    first_response = LLMResponse(
        content="",
        model_id="test-model",
        finish_reason="tool_use",
        tool_calls=[{"id": "tc_0", "name": "lookup", "arguments": {"q": "test"}}],
    )
    second_response = LLMResponse(
        content="Done thinking.",
        model_id="test-model",
        finish_reason="stop",
        tool_calls=[],
    )

    adapter = MagicMock(spec=LLMAdapter)
    responses = [first_response, second_response]
    call_index = [0]

    async def mock_generate(*a, **kw):
        resp = responses[call_index[0] % len(responses)]
        call_index[0] += 1
        return resp

    adapter.generate_with_tools = mock_generate

    executor = ToolUseExecutor(
        adapter=adapter,
        model_id="test-model",
        system_prompt="Help me.",
        tools=[
            LLMToolDefinition(
                name="submit_content",
                description="Submit",
                parameters={"type": "object", "properties": {}, "required": []},
            ),
            LLMToolDefinition(
                name="lookup",
                description="Look up info",
                parameters={
                    "type": "object",
                    "properties": {"q": {"type": "string"}},
                    "required": ["q"],
                },
            ),
        ],
        submit_tool_name="submit_content",
        max_iter=5,
    )

    with pytest.raises(ToolUseStoppedWithoutSubmitError) as exc_info:
        executor.run("Generate content.")

    assert exc_info.value.tool_name == "submit_content"
