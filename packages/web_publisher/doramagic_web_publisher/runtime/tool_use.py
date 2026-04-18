"""MiniMax-compatible tool_use loop built on top of LLMAdapter.

LLMAdapter.generate_with_tools() already handles Anthropic tool_use natively.
This module provides a synchronous multi-turn loop that:
  1. Sends system + user messages + tool definitions to LLM
  2. Detects tool_call responses (finish_reason == "tool_use")
  3. Executes tool calls via registered handlers
  4. Appends tool results and re-prompts
  5. Repeats until LLM calls a submit_* tool or returns stop or max_iter reached

For providers that do not natively support tool_use (MiniMax, zhipu etc.),
LLMAdapter._fallback_prompt_tools() serialises the tool schema into the prompt
and asks the model to respond with JSON — this module does NOT need to special-case
that, it just reads LLMResponse.tool_calls regardless of the backend.

Usage:
    executor = ToolUseExecutor(
        adapter=adapter,
        model_id="claude-sonnet-4-6",
        system_prompt="...",
        tools=[LLMToolDefinition(name="submit_content_fields", ...)],
        submit_tool_name="submit_content_fields",
        max_iter=5,
    )
    result = executor.run(initial_user_message)
    # result.tool_calls[0].arguments  ← the submitted fields dict
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from doramagic_shared_utils.llm_adapter import (
    LLMAdapter,
    LLMMessage,
    LLMResponse,
    LLMToolDefinition,
)

from doramagic_web_publisher.errors import (
    ToolUseMaxIterationsError,
    ToolUseStoppedWithoutSubmitError,
)
from doramagic_web_publisher.runtime.models import ToolCall, ToolCallResult

logger = logging.getLogger(__name__)

_DEFAULT_MAX_ITER = 5

# Regex to find fallback JSON tool calls inside ```json ... ``` code blocks.
# Bare-object scanning is handled separately via json.JSONDecoder().raw_decode()
# to support nested objects (which the flat regex cannot handle correctly).
_FALLBACK_CODE_BLOCK_RE = re.compile(
    r"```json\s*(\{[^`]+\})\s*```",
    re.DOTALL,
)


def _extract_fallback_tool_calls(content: str) -> list[dict]:
    """Parse zero or more fallback tool-call JSON objects from a content string.

    LLMAdapter._fallback_prompt_tools() asks the model to respond with:
        {"tool": "tool_name", "arguments": {...}}

    Supports:
    - JSON wrapped in ```json ... ``` code blocks  (checked first, preferred)
    - Bare JSON objects containing "tool" and "arguments" keys (supports nesting)
    - Multiple tool calls (parallel) embedded in the same content

    Returns a list of normalised dicts with keys: id, name, arguments.
    """
    results: list[dict] = []
    # Track character spans already consumed by code-block matches to avoid
    # double-counting them during the bare-object scan below.
    code_block_spans: list[tuple[int, int]] = []

    # --- Pass 1: code blocks (```json ... ```) — highest priority ---
    for match in _FALLBACK_CODE_BLOCK_RE.finditer(content):
        raw = (match.group(1) or "").strip()
        code_block_spans.append((match.start(), match.end()))
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("_extract_fallback_tool_calls: code-block parse failed: %r", raw)
            continue
        if not isinstance(obj, dict):
            continue
        tool_name = obj.get("tool")
        arguments = obj.get("arguments", {})
        if not isinstance(tool_name, str) or not tool_name:
            continue
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {"_raw": arguments}
        results.append(
            {
                "id": f"fallback_{len(results)}",
                "name": tool_name,
                "arguments": arguments,
            }
        )

    # --- Pass 2: bare JSON objects — scan with raw_decode to handle nesting ---
    # raw_decode(s, idx) tries to decode one JSON value starting at position idx.
    # It returns (obj, end_pos) on success; raises JSONDecodeError on failure.
    # We iterate over every '{' in the string as a candidate start position.
    # Characters inside strings (which may contain '{') are naturally handled
    # because raw_decode will succeed on the outer object and we advance offset
    # past the entire object — so inner '{' characters are never used as
    # independent start positions once the outer object is consumed.
    decoder = json.JSONDecoder()
    offset = 0
    while offset < len(content):
        next_brace = content.find("{", offset)
        if next_brace == -1:
            break

        # Skip positions that fall inside a code block already consumed above.
        in_code_block = any(start <= next_brace < end for start, end in code_block_spans)
        if in_code_block:
            # Jump past the end of the code block
            for start, end in code_block_spans:
                if start <= next_brace < end:
                    offset = end
                    break
            continue

        try:
            obj, end_pos = decoder.raw_decode(content, next_brace)
        except json.JSONDecodeError:
            # Not a valid JSON object starting here; try the next '{'
            offset = next_brace + 1
            continue

        # Advance offset past this object to avoid re-processing its interior.
        offset = end_pos

        if not isinstance(obj, dict):
            continue
        tool_name = obj.get("tool")
        arguments = obj.get("arguments")
        # Must have both "tool" (str) and "arguments" (dict) to be a valid tool call.
        if not isinstance(tool_name, str) or not tool_name:
            continue
        if not isinstance(arguments, dict):
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {"_raw": arguments}
            else:
                continue
        results.append(
            {
                "id": f"fallback_{len(results)}",
                "name": tool_name,
                "arguments": arguments,
            }
        )

    return results


def _normalize_fallback_response(response: LLMResponse) -> LLMResponse:
    """If response has no tool_calls but content contains fallback JSON, synthesise tool_calls.

    This is a no-op when:
    - response already has native tool_calls (provider supports native tools)
    - content contains no fallback JSON patterns

    Returns the (possibly mutated) response object.
    Only activates in the fallback scenario.
    """
    if response.tool_calls:
        # Already has native tool_calls — nothing to do
        return response
    content = response.content or ""
    parsed = _extract_fallback_tool_calls(content)
    if not parsed:
        return response
    # Inject synthesised tool_calls into the response
    response.tool_calls = parsed
    if parsed:
        response.finish_reason = "tool_use"
    logger.debug(
        "_normalize_fallback_response: synthesised %d tool_call(s) from content",
        len(parsed),
    )
    return response


class ToolUseResult:
    """Return value of a completed tool-use loop.

    Attributes:
        submitted_args: Arguments dict from the final submit_* tool call.
                        None if the loop ended without a submit call (rare for stop reason).
        llm_response: The final LLMResponse that terminated the loop.
        iterations: Total number of LLM turns used.
        all_tool_calls: Every tool call encountered (including non-submit ones).
        client_input_chars: Total characters sent to LLM across all turns (client-side count).
        client_output_chars: Total chars received from LLM across all turns (client-side count).

    Note on token counting:
        MiniMax Anthropic endpoint reports prompt_tokens that are far lower than actual
        (observed: ~81 reported vs ~1800 actual on Day 0.5). client_input_chars /
        client_output_chars provide character-level accounting as a reliable alternative.
        Approximate token count: (client_input_chars + client_output_chars) / 4.
    """

    def __init__(
        self,
        submitted_args: dict[str, Any] | None,
        llm_response: LLMResponse,
        iterations: int,
        all_tool_calls: list[ToolCall],
        client_input_chars: int = 0,
        client_output_chars: int = 0,
    ) -> None:
        self.submitted_args = submitted_args
        self.llm_response = llm_response
        self.iterations = iterations
        self.all_tool_calls = all_tool_calls
        self.client_input_chars = client_input_chars
        self.client_output_chars = client_output_chars


class ToolUseExecutor:
    """Drives a multi-turn LLM tool-use loop.

    This is the heart of the web_publisher pipeline.
    Each Phase instantiates one executor, passes its submit_tool schema,
    and calls run() with the phase-specific user prompt.

    The loop:
        iter 0: [system, user] → LLM
        iter N: [system, user, assistant(tool_calls), tool_results, ...] → LLM
        stop when: LLM calls submit_tool_name OR finish_reason == "stop" OR max_iter

    Parallel tool calls in a single turn are supported: all tool calls in the
    response are executed concurrently (serially in this implementation —
    tool execution is just dict passing, no I/O), then all results are appended
    as separate tool-result messages before the next LLM turn.
    """

    def __init__(
        self,
        adapter: LLMAdapter,
        model_id: str,
        system_prompt: str,
        tools: list[LLMToolDefinition],
        submit_tool_name: str,
        *,
        max_iter: int = _DEFAULT_MAX_ITER,
        temperature: float = 0.1,
        max_tokens: int = 8192,
    ) -> None:
        self._adapter = adapter
        self._model_id = model_id
        self._system_prompt = system_prompt
        self._tools = tools
        self._submit_tool_name = submit_tool_name
        self._max_iter = max_iter
        self._temperature = temperature
        self._max_tokens = max_tokens

    def run(self, user_message: str) -> ToolUseResult:
        """Execute the tool-use loop synchronously.

        Args:
            user_message: The initial user turn content.

        Returns:
            ToolUseResult with submitted_args and metadata.

        Raises:
            ToolUseMaxIterationsError: If max_iter reached without a submit call.
            ToolUseError: On unrecoverable LLM or tool execution errors.
        """
        import time as _time

        conversation: list[LLMMessage] = [
            LLMMessage(role="user", content=user_message),
        ]

        all_tool_calls: list[ToolCall] = []
        submitted_args: dict[str, Any] | None = None
        last_response: LLMResponse | None = None
        total_client_input_chars: int = 0
        total_client_output_chars: int = 0

        loop_start = _time.monotonic()
        logger.info(
            "ToolUseExecutor [%s] starting: model=%s max_iter=%d",
            self._submit_tool_name,
            self._model_id,
            self._max_iter,
        )

        for iteration in range(self._max_iter):
            # Measure input chars: system + all conversation messages
            input_text = self._system_prompt + "".join((msg.content or "") for msg in conversation)
            iter_input_chars = len(input_text)
            total_client_input_chars += iter_input_chars

            logger.debug(
                "ToolUseExecutor [%s] iter=%d, messages=%d, input_chars=%d",
                self._submit_tool_name,
                iteration,
                len(conversation),
                iter_input_chars,
            )

            iter_start = _time.monotonic()
            response = self._call_llm(conversation)
            iter_elapsed = _time.monotonic() - iter_start

            # Measure output chars
            output_text = response.content or ""
            iter_output_chars = len(output_text)
            total_client_output_chars += iter_output_chars

            # Normalise fallback JSON embedded in content (MiniMax / non-native tool providers)
            response = _normalize_fallback_response(response)
            last_response = response

            logger.info(
                "ToolUseExecutor [%s] llm: model=%s iter=%d elapsed=%.1fs "
                "input_chars=%d output_chars=%d "
                "prompt_tokens=%d(reported) completion_tokens=%d(reported)",
                self._submit_tool_name,
                self._model_id,
                iteration,
                iter_elapsed,
                iter_input_chars,
                iter_output_chars,
                response.prompt_tokens,
                response.completion_tokens,
            )

            logger.debug(
                "ToolUseExecutor iter=%d finish_reason=%s tool_calls=%d",
                iteration,
                response.finish_reason,
                len(response.tool_calls),
            )

            if not response.has_tool_calls:
                # LLM returned text without calling a tool.
                # This can happen when the model is uncertain or the prompt isn't
                # explicit enough. We append as assistant text and re-prompt once.
                if response.finish_reason == "stop" and iteration == 0:
                    # First turn, no tool calls — treat as soft failure, re-prompt.
                    logger.warning(
                        "ToolUseExecutor: LLM returned stop without tool call on iter 0; "
                        "re-prompting with reminder."
                    )
                    conversation.append(
                        LLMMessage(role="assistant", content=response.content or "")
                    )
                    conversation.append(
                        LLMMessage(
                            role="user",
                            content=(
                                "Please call the required submit tool with your output. "
                                f"Tool name: {self._submit_tool_name}"
                            ),
                        )
                    )
                    continue
                # Otherwise, LLM explicitly stopped without submitting — distinct error.
                logger.info(
                    "ToolUseExecutor: loop ended without submit (finish_reason=%s, iter=%d)",
                    response.finish_reason,
                    iteration,
                )
                raise ToolUseStoppedWithoutSubmitError(
                    self._submit_tool_name, iteration, response.finish_reason or "stop"
                )

            # Parse tool calls from the response.
            turn_tool_calls = self._parse_tool_calls(response)
            all_tool_calls.extend(turn_tool_calls)

            # Build the assistant message that contains tool_calls.
            assistant_msg = LLMMessage(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            )
            conversation.append(assistant_msg)

            # Execute each tool call and collect results.
            tool_result_messages: list[LLMMessage] = []
            for tc in turn_tool_calls:
                if tc.name == self._submit_tool_name:
                    # This is the terminal submit call — capture args and stop.
                    submitted_args = tc.arguments
                    logger.info(
                        "ToolUseExecutor: submit tool '%s' called on iter %d",
                        tc.name,
                        iteration,
                    )
                    # Append a synthetic tool result so the conversation is valid,
                    # then break out of the iteration loop.
                    tool_result_messages.append(
                        LLMMessage(
                            role="tool",
                            content=json.dumps({"status": "accepted"}),
                            tool_call_id=tc.id,
                        )
                    )
                    conversation.extend(tool_result_messages)
                    total_elapsed = _time.monotonic() - loop_start
                    logger.info(
                        "ToolUseExecutor [%s] completed: iterations=%d "
                        "total_elapsed=%.1fs client_input_chars=%d client_output_chars=%d "
                        "approx_tokens=%d",
                        self._submit_tool_name,
                        iteration + 1,
                        total_elapsed,
                        total_client_input_chars,
                        total_client_output_chars,
                        (total_client_input_chars + total_client_output_chars) // 4,
                    )
                    # Return immediately — no need for another LLM turn.
                    return ToolUseResult(
                        submitted_args=submitted_args,
                        llm_response=response,
                        iterations=iteration + 1,
                        all_tool_calls=all_tool_calls,
                        client_input_chars=total_client_input_chars,
                        client_output_chars=total_client_output_chars,
                    )
                else:
                    # Non-submit tool — execute it and collect result.
                    result = self._execute_tool(tc)
                    tool_result_messages.append(
                        LLMMessage(
                            role="tool",
                            content=result.output,
                            tool_call_id=tc.id,
                        )
                    )

            conversation.extend(tool_result_messages)

        # Exhausted iterations.
        if submitted_args is None:
            raise ToolUseMaxIterationsError(self._submit_tool_name, self._max_iter)

        # Should never reach here (submit returns early), but for safety:
        return ToolUseResult(
            submitted_args=submitted_args,
            llm_response=last_response,  # type: ignore[arg-type]
            iterations=self._max_iter,
            all_tool_calls=all_tool_calls,
            client_input_chars=total_client_input_chars,
            client_output_chars=total_client_output_chars,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_llm(self, conversation: list[LLMMessage]) -> LLMResponse:
        """Call LLMAdapter.generate_with_tools synchronously.

        LLMAdapter.chat() is synchronous; generate_with_tools is async.
        We use the same asyncio bridge pattern as LLMAdapter.chat().
        """
        import asyncio
        import concurrent.futures

        async def _async_call() -> LLMResponse:
            return await self._adapter.generate_with_tools(
                self._model_id,
                conversation,
                self._tools,
                system=self._system_prompt,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )

        def _run() -> LLMResponse:
            return asyncio.run(_async_call())

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(_run).result()
        return _run()

    def _parse_tool_calls(self, response: LLMResponse) -> list[ToolCall]:
        """Convert raw tool_calls from LLMResponse to typed ToolCall objects."""
        result: list[ToolCall] = []
        for raw in response.tool_calls:
            tc_id = raw.get("id", f"tc_{len(result)}")
            name = raw.get("name", "")
            arguments = raw.get("arguments", {})

            # LLMAdapter may return arguments as string (JSON) for some providers.
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    logger.warning("Could not parse tool call arguments as JSON: %r", arguments)
                    arguments = {"_raw": arguments}

            result.append(ToolCall(id=tc_id, name=name, arguments=arguments))
        return result

    def _execute_tool(self, tc: ToolCall) -> ToolCallResult:
        """Execute a non-submit tool call.

        In the current design, all tools are submit_* tools.
        This method exists for future extensibility (e.g., a search tool).
        """
        logger.debug("ToolUseExecutor: executing non-submit tool '%s'", tc.name)
        return ToolCallResult(
            tool_call_id=tc.id,
            tool_name=tc.name,
            output=json.dumps(
                {
                    "error": (
                        f"Unknown tool '{tc.name}'. Only '{self._submit_tool_name}' is supported."
                    ),
                }
            ),
        )
