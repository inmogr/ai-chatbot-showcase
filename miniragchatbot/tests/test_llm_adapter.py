"""OpenAI-compatible adapter driven by synthetic chunks — no network (TEST-PLAN §5.8, §5.9)."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import openai
import pytest
from conftest import FakeEmployeeTool, FakeQueryEmbedder, FakeVectorReader
from openai.types.chat import ChatCompletionChunk

from app.adapters.llm.openai_adapter import OpenAICompatibleLLMAdapter, make_llm_client
from app.config import ServerConfig
from app.domain.events import StreamTextEvent, TurnDoneEvent
from app.domain.exceptions import (
    LLMBusyError,
    LLMConfigurationError,
    LLMCutShortError,
    LLMTimeoutError,
    LLMUnavailableError,
    ToolExecutionError,
    TurnError,
)
from app.domain.models import LLMStreamEvent, TextDelta, ToolCallRequest, UserClaims
from app.domain.orchestrator import TurnOrchestrator

REQUEST = httpx.Request("POST", "https://llm.test/v1/chat/completions")
USER = UserClaims(sub="emp-001", exp=1, department="hr", level=1)


def chunk(
    content: str | None = None,
    *,
    tool_calls: list[dict[str, Any]] | None = None,
    finish: str | None = None,
    empty: bool = False,
) -> ChatCompletionChunk:
    base: dict[str, Any] = {
        "id": "c",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "m",
    }
    if empty:
        return ChatCompletionChunk.model_validate({**base, "choices": []})
    delta: dict[str, Any] = {}
    if content is not None:
        delta["content"] = content
    if tool_calls is not None:
        delta["tool_calls"] = tool_calls
    choice = {"index": 0, "delta": delta, "finish_reason": finish}
    return ChatCompletionChunk.model_validate({**base, "choices": [choice]})


def tool_delta(
    arguments: str, *, call_id: str | None = None, name: str | None = None
) -> dict[str, Any]:
    function: dict[str, Any] = {"arguments": arguments}
    if name:
        function["name"] = name
    delta: dict[str, Any] = {"index": 0, "function": function}
    if call_id:
        delta.update(id=call_id, type="function")
    return delta


class FakeStream:
    """Stands in for openai.AsyncStream: async iteration, `async with`, close()."""

    def __init__(self, items: list[Any], delays: list[float] | None = None) -> None:
        self._items = list(items)
        self._delays = list(delays or [])
        self.log: list[str] = []
        self.closed = False

    def __aiter__(self) -> "FakeStream":
        return self

    async def __anext__(self) -> ChatCompletionChunk:
        if self._delays:
            await asyncio.sleep(self._delays.pop(0))
        if not self._items:
            raise StopAsyncIteration
        item = self._items.pop(0)
        if isinstance(item, BaseException):
            raise item
        self.log.append(f"pulled {item.choices[0].delta.content if item.choices else None}")
        return item

    async def __aenter__(self) -> "FakeStream":
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.closed = True


class FakeClient:
    """`client.chat.completions.create(**kwargs)` returning a scripted outcome."""

    def __init__(self, outcome: Any, create_delay: float = 0.0) -> None:
        self.outcome = outcome
        self.create_delay = create_delay
        self.calls: list[dict[str, Any]] = []
        self.chat = self
        self.completions = self

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.create_delay:
            await asyncio.sleep(self.create_delay)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def make_adapter(
    outcome: Any, *, create_delay: float = 0.0, timeout: float = 1.0, extra: Any = None
) -> tuple[OpenAICompatibleLLMAdapter, FakeClient]:
    client = FakeClient(outcome, create_delay)
    adapter = OpenAICompatibleLLMAdapter(
        client,  # type: ignore[arg-type]
        "test-model",
        1500,
        extra_body=extra,
        first_token_timeout=timeout,
    )
    return adapter, client


async def collect(adapter: OpenAICompatibleLLMAdapter, **kwargs: Any) -> list[LLMStreamEvent]:
    return [
        event async for event in adapter.stream_chat([{"role": "user", "content": "hi"}], **kwargs)
    ]


def status_error(cls: Any, code: int) -> Any:
    return cls("upstream error", response=httpx.Response(code, request=REQUEST), body=None)


async def test_stream_chat_yields_text_deltas_progressively() -> None:
    stream = FakeStream([chunk("Hel"), chunk("lo"), chunk(None, finish="stop")])
    adapter, _ = make_adapter(stream)
    async for event in adapter.stream_chat([{"role": "user", "content": "hi"}]):
        assert isinstance(event, TextDelta)
        stream.log.append(f"got {event.text}")
    # Each delta reaches the consumer before the next chunk is even read (no buffering, R-03).
    assert stream.log[:4] == ["pulled Hel", "got Hel", "pulled lo", "got lo"]
    assert stream.closed  # `async with stream` closed the upstream response (R-06)


async def test_stream_chat_accumulates_tool_call_deltas() -> None:
    stream = FakeStream(
        [
            chunk(
                tool_calls=[tool_delta('{"user_', call_id="call_1", name="get_employee_context")]
            ),
            chunk(tool_calls=[tool_delta('id": "emp-001"}')], finish="tool_calls"),
        ]
    )
    adapter, client = make_adapter(stream)
    events = await collect(adapter, tools=[{"type": "function"}], tool_choice="auto")
    assert events == [
        ToolCallRequest(
            id="call_1",
            name="get_employee_context",
            raw_arguments='{"user_id": "emp-001"}',
            parsed_arguments={"user_id": "emp-001"},
        )
    ]
    assert client.calls[0]["tool_choice"] == "auto"


async def test_stream_chat_first_token_timeout_triggers_error() -> None:
    hanging_create, _ = make_adapter(FakeStream([chunk("x")]), create_delay=0.5, timeout=0.05)
    with pytest.raises(LLMTimeoutError):
        await collect(hanging_create)
    late_first_chunk, _ = make_adapter(FakeStream([chunk("x")], delays=[0.5]), timeout=0.05)
    with pytest.raises(LLMTimeoutError):
        await collect(late_first_chunk)
    # A first chunk of any kind (here: an empty delta) stops the timer; later chunks may be slow.
    slow_after_first, _ = make_adapter(
        FakeStream([chunk(None), chunk("late text", finish="stop")], delays=[0.0, 0.1]),
        timeout=0.05,
    )
    assert await collect(slow_after_first) == [TextDelta("late text")]


async def test_stream_chat_maps_429_to_busy_catalog_message() -> None:
    adapter, _ = make_adapter(status_error(openai.RateLimitError, 429))
    with pytest.raises(LLMBusyError) as raised:
        await collect(adapter)
    assert raised.value.message == "System is busy due to high demand. Please try again shortly."


SDK_ERROR_CASES: dict[str, tuple[Any, type[Exception]]] = {
    "bad_request_400": (status_error(openai.BadRequestError, 400), LLMConfigurationError),
    "auth_401": (status_error(openai.AuthenticationError, 401), LLMConfigurationError),
    # Seen live (2026-10-04, Gemini): 402 "prepayment credits are depleted" — retrying cannot
    # help, so it is a configuration error like 401/403/404, not "temporarily unavailable".
    "payment_required_402": (status_error(openai.APIStatusError, 402), LLMConfigurationError),
    "permission_denied_403": (
        status_error(openai.PermissionDeniedError, 403),
        LLMConfigurationError,
    ),
    "not_found_404": (status_error(openai.NotFoundError, 404), LLMConfigurationError),
    "server_500": (status_error(openai.InternalServerError, 500), LLMUnavailableError),
    "connection": (openai.APIConnectionError(request=REQUEST), LLMUnavailableError),
    "sdk_timeout": (openai.APITimeoutError(request=REQUEST), LLMTimeoutError),
    "mid_stream_drop": (
        FakeStream([chunk("partial"), openai.APIConnectionError(request=REQUEST)]),
        LLMUnavailableError,
    ),
    "empty_answer": (FakeStream([]), LLMUnavailableError),
    "content_filter": (
        FakeStream([chunk("x"), chunk(None, finish="content_filter")]),
        LLMUnavailableError,
    ),
    "length": (FakeStream([chunk("partial"), chunk(None, finish="length")]), LLMCutShortError),
    "bad_tool_args": (
        FakeStream(
            [
                chunk(
                    tool_calls=[tool_delta("{not json", call_id="c1", name="t")],
                    finish="tool_calls",
                )
            ]
        ),
        ToolExecutionError,
    ),
}


@pytest.mark.parametrize("case", list(SDK_ERROR_CASES))
async def test_stream_chat_maps_sdk_errors_to_catalog(case: str) -> None:
    outcome, expected = SDK_ERROR_CASES[case]
    adapter, _ = make_adapter(outcome)
    with pytest.raises(expected):
        await collect(adapter)


async def test_stream_chat_skips_empty_choice_chunks() -> None:
    stream = FakeStream(
        [chunk(empty=True), chunk("a"), chunk(empty=True), chunk("b", finish="stop")]
    )
    adapter, _ = make_adapter(stream)
    assert await collect(adapter) == [TextDelta("a"), TextDelta("b")]


async def test_groq_extra_params_sent_only_for_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "s" * 40)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-placeholder")
    monkeypatch.setenv("GROQ_EXTRA_PARAMS", '{"reasoning_effort": "low"}')
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert ServerConfig(_env_file=None).llm_endpoint().extra_body == {"reasoning_effort": "low"}
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-placeholder")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    assert ServerConfig(_env_file=None).llm_endpoint().extra_body is None

    with_extra, client = make_adapter(FakeStream([chunk("ok", finish="stop")]), extra={"k": "v"})
    await collect(with_extra)
    assert client.calls[0]["extra_body"] == {"k": "v"}
    plain, client = make_adapter(FakeStream([chunk("ok", finish="stop")]))
    await collect(plain)
    assert "extra_body" not in client.calls[0]
    assert (client.calls[0]["max_tokens"], client.calls[0]["stream"]) == (1500, True)


class RecordingLLM:
    """Fake LLM port that records its input and whether its stream was closed."""

    def __init__(self) -> None:
        self.closed = False
        self.messages: list[dict[str, Any]] = []

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncGenerator[LLMStreamEvent, None]:
        self.messages = messages
        try:
            for word in ("one ", "two ", "three "):
                yield TextDelta(word)
        finally:
            self.closed = True


async def test_run_turn_streams_llm_text_then_done() -> None:
    llm = RecordingLLM()
    events = [
        event
        async for event in TurnOrchestrator(
            FakeQueryEmbedder(), FakeVectorReader(), llm, FakeEmployeeTool()
        ).run_turn("How many days?", USER)
    ]
    assert events == [
        StreamTextEvent("one "),
        StreamTextEvent("two "),
        StreamTextEvent("three "),
        TurnDoneEvent(),
    ]
    assert llm.messages[0]["role"] == "system" and "emp-001" in llm.messages[0]["content"]
    assert llm.messages[-1] == {"role": "user", "content": "Question: How many days?"}


async def test_run_turn_closes_adapter_stream_on_early_exit() -> None:
    llm = RecordingLLM()
    turn = TurnOrchestrator(
        FakeQueryEmbedder(), FakeVectorReader(), llm, FakeEmployeeTool()
    ).run_turn("question?", USER)
    first = await anext(turn)
    await turn.aclose()  # the consumer stops early, e.g. after a failed send
    assert first == StreamTextEvent("one ")
    assert llm.closed  # aclosing closed the adapter stream deterministically (D-62)


EXTRA_FAILURES: dict[str, tuple[Any, type[Exception]]] = {
    "ended_without_finish": (FakeStream([chunk("partial")]), LLMUnavailableError),  # R-04
    "sse_decode_error": (  # R-05: SDK SSE decoding raises ValueError subclasses
        FakeStream([chunk("x"), json.JSONDecodeError("bad event", "doc", 0)]),
        LLMUnavailableError,
    ),
}


@pytest.mark.parametrize("case", list(EXTRA_FAILURES))
async def test_stream_chat_maps_incomplete_streams_to_unavailable(case: str) -> None:
    outcome, expected = EXTRA_FAILURES[case]
    adapter, _ = make_adapter(outcome)
    with pytest.raises(expected):
        await collect(adapter)


async def test_stream_chat_closes_upstream_on_early_exit() -> None:
    stream = FakeStream([chunk("one"), chunk("two"), chunk(None, finish="stop")])
    adapter, _ = make_adapter(stream)
    events = adapter.stream_chat([{"role": "user", "content": "hi"}])
    assert await anext(events) == TextDelta("one")
    await events.aclose()  # the turn is abandoned, e.g. the client disconnected
    assert stream.closed  # aclosing + `async with` closed the upstream stream at once (R-06)


def test_llm_client_never_retries() -> None:
    # R-03: the SDK default (max_retries=2) would silently re-send 429/5xx requests (D-37).
    assert make_llm_client("https://llm.test/v1", "key").max_retries == 0


async def test_llm_failures_logged_with_status_not_text(caplog: pytest.LogCaptureFixture) -> None:
    adapter, _ = make_adapter(status_error(openai.RateLimitError, 429))
    with caplog.at_level(logging.ERROR), pytest.raises(LLMBusyError):
        await collect(adapter)
    logged = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert logged and "status=429" in logged[0].getMessage()  # R-07
    assert "upstream error" not in logged[0].getMessage()  # never str(exc)


STREAM_END_REASONS: dict[str, tuple[Any, str]] = {
    "length": (
        FakeStream([chunk("partial"), chunk(None, finish="length")]),
        "finish_reason=length",
    ),
    "content_filter": (
        FakeStream([chunk("partial"), chunk(None, finish="content_filter")]),
        "finish_reason=content_filter",
    ),
    "ended_without_finish": (FakeStream([chunk("partial")]), "finish_reason=None"),
    "empty_answer": (FakeStream([chunk(None, finish="stop")]), "empty answer"),
    "bad_tool_args": (
        FakeStream(
            [
                chunk(
                    tool_calls=[tool_delta("{not json", call_id="c1", name="t")],
                    finish="tool_calls",
                )
            ]
        ),
        "unparseable tool arguments",
    ),
}


@pytest.mark.parametrize("case", list(STREAM_END_REASONS))
async def test_stream_end_failures_log_their_reason(
    case: str, caplog: pytest.LogCaptureFixture
) -> None:
    # R-20: these failures share catalog texts, so the server log must say which one it was.
    outcome, reason = STREAM_END_REASONS[case]
    adapter, _ = make_adapter(outcome)
    with caplog.at_level(logging.WARNING), pytest.raises(TurnError):
        await collect(adapter)
    assert reason in caplog.text
    assert "partial" not in caplog.text  # never the answer text


async def test_first_chunk_timeout_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    adapter, _ = make_adapter(FakeStream([chunk("x")], delays=[0.5]), timeout=0.05)
    with caplog.at_level(logging.WARNING), pytest.raises(LLMTimeoutError):
        await collect(adapter)
    assert "no first chunk within 0.05 s" in caplog.text


async def test_stream_chat_parses_only_the_first_tool_call() -> None:
    # R-13 / D-60: only the first call is executed, so a malformed extra call must not fail it.
    good = {
        "index": 0,
        "id": "c1",
        "type": "function",
        "function": {"name": "t", "arguments": "{}"},
    }
    bad = {"index": 1, "id": "c2", "type": "function", "function": {"name": "t", "arguments": "{x"}}
    adapter, _ = make_adapter(FakeStream([chunk(tool_calls=[good, bad], finish="tool_calls")]))
    events = await collect(adapter)
    assert [event.id for event in events if isinstance(event, ToolCallRequest)] == ["c1"]


async def test_stream_chat_sends_the_complete_request() -> None:
    # Every field matters: without `tools` the model can never call the employee tool.
    adapter, client = make_adapter(
        FakeStream([chunk("ok", finish="stop")]), extra={"reasoning_effort": "low"}
    )
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]
    tools = [{"type": "function", "function": {"name": "t", "parameters": {"type": "object"}}}]
    assert [e async for e in adapter.stream_chat(messages, tools=tools, tool_choice="auto")] == [
        TextDelta("ok")
    ]
    assert client.calls == [
        {
            "model": "test-model",
            "messages": messages,
            "max_tokens": 1500,
            "stream": True,
            "tools": tools,
            "tool_choice": "auto",
            "extra_body": {"reasoning_effort": "low"},
        }
    ]
