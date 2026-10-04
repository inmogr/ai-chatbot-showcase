"""Turn orchestration: one stateless turn per message (ARCHITECTURE §7)."""

import contextlib
import json
import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.domain.constants import TOP_K
from app.domain.events import StreamTextEvent, TurnDoneEvent, TurnEvent
from app.domain.exceptions import (
    EmbeddingError,
    LLMUnavailableError,
    ToolExecutionError,
    VectorSearchError,
)
from app.domain.models import (
    EmployeeContextArgs,
    LLMStreamEvent,
    PolicyChunk,
    RbacScope,
    TextDelta,
    ToolCallRequest,
    UserClaims,
)
from app.domain.ports import EmployeeToolPort, LLMPort, QueryEmbedderPort, VectorReaderPort
from app.domain.prompt import (
    EMPLOYEE_TOOL_NAME,
    IDOR_DENIAL_TEXT,
    TOOLS,
    build_messages,
    build_pass2_messages,
)

logger = logging.getLogger(__name__)


@dataclass
class _PassOne:
    """Pass-1 text (forwarded live) and the first tool call; extra calls are ignored (D-60)."""

    texts: list[str] = field(default_factory=list)
    call: ToolCallRequest | None = None

    def absorb(self, event: LLMStreamEvent) -> str | None:
        if isinstance(event, TextDelta):
            self.texts.append(event.text)
            return event.text
        if self.call is None:
            self.call = event
        else:
            logger.warning("ignoring an extra tool call: only the first is executed")
        return None


class TurnOrchestrator:
    """Runs one turn and yields events; it never touches the WebSocket."""

    def __init__(
        self,
        embedder: QueryEmbedderPort,
        reader: VectorReaderPort,
        llm: LLMPort,
        employee_tool: EmployeeToolPort,
        top_k: int = TOP_K,
    ) -> None:
        self._embedder = embedder
        self._reader = reader
        self._llm = llm
        self._employee_tool = employee_tool
        self._top_k = top_k

    async def run_turn(
        self,
        question: str,
        user: UserClaims,
    ) -> AsyncGenerator[TurnEvent, None]:
        chunks = await self._retrieve(question, user)  # retrieval always precedes pass 1 (D-10)
        messages = build_messages(question, user.sub, chunks)
        pass_one = _PassOne()
        first = self._llm.stream_chat(messages, tools=TOOLS, tool_choice="auto")
        async with contextlib.aclosing(first) as stream:
            async for event in stream:
                text = pass_one.absorb(event)
                if text:
                    yield StreamTextEvent(text)  # pass-1 text streams before any tool runs
        if pass_one.call is not None:  # at most one tool round (D-32)
            tool_content = await self._run_tool(pass_one.call, user)
            follow_up = build_pass2_messages(
                messages, "".join(pass_one.texts), pass_one.call, tool_content
            )
            second = self._llm.stream_chat(follow_up, tools=TOOLS, tool_choice="none")
            answered = False
            async with contextlib.aclosing(second) as stream:
                async for event in stream:
                    if isinstance(event, TextDelta):
                        answered = True
                        yield StreamTextEvent(event.text)
                    else:
                        logger.warning("pass 2 ignored tool_choice=none: tool call dropped")
            if not answered:  # a bare `done` would hide the failure (R-18)
                raise LLMUnavailableError()
        yield TurnDoneEvent()

    async def _run_tool(self, call: ToolCallRequest, user: UserClaims) -> str:
        """Validate the call, enforce `user_id == sub` in code (IDOR, D-52), then run the tool."""
        user_id = _requested_user_id(call)
        if user_id != user.sub:
            logger.warning("tool call for another user denied for sub=%s", user.sub)
            return IDOR_DENIAL_TEXT  # pass 2 explains the refusal; no lookup runs
        started = time.perf_counter()
        result = await self._employee_tool.get_employee_context(user_id)
        logger.info(
            "tool %s completed in %.2f s", EMPLOYEE_TOOL_NAME, time.perf_counter() - started
        )
        return json.dumps(result)

    async def _retrieve(self, question: str, user: UserClaims) -> list[PolicyChunk]:
        """The current question only (E04); the scope comes from verified claims only."""
        try:
            vector = await self._embedder.embed_query(question)
        except Exception as exc:
            logger.error("embedding failed: %s", type(exc).__name__)
            raise EmbeddingError() from exc
        try:
            scope = RbacScope(department=user.department, level=user.level)
            return await self._reader.query_chunks(vector, scope, self._top_k)
        except Exception as exc:
            logger.error("vector search failed: %s", type(exc).__name__)
            raise VectorSearchError() from exc


def _requested_user_id(call: ToolCallRequest) -> str:
    """The validated `user_id` of an employee-tool call; any other request is a lookup failure."""
    if call.name == EMPLOYEE_TOOL_NAME:
        with contextlib.suppress(ValidationError):
            return EmployeeContextArgs.model_validate(call.parsed_arguments).user_id
    logger.warning("invalid tool request: unknown tool or missing string user_id")
    raise ToolExecutionError()
