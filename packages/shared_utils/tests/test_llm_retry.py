"""Tests for LLMAdapter retry and exponential backoff."""

from __future__ import annotations

import pytest
from doramagic_shared_utils import llm_adapter as llm_adapter_module
from doramagic_shared_utils.llm_adapter import (
    _OVERLOAD_RETRY_DELAYS_SECONDS,
    LLMAdapter,
    LLMMessage,
    LLMResponse,
)


class FakeHttpError(Exception):
    """Simple exception that carries an HTTP status code."""

    def __init__(self, status_code: int, message: str = "boom") -> None:
        super().__init__(message)
        self.status_code = status_code


def _make_adapter() -> LLMAdapter:
    adapter = LLMAdapter(provider_override="mock")
    adapter._default_model = "test-model"
    return adapter


def test_retry_on_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _make_adapter()
    sleep_calls: list[int] = []
    monkeypatch.setattr(
        llm_adapter_module.time, "sleep", lambda seconds: sleep_calls.append(seconds)
    )

    call_count = 0

    async def fake_generate(model_id, messages, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("temporary network failure")
        return LLMResponse(content="ok", model_id=model_id)

    monkeypatch.setattr(adapter, "generate", fake_generate)

    response = adapter.chat([LLMMessage(role="user", content="hello")])

    assert response.content == "ok"
    assert call_count == 3
    assert sleep_calls == [1, 2]


def test_retry_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _make_adapter()
    sleep_calls: list[int] = []
    monkeypatch.setattr(
        llm_adapter_module.time, "sleep", lambda seconds: sleep_calls.append(seconds)
    )

    call_count = 0

    async def fake_generate(model_id, messages, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise FakeHttpError(429, "rate limited")
        return LLMResponse(content="recovered", model_id=model_id)

    monkeypatch.setattr(adapter, "generate", fake_generate)

    response = adapter.chat([LLMMessage(role="user", content="hello")])

    assert response.content == "recovered"
    assert call_count == 2
    assert sleep_calls == [1]


def test_no_retry_on_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _make_adapter()
    sleep_calls: list[int] = []
    monkeypatch.setattr(
        llm_adapter_module.time, "sleep", lambda seconds: sleep_calls.append(seconds)
    )

    call_count = 0

    async def fake_generate(model_id, messages, **kwargs):
        nonlocal call_count
        call_count += 1
        raise FakeHttpError(401, "unauthorized")

    monkeypatch.setattr(adapter, "generate", fake_generate)

    with pytest.raises(FakeHttpError, match="unauthorized"):
        adapter.chat([LLMMessage(role="user", content="hello")])

    assert call_count == 1
    assert sleep_calls == []


def test_max_retries_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _make_adapter()
    sleep_calls: list[int] = []
    monkeypatch.setattr(
        llm_adapter_module.time, "sleep", lambda seconds: sleep_calls.append(seconds)
    )

    call_count = 0

    async def fake_generate(model_id, messages, **kwargs):
        nonlocal call_count
        call_count += 1
        raise ConnectionError("persistent network failure")

    monkeypatch.setattr(adapter, "generate", fake_generate)

    with pytest.raises(ConnectionError, match="persistent network failure"):
        adapter.chat([LLMMessage(role="user", content="hello")])

    assert call_count == 4
    assert sleep_calls == [1, 2, 4]


def test_retry_on_529_uses_overload_delays(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 529 should use _OVERLOAD_RETRY_DELAYS_SECONDS, not the standard delays."""
    adapter = _make_adapter()
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        llm_adapter_module.time, "sleep", lambda seconds: sleep_calls.append(seconds)
    )
    # Suppress jitter for deterministic assertions
    monkeypatch.setattr(llm_adapter_module.random, "uniform", lambda a, b: 0.0)

    call_count = 0

    async def fake_generate(model_id, messages, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise FakeHttpError(529, "server overloaded")
        return LLMResponse(content="recovered", model_id=model_id)

    monkeypatch.setattr(adapter, "generate", fake_generate)

    response = adapter.chat([LLMMessage(role="user", content="hello")])

    assert response.content == "recovered"
    assert call_count == 2
    # First overload delay (index 0) with jitter stubbed to 0
    assert sleep_calls == [_OVERLOAD_RETRY_DELAYS_SECONDS[0]]


def test_529_max_retries_exhausted_uses_overload_delays(monkeypatch: pytest.MonkeyPatch) -> None:
    """Persistent 529 should exhaust all retries using overload delay sequence."""
    adapter = _make_adapter()
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        llm_adapter_module.time, "sleep", lambda seconds: sleep_calls.append(seconds)
    )
    # Suppress jitter for deterministic assertions
    monkeypatch.setattr(llm_adapter_module.random, "uniform", lambda a, b: 0.0)

    call_count = 0

    async def fake_generate(model_id, messages, **kwargs):
        nonlocal call_count
        call_count += 1
        raise FakeHttpError(529, "server overloaded")

    monkeypatch.setattr(adapter, "generate", fake_generate)

    with pytest.raises(FakeHttpError, match="server overloaded"):
        adapter.chat([LLMMessage(role="user", content="hello")])

    assert call_count == 4
    assert sleep_calls == list(_OVERLOAD_RETRY_DELAYS_SECONDS)
