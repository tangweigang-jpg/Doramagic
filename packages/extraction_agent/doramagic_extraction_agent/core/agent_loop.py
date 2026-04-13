"""Autonomous extraction agent driven by LLM tool_use.

The ``ExtractionAgent`` supports two API formats:

- **Anthropic** (default): Anthropic Messages API via ``anthropic`` SDK.
  Used by MiniMax, Claude, and other Anthropic-compatible endpoints.
- **OpenAI**: OpenAI Chat Completions API via ``httpx``.
  Used by GLM-5 (Bailian/DashScope), GPT-4o, DeepSeek, and other
  OpenAI-compatible endpoints.

The format is auto-detected from ``api_format`` parameter, or can be
explicitly set.  The rest of the pipeline (phases, tools, prompts) is
completely unaware of which backend is used.

Typical usage::

    agent = ExtractionAgent(
        adapter, registry,
        model_id="glm-5",
        api_format="openai",  # or "anthropic" (default)
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx
from doramagic_shared_utils.llm_adapter import LLMAdapter, LLMResponse
from pydantic import BaseModel, ValidationError

from doramagic_extraction_agent.core.circuit_breaker import CircuitBreaker
from doramagic_extraction_agent.core.context_manager import ContextManager
from doramagic_extraction_agent.core.message import AgentMessage, ToolResult
from doramagic_extraction_agent.core.tool_registry import ToolRegistry
from doramagic_extraction_agent.sop.schemas_v5 import RawFallback

logger = logging.getLogger(__name__)

_T = TypeVar("_T", bound=BaseModel)

# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------

_RETRY_DELAYS = (1, 2, 4)  # seconds between successive attempts
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 529}

# Transport-layer retry delays for 529/429/5xx errors in run_structured_call.
# Longer than _RETRY_DELAYS to give the provider time to recover from overload.
_TRANSPORT_RETRY_DELAYS = (5, 10, 20, 40)

# Keywords checked against str(exc) to identify transport-layer errors.
_TRANSPORT_ERROR_MARKERS = ("529", "429", "500", "502", "503", "overloaded", "overload")

# ---------------------------------------------------------------------------
# Token budget estimation
# ---------------------------------------------------------------------------

_TOKEN_BUDGET_WARN = 60_000  # warn level: soft budget
_TOKEN_BUDGET_MAX = 120_000  # error level: hard budget


# ---------------------------------------------------------------------------
# L2 example instance builder
# ---------------------------------------------------------------------------


def _build_example_instance(model: type[BaseModel]) -> dict[str, Any]:
    """Build a placeholder JSON instance from a Pydantic model.

    Produces a concrete "form to fill in" instead of a JSON Schema definition.
    MiniMax M2.7 echoes back schema definitions ($defs, $ref) but reliably
    fills in concrete examples.
    """
    result: dict[str, Any] = {}
    for name, field_info in model.model_fields.items():
        annotation = field_info.annotation
        # Unwrap Optional
        origin = getattr(annotation, "__origin__", None)
        args = getattr(annotation, "__args__", ())

        if annotation is str or annotation == str:
            result[name] = f"<{name}>"
        elif annotation is int or annotation == int:
            result[name] = 0
        elif annotation is float or annotation == float:
            result[name] = 0.0
        elif annotation is bool or annotation == bool:
            result[name] = False
        elif origin is list or (hasattr(annotation, "__origin__") and str(origin) == "typing.List"):
            # list[X] → [example_of_X]
            item_type = args[0] if args else str
            if isinstance(item_type, type) and issubclass(item_type, BaseModel):
                result[name] = [_build_example_instance(item_type)]
            else:
                result[name] = [f"<{name}_item>"]
        elif origin is dict:
            result[name] = {f"<key>": f"<value>"}
        elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
            result[name] = _build_example_instance(annotation)
        else:
            # Fallback for Optional, Literal, Union, etc.
            if field_info.default is not None and field_info.default is not ...:
                result[name] = field_info.default
            elif field_info.default_factory is not None:
                result[name] = field_info.default_factory()
            else:
                result[name] = f"<{name}>"
    return result

# ---------------------------------------------------------------------------
# Convergence detection (Diminishing Returns)
# ---------------------------------------------------------------------------

_CONVERGENCE_PATIENCE = 3  # consecutive small-delta iterations before stopping
_CONVERGENCE_THRESHOLD = 0.05  # artifact growth < 5% of previous = "small delta"
_MAX_TOOL_RESULTS_KEPT = 8  # LRU cap for microcompact


class ConvergenceDetector:
    """Detect when a Worker has exhausted useful information.

    Tracks artifact size across iterations.  When consecutive growth
    drops below *threshold* for *patience* rounds, signals convergence.

    Design source: Claude Code ``tokenBudget.ts`` — diminishing-returns
    early stopping saves 15-30 % Worker-phase tokens.
    """

    def __init__(
        self,
        patience: int = _CONVERGENCE_PATIENCE,
        threshold: float = _CONVERGENCE_THRESHOLD,
    ) -> None:
        self.patience = patience
        self.threshold = threshold
        self._prev_size: int = 0
        self._small_delta_count: int = 0

    def update(self, artifacts: dict[str, str]) -> bool:
        """Return ``True`` when the Worker should stop early."""
        current_size = sum(len(v) for v in artifacts.values())
        if self._prev_size > 0:
            delta = current_size - self._prev_size
            if delta < self._prev_size * self.threshold:
                self._small_delta_count += 1
            else:
                self._small_delta_count = 0
        elif self._prev_size == 0 and current_size == 0 and self._small_delta_count >= 0:
            # Worker producing nothing across iterations — count as small delta
            self._small_delta_count += 1
        self._prev_size = current_size
        return self._small_delta_count >= self.patience


def microcompact(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """LRU-clear old tool results to prevent context bloat.

    Only clears *regenerable* content (tool outputs).  User and assistant
    messages are never touched because they are not regenerable.

    Design source: Claude Code Layer-1 Microcompact.
    """
    tool_indices = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    if len(tool_indices) <= _MAX_TOOL_RESULTS_KEPT:
        return messages
    for idx in tool_indices[:-_MAX_TOOL_RESULTS_KEPT]:
        messages[idx]["content"] = "[cleared — regenerable tool result]"
    return messages


def estimate_tokens(text: str) -> int:
    """Estimate token count without calling a tokenizer.

    Heuristic for mixed Chinese/English/code content:
    - ASCII chars (code, English): ~4 chars per token
    - CJK chars (Chinese): ~1.8 chars per token
    - Safety factor: 1.2x
    - Fixed overhead of 100 tokens for message framing
    """
    if not text:
        return 0
    ascii_count = sum(1 for c in text if ord(c) < 128)
    cjk_count = len(text) - ascii_count
    raw = ascii_count / 4.0 + cjk_count / 1.8
    return int(raw * 1.2) + 100  # overhead for message framing


def _is_transport_error(exc: BaseException) -> bool:
    """Return True if *exc* looks like a transient transport / overload error.

    Checks for HTTP status codes and provider overload messages.  When the
    exception carries a ``last_completion`` (Instructor got a response from
    the API but couldn't parse it — e.g. ThinkingBlock instead of ToolUseBlock),
    it is NOT a transport error: the API responded successfully, but the
    response structure didn't match Instructor's expectations.  Retrying
    the same request won't help — fall through to L1.5/L2 instead.
    """
    # If Instructor received a completion, the API responded — not a transport issue.
    if getattr(exc, "last_completion", None) is not None:
        return False

    exc_str = str(exc).lower()
    return any(marker in exc_str for marker in _TRANSPORT_ERROR_MARKERS)


# Two-tier httpx timeouts:
# - FAST: for agent loop tool-use calls. MiniMax TTFT can exceed 120s with
#   large context (worker_arch on zvt: 170K+ tokens), so 240s is the safe floor.
# - LONG: for Instructor structured calls (non-streaming, MiniMax can take 2-4 min).
_LLM_TIMEOUT_FAST = httpx.Timeout(connect=30, read=240, write=30, pool=60)
_LLM_TIMEOUT_LONG = httpx.Timeout(connect=30, read=360, write=30, pool=60)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class PhaseResult:
    """Outcome of a single agent phase.

    Attributes:
        phase_name: Name passed to ``run_phase``.
        status: One of ``"completed"``, ``"circuit_break"``,
            ``"max_iterations"``, ``"error"``.
        iterations: Number of LLM calls made.
        total_tokens: Cumulative prompt + completion tokens consumed.
        final_text: Last text content returned by the model (only set when
            ``status == "completed"``).
        error: Human-readable error description (set when status is not
            ``"completed"``).
    """

    phase_name: str
    status: str  # "completed" | "circuit_break" | "max_iterations" | "error"
    iterations: int = 0
    total_tokens: int = 0
    final_text: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class ExtractionAgent:
    """Autonomous extraction agent driven by LLM tool_use.

    Drives a multi-turn conversation by repeatedly calling the model,
    executing the requested tools, and feeding results back until the
    model stops issuing tool calls or a safety limit is reached.

    Supports both Anthropic and OpenAI API formats via ``api_format``.
    """

    def __init__(
        self,
        adapter: LLMAdapter,
        tool_registry: ToolRegistry,
        *,
        max_iterations: int = 200,
        max_consecutive_failures: int = 3,
        max_tokens_per_call: int = 16384,
        model_id: str = "",
        context_manager: ContextManager | None = None,
        checkpoint_mgr: Any | None = None,
        api_format: str = "anthropic",
    ) -> None:
        self._adapter = adapter
        self._tool_registry = tool_registry
        self._max_iterations = max_iterations
        self._max_consecutive_failures = max_consecutive_failures
        self._max_tokens_per_call = max_tokens_per_call
        self._model_id = model_id or adapter._default_model
        self._context_manager = context_manager
        self._checkpoint_mgr = checkpoint_mgr
        self._api_format = api_format  # "anthropic" or "openai"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_phase(
        self,
        phase_name: str,
        system_prompt: str,
        initial_user_message: str,
        *,
        allowed_tools: list[str] | None = None,
        max_iterations: int | None = None,
    ) -> PhaseResult:
        """Run one phase of the extraction SOP.

        Drives the tool_use loop until the model stops calling tools, a
        circuit-breaker limit fires, or the iteration cap is reached.
        """
        effective_max = max_iterations if max_iterations is not None else self._max_iterations
        registry = (
            self._tool_registry.filter(allowed_tools)
            if allowed_tools is not None
            else self._tool_registry
        )

        # Get tool definitions in the right format
        if self._api_format == "openai":
            api_tools = self._convert_tools_to_openai(registry.get_api_tools())
        else:
            api_tools = registry.get_api_tools()

        # Build initial conversation history
        if self._api_format == "openai":
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": initial_user_message},
            ]
        else:
            messages = [
                {"role": "user", "content": initial_user_message},
            ]

        _compaction_seq: int = 0

        cb = CircuitBreaker(
            max_consecutive=self._max_consecutive_failures,
            max_total=effective_max,
        )

        logger.info(
            "ExtractionAgent.run_phase(%r) start — model=%s tools=%d max_iter=%d",
            phase_name,
            self._model_id,
            len(registry),
            effective_max,
        )

        while True:
            cb.increment_iterations()
            should_stop, reason = cb.should_break()
            if should_stop and "max iterations" in reason:
                logger.warning("Phase %r hit iteration cap: %s", phase_name, reason)
                return PhaseResult(
                    phase_name=phase_name,
                    status="max_iterations",
                    iterations=cb.stats["total_iterations"],
                    total_tokens=cb.stats["total_tokens"],
                    error=reason,
                )

            # --- LLM call (with context overflow recovery) ---
            try:
                if self._api_format == "openai":
                    response, raw_resp = await self._raw_openai_call(
                        system_prompt, messages, api_tools
                    )
                else:
                    response, raw_resp = await self._raw_anthropic_call(
                        system_prompt, messages, api_tools
                    )
            except Exception as exc:
                exc_str = str(exc)
                is_overflow = (
                    "context window exceeds limit" in exc_str
                    or "prompt is too long" in exc_str.lower()
                )
                if is_overflow:
                    logger.warning(
                        "Phase %r: context overflow (%d messages) — aggressive compact and retry",
                        phase_name,
                        len(messages),
                    )
                    if self._context_manager and len(messages) > 2:
                        messages, _ = self._context_manager.summarize_messages(
                            messages,
                            keep_last_n=2,
                        )
                        logger.info("Aggressive compact: %d messages remain", len(messages))
                        continue
                # Include exception type for errors with empty str() (e.g. httpx.ReadTimeout)
                error_detail = exc_str if exc_str else f"{type(exc).__name__}"
                logger.exception("Phase %r: LLM call failed:\n%s", phase_name, error_detail)
                return PhaseResult(
                    phase_name=phase_name,
                    status="error",
                    iterations=cb.stats["total_iterations"],
                    total_tokens=cb.stats["total_tokens"],
                    error=error_detail,
                )

            call_tokens = response.prompt_tokens + response.completion_tokens
            cb.add_tokens(call_tokens)
            logger.debug(
                "Phase %r iter=%d tokens=%d (+%d) tool_calls=%d",
                phase_name,
                cb.stats["total_iterations"],
                cb.stats["total_tokens"],
                call_tokens,
                len(response.tool_calls),
            )

            # --- Append assistant turn ---
            assistant_dict = self._build_assistant_message(raw_resp)
            messages.append(assistant_dict)

            # --- No tool calls → model is done ---
            if not response.has_tool_calls:
                logger.info(
                    "Phase %r completed in %d iterations, %d tokens",
                    phase_name,
                    cb.stats["total_iterations"],
                    cb.stats["total_tokens"],
                )
                return PhaseResult(
                    phase_name=phase_name,
                    status="completed",
                    iterations=cb.stats["total_iterations"],
                    total_tokens=cb.stats["total_tokens"],
                    final_text=response.content,
                )

            # --- Execute tools ---
            tool_results: list[ToolResult] = []
            for tc in response.tool_calls:
                result = await registry.execute(tc["name"], tc["arguments"])
                result = ToolResult(
                    tool_use_id=tc["id"],
                    content=result.content,
                    is_error=result.is_error,
                )
                tool_results.append(result)

                if result.is_error:
                    cb.record_failure(result.content)
                    logger.warning(
                        "Phase %r: tool %r failed: %s",
                        phase_name,
                        tc["name"],
                        result.content,
                    )
                else:
                    cb.record_success()

            # --- Append tool-result turn ---
            results_dict = self._build_tool_results_message(tool_results)
            if isinstance(results_dict, list):
                messages.extend(results_dict)
            else:
                messages.append(results_dict)

            # --- Context window management ---
            if self._context_manager is not None:
                _probe = [{"role": "system", "content": system_prompt}, *messages]
                if self._context_manager.should_summarize(_probe):
                    if self._checkpoint_mgr is not None:
                        self._checkpoint_mgr.archive_conversation(
                            phase_name, messages, sequence=_compaction_seq
                        )
                    messages, _summary = self._context_manager.summarize_messages(messages)
                    _compaction_seq += 1
                    logger.info(
                        "Phase %r: context compacted (event #%d) — %d messages after compaction",
                        phase_name,
                        _compaction_seq,
                        len(messages),
                    )

            # --- Check circuit breaker ---
            should_stop, reason = cb.should_break()
            if should_stop:
                logger.warning("Phase %r circuit breaker opened: %s", phase_name, reason)
                return PhaseResult(
                    phase_name=phase_name,
                    status="circuit_break",
                    iterations=cb.stats["total_iterations"],
                    total_tokens=cb.stats["total_tokens"],
                    error=reason,
                )

    # ------------------------------------------------------------------
    # Anthropic backend
    # ------------------------------------------------------------------

    async def _raw_anthropic_call(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        api_tools: list[dict[str, Any]],
        *,
        long_timeout: bool = False,
    ) -> tuple[LLMResponse, Any]:
        """Call the Anthropic-compatible endpoint directly."""
        import anthropic

        adapter = self._adapter
        timeout = _LLM_TIMEOUT_LONG if long_timeout else _LLM_TIMEOUT_FAST

        def _make_client() -> anthropic.AsyncAnthropic:
            kw: dict[str, Any] = {}
            if adapter._base_url:
                kw["base_url"] = adapter._base_url
            if adapter._api_key:
                kw["api_key"] = adapter._api_key
            kw["timeout"] = timeout
            return anthropic.AsyncAnthropic(**kw)

        suffix = ":long" if long_timeout else ""
        client_key = f"anthropic:{adapter._base_url or 'default'}{suffix}"
        client: anthropic.AsyncAnthropic = adapter._get_or_create_client(client_key, _make_client)

        temperature = adapter._resolve_temperature(0.0, self._model_id)

        for attempt, delay in enumerate((*_RETRY_DELAYS, None)):
            try:
                resp = await client.messages.create(
                    model=self._model_id,
                    system=system_prompt,
                    messages=messages,  # type: ignore[arg-type]
                    tools=api_tools,  # type: ignore[arg-type]
                    max_tokens=self._max_tokens_per_call,
                    temperature=temperature,
                )
                break
            except Exception as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None) or getattr(
                    exc, "status_code", None
                )
                is_retryable = (
                    isinstance(exc, (ConnectionError, TimeoutError))
                    or status in _RETRYABLE_STATUS_CODES
                    or isinstance(exc, anthropic.APITimeoutError)
                )
                if is_retryable and delay is not None:
                    logger.warning(
                        "_raw_anthropic_call attempt %d failed: %s — retrying in %ds",
                        attempt + 1,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        for block in resp.content:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_parts.append(block.text)
            elif block_type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "arguments": block.input,
                    }
                )

        llm_response = LLMResponse(
            content="\n".join(text_parts) if text_parts else "",
            model_id=self._model_id,
            finish_reason="tool_use" if tool_calls else (resp.stop_reason or "stop"),
            tool_calls=tool_calls,
            prompt_tokens=resp.usage.input_tokens,
            completion_tokens=resp.usage.output_tokens,
        )
        return llm_response, resp

    # ------------------------------------------------------------------
    # OpenAI backend
    # ------------------------------------------------------------------

    async def _raw_openai_call(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        api_tools: list[dict[str, Any]],
        *,
        long_timeout: bool = False,
    ) -> tuple[LLMResponse, dict[str, Any]]:
        """Call an OpenAI-compatible endpoint via httpx.

        Supports GLM-5, GPT-4o, DeepSeek, and any provider exposing
        the ``/chat/completions`` endpoint with function-calling support.
        """
        adapter = self._adapter
        base_url = (adapter._base_url or "").rstrip("/")
        url = f"{base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {adapter._api_key}",
        }

        temperature = adapter._resolve_temperature(0.0, self._model_id)

        body: dict[str, Any] = {
            "model": self._model_id,
            "messages": messages,
            "max_tokens": self._max_tokens_per_call,
            "temperature": temperature,
        }
        if api_tools:
            body["tools"] = api_tools

        timeout = _LLM_TIMEOUT_LONG if long_timeout else _LLM_TIMEOUT_FAST
        suffix = ":long" if long_timeout else ""
        client_key = f"openai_httpx:{base_url}{suffix}"

        def _make_client() -> httpx.AsyncClient:
            return httpx.AsyncClient(timeout=timeout)

        client: httpx.AsyncClient = adapter._get_or_create_client(client_key, _make_client)

        for attempt, delay in enumerate((*_RETRY_DELAYS, None)):
            try:
                resp = await client.post(url, headers=headers, json=body)
                if resp.status_code in _RETRYABLE_STATUS_CODES:
                    if delay is not None:
                        logger.warning(
                            "_raw_openai_call attempt %d failed: HTTP %d %s — retrying in %ds",
                            attempt + 1,
                            resp.status_code,
                            resp.text[:200],
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    resp.raise_for_status()
                resp.raise_for_status()
                break
            except httpx.TimeoutException as exc:
                if delay is not None:
                    logger.warning(
                        "_raw_openai_call attempt %d timed out: %s — retrying in %ds",
                        attempt + 1,
                        type(exc).__name__,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise
            except httpx.HTTPStatusError:
                raise
            except (ConnectionError, OSError) as exc:
                if delay is not None:
                    logger.warning(
                        "_raw_openai_call attempt %d failed: %s — retrying in %ds",
                        attempt + 1,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

        data = resp.json()
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})

        # Parse text content
        content = msg.get("content") or ""

        # Parse tool calls
        tool_calls: list[dict[str, Any]] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            args = fn.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            tool_calls.append(
                {
                    "id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "arguments": args,
                }
            )

        # Token usage
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        finish_reason = choice.get("finish_reason", "stop")

        llm_response = LLMResponse(
            content=content,
            model_id=self._model_id,
            finish_reason="tool_use" if tool_calls else finish_reason,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return llm_response, data

    # ------------------------------------------------------------------
    # Structured output (v5 — Instructor integration)
    # ------------------------------------------------------------------

    async def run_structured_call(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type[_T],
        *,
        max_retries: int = 1,
        max_tokens: int | None = None,
    ) -> tuple[_T | RawFallback, int]:
        """Make a single LLM call returning a validated Pydantic model.

        max_retries controls Instructor's schema re-ask count (default 1).
        Transport errors (529/429/5xx) are handled by the outer transport
        retry loop, NOT by Instructor's retry. This prevents retry stacking
        (previously 5 transport × 3 Instructor = 15 attempts).

        Uses a three-level degradation chain:

        - **L1**: Instructor structured output via tool_use — the LLM
          returns data matching ``response_model`` or Instructor retries.
        - **L2**: Free-form LLM call → extract JSON → Pydantic validate.
        - **L3**: Return raw text as :class:`RawFallback` (no data lost).

        Args:
            system_prompt: System message for the LLM.
            user_message: User message with full context.
            response_model: Pydantic ``BaseModel`` subclass.
            max_retries: How many times Instructor retries on schema mismatch.

        Returns:
            ``(validated_model, total_tokens)`` or ``(RawFallback, total_tokens)``.
        """
        total_tokens = 0

        # --- Token budget pre-check ---
        input_estimate = estimate_tokens(system_prompt) + estimate_tokens(user_message)
        if input_estimate > _TOKEN_BUDGET_MAX:
            logger.error(
                "run_structured_call: estimated input %d tokens EXCEEDS budget %d — "
                "consider chunking the request",
                input_estimate,
                _TOKEN_BUDGET_MAX,
            )
        elif input_estimate > _TOKEN_BUDGET_WARN:
            logger.warning(
                "run_structured_call: estimated input %d tokens exceeds soft budget %d",
                input_estimate,
                _TOKEN_BUDGET_WARN,
            )
        else:
            logger.debug(
                "run_structured_call: estimated input %d tokens (budget OK)",
                input_estimate,
            )

        l1_partial_text = ""

        effective_max_tokens = max_tokens or self._max_tokens_per_call

        # --- L1: Instructor structured output ---
        # Skip L1 for models known to be incompatible with Instructor
        # (thinking mode + tool_choice=required conflict, never succeeds)
        _skip_l1 = any(
            tag in self._model_id.lower()
            for tag in ("glm-5", "glm-4", "deepseek", "minimax")
        )

        # Outer transport-layer retry loop: 529/429/5xx are retried here with
        # exponential back-off so Instructor never gets a chance to fast-retry
        # them.  Schema / validation errors fall through immediately to L2.
        if _skip_l1:
            logger.info(
                "run_structured_call: L1 skipped for %s (Instructor incompatible) — using L2",
                self._model_id,
            )

        for _t_attempt, _t_delay in enumerate((*_TRANSPORT_RETRY_DELAYS, None)):
            if _skip_l1:
                break  # skip L1 entirely, proceed to L1.5/L2

            try:
                result, tokens = await self._instructor_call(
                    system_prompt,
                    user_message,
                    response_model,
                    max_retries=max_retries,
                    max_tokens=effective_max_tokens,
                )
                total_tokens += tokens
                logger.info(
                    "run_structured_call L1 success: %s (%d tokens)",
                    response_model.__name__,
                    tokens,
                )
                return result, total_tokens
            except (KeyboardInterrupt, asyncio.CancelledError):
                raise
            except Exception as l1_exc:
                if _is_transport_error(l1_exc) and _t_delay is not None:
                    logger.warning(
                        "run_structured_call L1: transport error (attempt %d/%d): "
                        "%s — waiting %ds before retry (NOT degrading to L2)",
                        _t_attempt + 1,
                        len(_TRANSPORT_RETRY_DELAYS),
                        type(l1_exc).__name__,
                        _t_delay,
                    )
                    await asyncio.sleep(_t_delay)
                    continue  # retry L1, do not degrade

                # Non-transport error (schema mismatch, skip flag, or all
                # transport retries exhausted) → fall through to L2.
                logger.warning(
                    "run_structured_call L1 failed (%s): %s — falling back to L2",
                    type(l1_exc).__name__,
                    l1_exc,
                )
                # Instructor exposes retry usage via total_usage or n_attempts
                l1_usage = getattr(l1_exc, "total_usage", None) or getattr(
                    l1_exc, "_tokens_used", None
                )
                if l1_usage is not None:
                    if hasattr(l1_usage, "total_tokens"):
                        total_tokens += l1_usage.total_tokens
                    elif hasattr(l1_usage, "input_tokens"):
                        # Anthropic Usage object: input_tokens + output_tokens
                        total_tokens += (l1_usage.input_tokens or 0) + (l1_usage.output_tokens or 0)
                    elif isinstance(l1_usage, (int, float)):
                        total_tokens += int(l1_usage)

                # Preserve partial completion from L1 for L1.5 salvage.
                # Extract TextBlock text directly from the Message object
                # instead of str(Message) repr (which buries JSON in Python repr).
                last = getattr(l1_exc, "last_completion", None)
                if last is not None:
                    # Try to extract text from content blocks (Anthropic Message)
                    content_blocks = getattr(last, "content", None)
                    if content_blocks and isinstance(content_blocks, list):
                        for block in content_blocks:
                            # TextBlock: contains the actual JSON output
                            block_text = getattr(block, "text", None)
                            if block_text and isinstance(block_text, str) and len(block_text) > 50:
                                l1_partial_text = block_text
                                break
                            # ToolUseBlock: contains parsed input dict
                            block_input = getattr(block, "input", None)
                            if block_input and isinstance(block_input, dict):
                                l1_partial_text = json.dumps(block_input)
                                break
                    # Fallback: str(last) if no blocks found
                    if not l1_partial_text:
                        l1_partial_text = str(last)

                break  # exit transport retry loop, proceed to L2

        # --- L1.5: Try to salvage JSON from L1's completion text ---
        # MiniMax with thinking mode returns [ThinkingBlock, TextBlock] instead
        # of [ToolUseBlock].  Instructor can't parse it, but the TextBlock often
        # contains valid JSON.  Extract + validate before making another API call.
        if l1_partial_text:
            try:
                from doramagic_extraction_agent.sop.executor import _extract_json

                extracted = _extract_json(l1_partial_text, require_type=dict)
                if extracted is not None:
                    validated = response_model.model_validate(extracted)
                    logger.info(
                        "run_structured_call L1.5 success: salvaged %s from L1 completion (%d tokens)",
                        response_model.__name__,
                        total_tokens,
                    )
                    return validated, total_tokens
            except (KeyboardInterrupt, asyncio.CancelledError):
                raise
            except Exception as l15_exc:
                logger.warning(
                    "L1.5 salvage failed: %s: %s — proceeding to L2",
                    type(l15_exc).__name__,
                    l15_exc,
                )

        # --- L2: Free-form call with example instance + _extract_json + model_validate ---
        # Inject a concrete JSON EXAMPLE (not the schema definition) so the
        # model sees "a form to fill in" rather than "metadata to echo back".
        # MiniMax M2.7 frequently echoes raw model_json_schema() output
        # ($defs, $ref, properties) instead of producing data instances.
        schema_hint = ""
        try:
            example = _build_example_instance(response_model)
            example_json = json.dumps(example, indent=2, ensure_ascii=False)
            # List required field names for explicit instruction
            required_fields = [
                name for name, f in response_model.model_fields.items()
                if f.is_required()
            ]
            schema_hint = (
                f"\n\n## REQUIRED OUTPUT FORMAT\n"
                f"Return a single JSON object with EXACTLY this structure. "
                f"Replace the placeholder values with real extracted data:\n"
                f"```json\n{example_json}\n```\n"
                f"CRITICAL: Return actual DATA, NOT a JSON Schema definition. "
                f"Do NOT include $defs, $ref, or 'properties' keys.\n"
                f"Required fields: {', '.join(required_fields)}\n"
            )
        except Exception:
            pass  # Example generation failed; proceed without hint

        raw_text = ""
        l2_message = user_message + schema_hint if schema_hint else user_message
        for _t2_attempt, _t2_delay in enumerate((*_TRANSPORT_RETRY_DELAYS, None)):
            try:
                raw_text, tokens = await self._freeform_call(
                    system_prompt,
                    l2_message,
                    long_timeout=True,
                )
                total_tokens += tokens

                from doramagic_extraction_agent.sop.executor import _extract_json

                # Accept both dict and list — MiniMax often returns lists
                # without the wrapper object (e.g. [{uc1}] instead of
                # {"use_cases": [{uc1}]}).
                extracted = _extract_json(raw_text)
                if extracted is None:
                    raise ValueError("_extract_json returned None")

                # If extracted is a list, try wrapping it in the model's
                # first list field
                if isinstance(extracted, list):
                    for fn, fi in response_model.model_fields.items():
                        origin = getattr(fi.annotation, "__origin__", None)
                        if origin is list:
                            extracted = {fn: extracted}
                            break

                validated = response_model.model_validate(extracted)
                logger.info(
                    "run_structured_call L2 success: %s (%d tokens total)",
                    response_model.__name__,
                    total_tokens,
                )
                return validated, total_tokens
            except (KeyboardInterrupt, asyncio.CancelledError):
                raise
            except (ValidationError, ValueError, TypeError) as l2_exc:
                # Schema/parse errors are not transport errors; go straight to L3.
                logger.warning(
                    "run_structured_call L2 failed (%s): %s — falling back to L3",
                    type(l2_exc).__name__,
                    l2_exc,
                )
                break
            except Exception as l2_exc:
                if _is_transport_error(l2_exc) and _t2_delay is not None:
                    logger.warning(
                        "run_structured_call L2: transport error (attempt %d/%d): "
                        "%s — waiting %ds before retry (NOT degrading to L3)",
                        _t2_attempt + 1,
                        len(_TRANSPORT_RETRY_DELAYS),
                        type(l2_exc).__name__,
                        _t2_delay,
                    )
                    await asyncio.sleep(_t2_delay)
                    continue  # retry L2, do not degrade

                logger.warning(
                    "run_structured_call L2 LLM call failed (%s): %s — falling back to L3",
                    type(l2_exc).__name__,
                    l2_exc,
                )
                break  # exit transport retry loop, proceed to L3

        # --- L3: Universal recovery before returning RawFallback ---
        # Try JSON → YAML → truncated JSON on the raw text. If any parse
        # succeeds AND model_validate passes (lenient), return the validated
        # result instead of RawFallback. This saves EVERY phase handler from
        # implementing its own L3 recovery logic.
        fallback_text = raw_text or l1_partial_text
        if fallback_text:
            import re as _re
            import yaml as _yaml_recover

            from doramagic_extraction_agent.sop.executor import _extract_json as _l3_extract

            # Use _extract_json first (handles fences, prose, bracket scan)
            parsed = _l3_extract(fallback_text)

            # Fallback: strip fences + try YAML + truncated JSON
            if parsed is None:
                cleaned = fallback_text.strip()
                cleaned = _re.sub(r"^```(?:json|yaml)?\s*\n?", "", cleaned)
                cleaned = _re.sub(r"\n?```\s*$", "", cleaned)
                try:
                    parsed = _yaml_recover.safe_load(cleaned)
                except Exception:
                    pass
                if parsed is None:
                    last_complete = cleaned.rfind("},")
                    if last_complete > 0:
                        try:
                            parsed = json.loads(
                                cleaned[:last_complete + 1] + "\n  ]\n}"
                            )
                        except (json.JSONDecodeError, ValueError):
                            pass

            if isinstance(parsed, (dict, list)):
                # Strategy A: direct validation (parsed is the correct shape)
                if isinstance(parsed, dict):
                    try:
                        validated = response_model.model_validate(parsed)
                        logger.info(
                            "run_structured_call L3 recovery success: %s (direct)",
                            response_model.__name__,
                        )
                        return validated, total_tokens
                    except Exception:
                        pass

                # Strategy B: parsed is a list or unwrapped item — wrap it
                # Find the main list field in the model and wrap accordingly
                for field_name, field_info in response_model.model_fields.items():
                    origin = getattr(field_info.annotation, "__origin__", None)
                    if origin is list:
                        items = parsed if isinstance(parsed, list) else [parsed]
                        try:
                            validated = response_model.model_validate(
                                {field_name: items}
                            )
                            logger.info(
                                "run_structured_call L3 recovery success: %s "
                                "(wrapped %d items in '%s')",
                                response_model.__name__,
                                len(items),
                                field_name,
                            )
                            return validated, total_tokens
                        except Exception:
                            continue

                logger.warning(
                    "run_structured_call L3 recovery: parsed %s but all "
                    "validation strategies failed",
                    type(parsed).__name__,
                )

        logger.error(
            "run_structured_call L3: returning raw text fallback (%d chars)",
            len(fallback_text),
        )
        return RawFallback(text=fallback_text, stage="l3_raw"), total_tokens

    async def _instructor_call(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type[_T],
        *,
        max_retries: int = 3,
        max_tokens: int | None = None,
    ) -> tuple[_T, int]:
        """L1: Instructor-wrapped LLM call using tool_use for schema enforcement."""

        adapter = self._adapter
        effective_max_tokens = max_tokens or self._max_tokens_per_call

        if self._api_format == "openai":
            client = self._get_instructor_openai_client(adapter)
            # Disable thinking mode for ALL Instructor structured calls.
            # Instructor sets tool_choice=required, which conflicts with
            # thinking mode on MiniMax, GLM-5, and other providers.
            extra_body: dict[str, Any] = {"thinking": False}
            create_kwargs: dict[str, Any] = {
                "model": self._model_id,
                "response_model": response_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "max_retries": max_retries,
                "max_tokens": effective_max_tokens,
                "temperature": adapter._resolve_temperature(0.0, self._model_id),
            }
            if extra_body:
                create_kwargs["extra_body"] = extra_body
            resp = await client.chat.completions.create(**create_kwargs)
            # instructor returns the Pydantic model directly
            tokens = getattr(resp, "_raw_response", None)
            if tokens and hasattr(tokens, "usage"):
                token_count = (tokens.usage.prompt_tokens or 0) + (
                    tokens.usage.completion_tokens or 0
                )
            else:
                token_count = 0
            return resp, token_count
        else:
            # Anthropic format (MiniMax, Claude)
            client = self._get_instructor_anthropic_client(adapter)
            # Disable thinking mode for Anthropic-format Instructor calls.
            # MiniMax M2.7 returns [ThinkingBlock, ToolUseBlock] when thinking
            # is enabled, but Instructor expects [ToolUseBlock] only.
            # tool_choice=required (set by Instructor) conflicts with thinking.
            #
            # The Anthropic SDK accepts thinking={"type":"disabled"} to suppress
            # ThinkingBlock output.  This is safe for Claude (no-op if model
            # doesn't support extended thinking) and fixes MiniMax.
            create_kwargs_anthropic: dict[str, Any] = {
                "model": self._model_id,
                "response_model": response_model,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_message}],
                "max_retries": max_retries,
                "max_tokens": effective_max_tokens,
                "temperature": adapter._resolve_temperature(0.0, self._model_id),
                "thinking": {"type": "disabled"},
            }
            resp = await client.messages.create(**create_kwargs_anthropic)
            tokens = getattr(resp, "_raw_response", None)
            if tokens and hasattr(tokens, "usage"):
                token_count = (tokens.usage.input_tokens or 0) + (tokens.usage.output_tokens or 0)
            else:
                token_count = 0
            return resp, token_count

    async def _freeform_call(
        self,
        system_prompt: str,
        user_message: str,
        *,
        long_timeout: bool = False,
    ) -> tuple[str, int]:
        """L2: Plain LLM call without structured output, returns (text, tokens).

        Args:
            long_timeout: Use LONG timeout (read=300s) instead of FAST (read=120s).
                Set True when called from run_structured_call L2 fallback,
                where the context is large and generation can be slow.
        """
        if self._api_format == "openai":
            resp, _ = await self._raw_openai_call(
                system_prompt,
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                [],  # no tools
                long_timeout=long_timeout,
            )
        else:
            resp, _ = await self._raw_anthropic_call(
                system_prompt,
                [{"role": "user", "content": user_message}],
                [],  # no tools
                long_timeout=long_timeout,
            )
        tokens = (resp.prompt_tokens or 0) + (resp.completion_tokens or 0)
        return resp.content, tokens

    def _get_instructor_anthropic_client(self, adapter: LLMAdapter) -> Any:
        """Get or create an Instructor-wrapped Anthropic async client."""
        import anthropic
        import instructor

        cache_key = f"instructor_anthropic:{adapter._base_url or 'default'}"

        def _make() -> Any:
            kw: dict[str, Any] = {}
            if adapter._base_url:
                kw["base_url"] = adapter._base_url
            if adapter._api_key:
                kw["api_key"] = adapter._api_key
            kw["timeout"] = _LLM_TIMEOUT_LONG
            raw_client = anthropic.AsyncAnthropic(**kw)
            return instructor.from_anthropic(raw_client)

        return adapter._get_or_create_client(cache_key, _make)

    def _get_instructor_openai_client(self, adapter: LLMAdapter) -> Any:
        """Get or create an Instructor-wrapped OpenAI async client."""
        import instructor
        import openai

        cache_key = f"instructor_openai:{adapter._base_url or 'default'}"

        def _make() -> Any:
            kw: dict[str, Any] = {}
            if adapter._base_url:
                kw["base_url"] = adapter._base_url
            if adapter._api_key:
                kw["api_key"] = adapter._api_key
            kw["timeout"] = _LLM_TIMEOUT_LONG
            raw_client = openai.AsyncOpenAI(**kw)
            return instructor.from_openai(raw_client)

        return adapter._get_or_create_client(cache_key, _make)

    # ------------------------------------------------------------------
    # Message builders (format-aware)
    # ------------------------------------------------------------------

    def _build_assistant_message(self, raw_resp: Any) -> dict[str, Any]:
        """Convert a raw API response to the assistant message dict."""
        if self._api_format == "openai":
            return self._build_openai_assistant_message(raw_resp)
        return AgentMessage.from_raw_api_response(raw_resp).to_api_dict()

    def _build_tool_results_message(
        self, results: list[ToolResult]
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Build the message(s) that return tool results to the model."""
        if self._api_format == "openai":
            return self._build_openai_tool_results(results)
        return AgentMessage.tool_results(results).to_api_dict()

    # ------------------------------------------------------------------
    # OpenAI format helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_tools_to_openai(
        anthropic_tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert Anthropic tool defs to OpenAI function-calling format.

        Anthropic: {"name", "description", "input_schema"}
        OpenAI:    {"type": "function", "function": {"name", "description", "parameters"}}
        """
        openai_tools = []
        for tool in anthropic_tools:
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {}),
                    },
                }
            )
        return openai_tools

    @staticmethod
    def _build_openai_assistant_message(raw_resp: dict[str, Any]) -> dict[str, Any]:
        """Build assistant message dict from OpenAI API response."""
        choice = raw_resp.get("choices", [{}])[0]
        msg = choice.get("message", {})

        result: dict[str, Any] = {
            "role": "assistant",
            "content": msg.get("content") or "",
        }

        tool_calls = msg.get("tool_calls")
        if tool_calls:
            result["tool_calls"] = tool_calls

        return result

    @staticmethod
    def _build_openai_tool_results(
        results: list[ToolResult],
    ) -> list[dict[str, Any]]:
        """Build OpenAI tool result messages (one per tool call)."""
        return [
            {
                "role": "tool",
                "tool_call_id": r.tool_use_id,
                "content": r.content,
            }
            for r in results
        ]
