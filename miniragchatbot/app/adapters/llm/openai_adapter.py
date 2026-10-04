"""OpenAI-compatible streaming adapter behind LLMPort (D-29, D-31, D-37, D-56, D-59, D-67).

One adapter serves every provider in the table (Groq by default): it yields each text delta as it
arrives, assembles tool calls from their streamed fragments, and maps provider failures to catalog
errors. Nothing is retried.
"""

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass, field
from typing import Any, cast

import openai
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk

from app.domain.constants import FIRST_TOKEN_TIMEOUT_SECONDS
from app.domain.exceptions import (
    LLMBusyError,
    LLMConfigurationError,
    LLMCutShortError,
    LLMTimeoutError,
    LLMUnavailableError,
    ToolExecutionError,
    TurnError,
)
from app.domain.models import LLMStreamEvent, TextDelta, ToolCallRequest

# Account or request problems that a retry cannot fix (catalog row 10). 402 has no SDK class.
_CONFIGURATION_ERRORS = (
    openai.BadRequestError,
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.NotFoundError,
)
HTTP_PAYMENT_REQUIRED = 402
logger = logging.getLogger(__name__)


def make_llm_client(base_url: str, api_key: str) -> AsyncOpenAI:
    """The SDK retries 429/5xx twice by default; this design retries nothing (D-37, R-03)."""
    return AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=0)


@dataclass
class _ToolCallParts:
    id: str = ""
    name: str = ""
    arguments: list[str] = field(default_factory=list)


@dataclass
class _StreamState:
    """Accumulates one streamed completion: tool-call fragments per index, text seen, finish."""

    calls: dict[int, _ToolCallParts] = field(default_factory=dict)
    text_seen: bool = False
    finish_reason: str | None = None

    def consume(self, chunk: ChatCompletionChunk) -> str | None:
        """Fold one chunk into the state and return its text delta, if any."""
        if not chunk.choices:
            return None
        choice = chunk.choices[0]
        self.finish_reason = choice.finish_reason or self.finish_reason
        for call in choice.delta.tool_calls or []:
            parts = self.calls.setdefault(call.index, _ToolCallParts())
            parts.id = call.id or parts.id
            if call.function is not None:
                parts.name = call.function.name or parts.name
                parts.arguments.append(call.function.arguments or "")
        if choice.delta.content:
            self.text_seen = True
            return choice.delta.content
        return None


class OpenAICompatibleLLMAdapter:
    """Streams chat completions from any OpenAI-compatible endpoint (Groq, Gemini, Ollama, …)."""

    def __init__(
        self,
        client: AsyncOpenAI,
        model: str,
        max_tokens: int,
        extra_body: dict[str, Any] | None = None,
        first_token_timeout: float = FIRST_TOKEN_TIMEOUT_SECONDS,
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._extra_body = extra_body
        self._first_token_timeout = first_token_timeout

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncGenerator[LLMStreamEvent, None]:
        request = self._request(messages, tools, tool_choice)
        try:
            async with contextlib.aclosing(self._stream(request)) as events:
                async for event in events:
                    yield event
        except (openai.APIError, ValueError) as exc:  # ValueError: SDK SSE decoding (R-05)
            logger.error(
                "llm request failed: %s status=%s request_id=%s",  # never str(exc) (R-07)
                type(exc).__name__,
                getattr(exc, "status_code", None),
                getattr(exc, "request_id", None),
            )
            raise _catalog_error(exc) from exc

    def _request(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        tool_choice: str | dict[str, Any] | None,
    ) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "stream": True,
        }
        if tools is not None:
            request["tools"] = tools
        if tool_choice is not None:
            request["tool_choice"] = tool_choice
        if self._extra_body:
            request["extra_body"] = self._extra_body
        return request

    async def _stream(self, request: dict[str, Any]) -> AsyncGenerator[LLMStreamEvent, None]:
        # One deadline from request start to the first chunk of any kind (D-56); it is closed
        # before anything is yielded, so no timeout context spans a `yield` (D-62).
        deadline = asyncio.get_running_loop().time() + self._first_token_timeout
        create = cast(Any, self._client.chat.completions.create)
        try:
            async with asyncio.timeout_at(deadline):
                stream = await create(**request)
        except TimeoutError as exc:
            raise self._first_chunk_timeout() from exc
        async with stream:
            chunks: AsyncIterator[ChatCompletionChunk] = aiter(stream)
            try:
                async with asyncio.timeout_at(deadline):
                    chunk = await anext(chunks, None)
            except TimeoutError as exc:
                raise self._first_chunk_timeout() from exc
            state = _StreamState()
            while chunk is not None:
                text = state.consume(chunk)
                if text:
                    yield TextDelta(text)
                chunk = await anext(chunks, None)
        for call in _completed_calls(state):
            yield call

    def _first_chunk_timeout(self) -> LLMTimeoutError:
        logger.warning("llm sent no first chunk within %g s", self._first_token_timeout)
        return LLMTimeoutError()


def _catalog_error(exc: Exception) -> TurnError:
    if isinstance(exc, openai.APITimeoutError):  # a subclass of APIConnectionError: first
        return LLMTimeoutError()
    if isinstance(exc, openai.RateLimitError):
        return LLMBusyError()
    if isinstance(exc, _CONFIGURATION_ERRORS) or (
        getattr(exc, "status_code", None) == HTTP_PAYMENT_REQUIRED
    ):
        return LLMConfigurationError()
    return LLMUnavailableError()  # 5xx, connection error, mid-stream drop, bad SSE


def _completed_calls(state: _StreamState) -> list[ToolCallRequest]:
    """Check how the stream ended and return its tool calls (catalog rows 8, 12, 13). Rows
    share texts, so each failure logs its reason — never the text (R-20)."""
    if state.finish_reason in ("length", "content_filter", None):  # None: cut off (R-04)
        logger.warning("llm stream failed: finish_reason=%s", state.finish_reason)
        raise LLMCutShortError() if state.finish_reason == "length" else LLMUnavailableError()
    calls = [parts for _, parts in sorted(state.calls.items())]
    if not calls and not state.text_seen:
        logger.warning("llm returned an empty answer")
        raise LLMUnavailableError()
    if len(calls) > 1:  # only the first call is executed, so only it is parsed (D-60, R-13)
        logger.warning("ignoring %d extra tool call(s)", len(calls) - 1)
    return [_tool_call(calls[0])] if calls else []


def _tool_call(parts: _ToolCallParts) -> ToolCallRequest:
    raw = "".join(parts.arguments)
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        logger.warning("llm sent unparseable tool arguments")
        raise ToolExecutionError()
    return ToolCallRequest(id=parts.id, name=parts.name, raw_arguments=raw, parsed_arguments=parsed)
