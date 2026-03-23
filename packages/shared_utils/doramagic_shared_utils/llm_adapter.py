"""模型无关 LLM 调用适配器 — 统一不同 provider 的调用接口。

管线代码中不出现 anthropic.Client() 或 google.GenerativeAI()。
所有 LLM 调用通过此适配器。

用法:
    adapter = LLMAdapter()
    response = await adapter.generate("claude-opus-4-6", messages=[...])
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence


@dataclass
class LLMMessage:
    """统一消息格式。"""

    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list[dict]] = None


@dataclass
class LLMToolDefinition:
    """统一工具定义格式。"""

    name: str
    description: str
    parameters: dict  # JSON Schema


@dataclass
class LLMResponse:
    """统一响应格式。"""

    content: str
    model_id: str
    finish_reason: str = "stop"  # stop, tool_use, length, error
    tool_calls: list[dict] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def is_refusal(self) -> bool:
        """Detect if the model refused to process the input.

        CRITICAL GAP fix: LLM refusal was previously unhandled, causing
        silent hangs or empty output. Common refusal patterns across providers.
        """
        if not self.content:
            return False
        lower = self.content.lower().strip()
        refusal_patterns = [
            "i cannot",
            "i can't",
            "i'm not able to",
            "i am not able to",
            "i apologize, but i",
            "i'm sorry, but i cannot",
            "as an ai",
            "i must decline",
            "i'm unable to",
            "this request violates",
            "i don't think i should",
        ]
        return any(lower.startswith(p) for p in refusal_patterns)


def _provider_from_model_id(model_id: str) -> str:
    """从 model_id 推断 provider。也可通过 RoutingResult.provider 显式指定。"""
    prefixes = {
        "claude": "anthropic",
        "gpt": "openai",
        "o1": "openai",
        "o3": "openai",
        "o4": "openai",
        "gemini": "google",
        "glm": "zhipu",
        "minimax": "minimax",
    }
    model_lower = model_id.lower()
    for prefix, provider in prefixes.items():
        if model_lower.startswith(prefix):
            return provider
    return "unknown"


class LLMAdapter:
    """
    统一 LLM 调用接口。

    每个 provider 的具体实现延迟加载（首次调用时 import）。
    这样不依赖用户安装所有 SDK — 只需安装自己用的 provider 的 SDK。
    """

    def __init__(self, provider_override: Optional[str] = None, config: Any = None):
        if config is not None and hasattr(config, 'provider'):
            self._provider_override = config.provider
        else:
            self._provider_override = provider_override
        self._clients: dict[str, Any] = {}
        self._default_model: str = ""  # set by router or config

    def chat(
        self,
        messages: Sequence[LLMMessage],
        system: Optional[str] = None,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """同步调用接口 — S1-Sonnet 风格。内部 async 桥接。"""
        import asyncio
        model_id = self._default_model or "default"
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run,
                    self.generate(model_id, messages, system=system, temperature=temperature, max_tokens=max_tokens)
                ).result()
        return asyncio.run(
            self.generate(model_id, messages, system=system, temperature=temperature, max_tokens=max_tokens)
        )

    async def generate(
        self,
        model_id: str,
        messages: Sequence[LLMMessage],
        *,
        provider: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        system: Optional[str] = None,
    ) -> LLMResponse:
        """统一文本生成接口。"""
        resolved_provider = provider or self._provider_override or _provider_from_model_id(model_id)
        return await self._dispatch(
            resolved_provider, model_id, messages,
            temperature=temperature, max_tokens=max_tokens, system=system,
        )

    async def generate_with_tools(
        self,
        model_id: str,
        messages: Sequence[LLMMessage],
        tools: Sequence[LLMToolDefinition],
        *,
        provider: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        system: Optional[str] = None,
    ) -> LLMResponse:
        """统一工具调用接口。对不支持 tool_use 的模型，回退到 prompt-based 工具选择。"""
        resolved_provider = provider or self._provider_override or _provider_from_model_id(model_id)
        return await self._dispatch_with_tools(
            resolved_provider, model_id, messages, tools,
            temperature=temperature, max_tokens=max_tokens, system=system,
        )

    async def _dispatch(
        self, provider: str, model_id: str, messages: Sequence[LLMMessage], **kwargs
    ) -> LLMResponse:
        """分发到具体 provider 实现。"""
        if provider == "anthropic":
            return await self._call_anthropic(model_id, messages, **kwargs)
        if provider == "openai":
            return await self._call_openai(model_id, messages, **kwargs)
        if provider == "google":
            return await self._call_google(model_id, messages, **kwargs)
        if provider == "mock":
            return self._call_mock(model_id, messages, **kwargs)
        raise NotImplementedError(
            f"Provider '{provider}' not implemented. "
            f"Supported: anthropic, openai, google, mock. "
            f"PRs welcome for: zhipu, minimax."
        )

    async def _dispatch_with_tools(
        self, provider: str, model_id: str, messages: Sequence[LLMMessage],
        tools: Sequence[LLMToolDefinition], **kwargs
    ) -> LLMResponse:
        """分发工具调用到具体 provider。"""
        if provider == "anthropic":
            return await self._call_anthropic_tools(model_id, messages, tools, **kwargs)
        if provider == "openai":
            return await self._call_openai_tools(model_id, messages, tools, **kwargs)
        if provider == "google":
            return await self._call_google_tools(model_id, messages, tools, **kwargs)
        if provider == "mock":
            return self._call_mock(model_id, messages, **kwargs)
        # 不支持工具的 provider → 回退到 prompt-based
        return await self._fallback_prompt_tools(provider, model_id, messages, tools, **kwargs)

    # --- Anthropic ---

    async def _call_anthropic(self, model_id: str, messages: Sequence[LLMMessage], **kwargs) -> LLMResponse:
        import anthropic
        client = self._get_or_create_client("anthropic", lambda: anthropic.AsyncAnthropic())
        api_messages = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        system_text = kwargs.get("system") or next((m.content for m in messages if m.role == "system"), None)
        resp = await client.messages.create(
            model=model_id,
            messages=api_messages,
            max_tokens=kwargs.get("max_tokens", 4096),
            temperature=kwargs.get("temperature", 0.0),
            system=system_text or "",
        )
        return LLMResponse(
            content=resp.content[0].text if resp.content else "",
            model_id=model_id,
            finish_reason=resp.stop_reason or "stop",
            prompt_tokens=resp.usage.input_tokens,
            completion_tokens=resp.usage.output_tokens,
        )

    async def _call_anthropic_tools(
        self, model_id: str, messages: Sequence[LLMMessage],
        tools: Sequence[LLMToolDefinition], **kwargs
    ) -> LLMResponse:
        import anthropic
        client = self._get_or_create_client("anthropic", lambda: anthropic.AsyncAnthropic())
        api_messages = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        system_text = kwargs.get("system") or next((m.content for m in messages if m.role == "system"), None)
        api_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in tools
        ]
        resp = await client.messages.create(
            model=model_id,
            messages=api_messages,
            tools=api_tools,
            max_tokens=kwargs.get("max_tokens", 4096),
            temperature=kwargs.get("temperature", 0.0),
            system=system_text or "",
        )
        tool_calls = []
        text_parts = []
        for block in resp.content:
            if block.type == "tool_use":
                tool_calls.append({"id": block.id, "name": block.name, "arguments": block.input})
            elif block.type == "text":
                text_parts.append(block.text)
        return LLMResponse(
            content="\n".join(text_parts),
            model_id=model_id,
            finish_reason="tool_use" if tool_calls else (resp.stop_reason or "stop"),
            tool_calls=tool_calls,
            prompt_tokens=resp.usage.input_tokens,
            completion_tokens=resp.usage.output_tokens,
        )

    # --- OpenAI ---

    async def _call_openai(self, model_id: str, messages: Sequence[LLMMessage], **kwargs) -> LLMResponse:
        import openai
        client = self._get_or_create_client("openai", lambda: openai.AsyncOpenAI())
        api_messages = [{"role": m.role, "content": m.content} for m in messages]
        resp = await client.chat.completions.create(
            model=model_id,
            messages=api_messages,
            max_tokens=kwargs.get("max_tokens", 4096),
            temperature=kwargs.get("temperature", 0.0),
        )
        choice = resp.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model_id=model_id,
            finish_reason=choice.finish_reason or "stop",
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
        )

    async def _call_openai_tools(
        self, model_id: str, messages: Sequence[LLMMessage],
        tools: Sequence[LLMToolDefinition], **kwargs
    ) -> LLMResponse:
        import openai
        client = self._get_or_create_client("openai", lambda: openai.AsyncOpenAI())
        api_messages = [{"role": m.role, "content": m.content} for m in messages]
        api_tools = [
            {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
            for t in tools
        ]
        resp = await client.chat.completions.create(
            model=model_id,
            messages=api_messages,
            tools=api_tools,
            max_tokens=kwargs.get("max_tokens", 4096),
            temperature=kwargs.get("temperature", 0.0),
        )
        choice = resp.choices[0]
        tool_calls = []
        if choice.message.tool_calls:
            import json as _json
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": _json.loads(tc.function.arguments),
                })
        return LLMResponse(
            content=choice.message.content or "",
            model_id=model_id,
            finish_reason="tool_use" if tool_calls else (choice.finish_reason or "stop"),
            tool_calls=tool_calls,
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
        )

    # --- Google ---

    async def _call_google(self, model_id: str, messages: Sequence[LLMMessage], **kwargs) -> LLMResponse:
        from google import genai
        client = self._get_or_create_client(
            "google",
            lambda: genai.Client(api_key=os.environ.get("GOOGLE_API_KEY", "")),
        )
        # Gemini uses a flat prompt or structured contents
        prompt_parts = []
        for m in messages:
            prompt_parts.append(m.content)
        combined = "\n\n".join(prompt_parts)
        resp = client.models.generate_content(
            model=model_id,
            contents=combined,
        )
        return LLMResponse(
            content=resp.text or "",
            model_id=model_id,
            prompt_tokens=getattr(resp, "prompt_token_count", 0) or 0,
            completion_tokens=getattr(resp, "candidates_token_count", 0) or 0,
        )

    async def _call_google_tools(
        self, model_id: str, messages: Sequence[LLMMessage],
        tools: Sequence[LLMToolDefinition], **kwargs
    ) -> LLMResponse:
        # Gemini tool calling — simplified; full impl would use google.genai tool objects
        # 回退到 prompt-based
        return await self._fallback_prompt_tools("google", model_id, messages, tools, **kwargs)

    # --- Mock (for testing) ---

    def _call_mock(self, model_id: str, messages: Sequence[LLMMessage], **kwargs) -> LLMResponse:
        return LLMResponse(
            content="[MOCK] This is a mock response for testing.",
            model_id=model_id,
            finish_reason="stop",
            prompt_tokens=100,
            completion_tokens=20,
        )

    # --- Fallback: prompt-based tool calling ---

    async def _fallback_prompt_tools(
        self, provider: str, model_id: str, messages: Sequence[LLMMessage],
        tools: Sequence[LLMToolDefinition], **kwargs
    ) -> LLMResponse:
        """对不支持原生工具调用的模型，将工具定义注入 system prompt。"""
        import json as _json
        tool_descriptions = []
        for t in tools:
            tool_descriptions.append(
                f"Tool: {t.name}\nDescription: {t.description}\n"
                f"Parameters: {_json.dumps(t.parameters, indent=2)}"
            )
        tool_prompt = (
            "You have access to the following tools. "
            "To use a tool, respond with a JSON object: "
            '{"tool": "tool_name", "arguments": {...}}\n\n'
            + "\n---\n".join(tool_descriptions)
        )
        augmented = [LLMMessage(role="system", content=tool_prompt)] + list(messages)
        return await self._dispatch(provider, model_id, augmented, **kwargs)

    # --- Client management ---

    def _get_or_create_client(self, key: str, factory):
        if key not in self._clients:
            self._clients[key] = factory()
        return self._clients[key]


# --- Config helper ---

@dataclass
class LLMAdapterConfig:
    """Simple config for adapter construction."""
    provider: str = "mock"
    model: str = ""
    api_key_env: str = ""


# --- Mock adapter for testing ---

class MockLLMAdapter(LLMAdapter):
    """Deterministic adapter for unit tests. No real LLM calls.

    Usage:
        adapter = MockLLMAdapter(responses=['{"tool": "read_file", ...}', ...])
        adapter = MockLLMAdapter(response_fn=lambda msgs, sys: '...')
        adapter = MockLLMAdapter()  # uses default_response
    """

    def __init__(
        self,
        responses: Optional[list] = None,
        response_fn: Any = None,
        default_response: str = '{"tool": "append_finding", "arguments": {"status": "pending", "statement": "mock"}}',
    ) -> None:
        super().__init__(provider_override="mock")
        self._responses = list(responses or [])
        self._response_fn = response_fn
        self._default = default_response
        self._call_index = 0
        self._default_model = "mock-model"

    def chat(
        self,
        messages: Sequence[LLMMessage],
        system: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        if self._response_fn is not None:
            content = self._response_fn(messages, system)
        elif self._call_index < len(self._responses):
            content = self._responses[self._call_index]
            self._call_index += 1
        else:
            content = self._default

        total_chars = sum(len(m.content) for m in messages) + len(system or "")
        prompt_tokens = max(10, total_chars // 4)
        completion_tokens = max(5, len(content) // 4)

        return LLMResponse(
            content=content,
            model_id="mock-model",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    async def generate(self, model_id, messages, **kwargs):
        return self.chat(messages, system=kwargs.get("system"))

    def _call_mock(self, model_id, messages, **kwargs):
        return self.chat(messages, system=kwargs.get("system"))
