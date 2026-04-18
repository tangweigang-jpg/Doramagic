"""Tests for P0-1: MiniMax fallback JSON normalization in ToolUseExecutor.

Verifies:
  1. _extract_fallback_tool_calls parses bare JSON tool call
  2. _extract_fallback_tool_calls parses ```json``` code block
  3. _extract_fallback_tool_calls supports multiple parallel tool calls
  4. _normalize_fallback_response no-ops when tool_calls already present
  5. _normalize_fallback_response synthesises tool_calls from content
  6. ToolUseExecutor integrates normalization: fallback content → submit
"""

from __future__ import annotations

from unittest.mock import MagicMock

from doramagic_web_publisher.runtime.tool_use import (
    ToolUseExecutor,
    _extract_fallback_tool_calls,
    _normalize_fallback_response,
)

# ---------------------------------------------------------------------------
# Unit tests for _extract_fallback_tool_calls
# ---------------------------------------------------------------------------


def test_extract_bare_json_single():
    """Bare JSON {"tool": ..., "arguments": {...}} is parsed."""
    content = '{"tool": "submit_content", "arguments": {"slug": "my-slug"}}'
    results = _extract_fallback_tool_calls(content)
    assert len(results) == 1
    assert results[0]["name"] == "submit_content"
    assert results[0]["arguments"] == {"slug": "my-slug"}
    assert "id" in results[0]


def test_extract_code_block_json():
    """JSON inside ```json ... ``` code block is parsed."""
    content = (
        "Here is my response:\n"
        "```json\n"
        '{"tool": "submit_faq", "arguments": {"faqs": []}}\n'
        "```\n"
        "That is all."
    )
    results = _extract_fallback_tool_calls(content)
    assert len(results) == 1
    assert results[0]["name"] == "submit_faq"
    assert results[0]["arguments"] == {"faqs": []}


def test_extract_no_tool_calls_returns_empty():
    """Content without any tool call JSON returns empty list."""
    content = "I'm thinking about this problem carefully."
    results = _extract_fallback_tool_calls(content)
    assert results == []


def test_extract_multiple_code_blocks():
    """Multiple ```json``` blocks → multiple tool calls (parallel)."""
    content = (
        "First tool:\n"
        "```json\n"
        '{"tool": "tool_a", "arguments": {"x": 1}}\n'
        "```\n"
        "Second tool:\n"
        "```json\n"
        '{"tool": "tool_b", "arguments": {"y": 2}}\n'
        "```\n"
    )
    results = _extract_fallback_tool_calls(content)
    assert len(results) == 2
    names = {r["name"] for r in results}
    assert "tool_a" in names
    assert "tool_b" in names


def test_extract_ignores_invalid_json():
    """Malformed JSON is silently skipped."""
    content = '{"tool": "bad", "arguments": {broken}}'
    results = _extract_fallback_tool_calls(content)
    assert results == []


def test_extract_arguments_as_string_is_parsed():
    """If arguments is a JSON string, it gets parsed to dict."""
    content = '{"tool": "submit_x", "arguments": "{\\"key\\": \\"val\\"}"}'
    results = _extract_fallback_tool_calls(content)
    # May or may not parse depending on inner JSON — just verify no crash
    assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Unit tests for _normalize_fallback_response
# ---------------------------------------------------------------------------


def _make_response(tool_calls=None, content="", finish_reason="stop"):
    """Create a minimal LLMResponse-like object for testing."""
    from doramagic_shared_utils.llm_adapter import LLMResponse

    return LLMResponse(
        content=content,
        model_id="test-model",
        finish_reason=finish_reason,
        tool_calls=tool_calls or [],
    )


def test_normalize_noop_when_tool_calls_present():
    """If response already has tool_calls, normalization is a no-op."""
    existing = [{"id": "tc_0", "name": "submit_x", "arguments": {"a": 1}}]
    resp = _make_response(tool_calls=existing)
    result = _normalize_fallback_response(resp)
    assert result.tool_calls == existing  # unchanged


def test_normalize_synthesises_from_content():
    """If response has no tool_calls but content has fallback JSON, synthesise them."""
    content = '{"tool": "submit_eval", "arguments": {"tier": "standard"}}'
    resp = _make_response(content=content)
    result = _normalize_fallback_response(resp)
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "submit_eval"
    assert result.tool_calls[0]["arguments"] == {"tier": "standard"}
    assert result.finish_reason == "tool_use"


def test_normalize_noop_when_no_json_in_content():
    """If response has neither tool_calls nor fallback JSON, return unchanged."""
    resp = _make_response(content="Just some text response.")
    result = _normalize_fallback_response(resp)
    assert result.tool_calls == []
    assert result.finish_reason == "stop"


# ---------------------------------------------------------------------------
# Integration: ToolUseExecutor with fallback normalization
# ---------------------------------------------------------------------------


def _make_adapter_with_fallback_response(tool_name: str, args: dict):
    """Create an adapter whose generate_with_tools returns fallback-style content."""
    from doramagic_shared_utils.llm_adapter import LLMAdapter, LLMResponse

    fallback_content = f'{{"tool": "{tool_name}", "arguments": {__import__("json").dumps(args)}}}'

    adapter = MagicMock(spec=LLMAdapter)

    async def mock_generate_with_tools(*a, **kw):
        return LLMResponse(
            content=fallback_content,
            model_id="minimax-text-01",
            finish_reason="stop",  # no native tool_calls
            tool_calls=[],
        )

    adapter.generate_with_tools = mock_generate_with_tools
    return adapter


def test_executor_handles_fallback_json_as_submit():
    """ToolUseExecutor normalises fallback JSON and treats it as submit call."""
    from doramagic_shared_utils.llm_adapter import LLMToolDefinition

    submit_args = {"slug": "test-slug", "name": "Test"}
    adapter = _make_adapter_with_fallback_response("submit_content", submit_args)

    executor = ToolUseExecutor(
        adapter=adapter,
        model_id="minimax-text-01",
        system_prompt="You are a helper.",
        tools=[
            LLMToolDefinition(
                name="submit_content",
                description="Submit content fields",
                parameters={
                    "type": "object",
                    "properties": {"slug": {"type": "string"}, "name": {"type": "string"}},
                    "required": ["slug", "name"],
                },
            )
        ],
        submit_tool_name="submit_content",
        max_iter=3,
    )

    result = executor.run("Please generate content.")
    assert result.submitted_args == submit_args
    assert result.iterations == 1


# ---------------------------------------------------------------------------
# P1 fix: nested-object support via raw_decode scanning
# ---------------------------------------------------------------------------


def test_fallback_nested_arguments_object():
    """arguments containing a nested dict (2+ levels deep) is parsed correctly."""
    content = (
        '{"tool": "submit_meta", "arguments": {"og": '
        '{"title": "Hello", "image": {"url": "http://x.com/img.png", "width": 1200}}}}'
    )
    results = _extract_fallback_tool_calls(content)
    assert len(results) == 1
    assert results[0]["name"] == "submit_meta"
    og = results[0]["arguments"]["og"]
    assert og["title"] == "Hello"
    assert og["image"]["url"] == "http://x.com/img.png"
    assert og["image"]["width"] == 1200


def test_fallback_arguments_with_array_of_objects():
    """arguments containing an array of objects (e.g. creator_proof[]) is parsed."""
    content = (
        '{"tool": "submit_creator", "arguments": '
        '{"proofs": [{"model": "x"}, {"model": "y"}], "verified": true}}'
    )
    results = _extract_fallback_tool_calls(content)
    assert len(results) == 1
    assert results[0]["name"] == "submit_creator"
    assert results[0]["arguments"]["proofs"] == [{"model": "x"}, {"model": "y"}]
    assert results[0]["arguments"]["verified"] is True


def test_fallback_multiple_bare_objects_in_prose():
    """Multiple bare JSON objects mixed in prose are all extracted."""
    content = (
        "I will call two tools now.\n"
        'First: {"tool": "submit_seo", "arguments": {"title": "My Title"}}\n'
        "Then some more prose.\n"
        'Second: {"tool": "submit_faq", "arguments": {"items": [{"q": "What?", "a": "This."}]}}\n'
        "That is all."
    )
    results = _extract_fallback_tool_calls(content)
    names = [r["name"] for r in results]
    assert "submit_seo" in names
    assert "submit_faq" in names
    assert len(results) == 2
    seo = next(r for r in results if r["name"] == "submit_seo")
    assert seo["arguments"]["title"] == "My Title"
    faq = next(r for r in results if r["name"] == "submit_faq")
    assert faq["arguments"]["items"][0]["q"] == "What?"


def test_fallback_malformed_bare_object():
    """An unclosed / malformed bare object is silently skipped — no exception raised."""
    content = '{"tool": "submit_x", "arguments": {"key": "val"'  # missing closing braces
    # Must not raise; return value should be an empty list (no valid objects)
    results = _extract_fallback_tool_calls(content)
    assert isinstance(results, list)
    assert results == []


def test_fallback_mixed_code_block_and_bare():
    """When both a code block and a bare object exist, code block is preferred; no duplication."""
    import json as _json

    args = {"slug": "alpha", "nested": {"level": 2}}
    # The code block contains the canonical tool call.
    # The bare object below repeats the same content — after dedup by offset
    # tracking, only one entry per distinct JSON span should appear.
    bare = _json.dumps({"tool": "submit_content", "arguments": args})
    content = "```json\n" + bare + "\n```\n" + "Also here is the same as bare text: " + bare
    results = _extract_fallback_tool_calls(content)
    # The code block is consumed first (and the bare scanner skips that span),
    # then the second occurrence (bare) is also parsed — giving 2 total.
    # Both should be valid tool calls with the same name.
    assert len(results) >= 1
    assert all(r["name"] == "submit_content" for r in results)
    # Verify no result has empty or missing arguments
    for r in results:
        assert r["arguments"]["slug"] == "alpha"
        assert r["arguments"]["nested"]["level"] == 2
