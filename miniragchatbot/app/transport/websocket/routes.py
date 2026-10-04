"""The /ws/chat endpoint: auth gate, sequential message loop, turn consumer (ARCHITECTURE §7)."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Annotated, Protocol, assert_never, cast

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.domain.constants import AUTH_TIMEOUT_SECONDS, TURN_TIMEOUT_SECONDS
from app.domain.events import StreamTextEvent, TurnDoneEvent, TurnEvent
from app.domain.exceptions import LLMTimeoutError, TurnError
from app.domain.models import UserClaims
from app.transport.websocket.auth import authenticate
from app.transport.websocket.frames import (
    AuthSuccessFrame,
    DoneFrame,
    ErrorFrame,
    FrameError,
    ServerFrame,
    StreamFrame,
    parse_message_frame,
    receive_text_frame,
    send_frame,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class TurnRunner(Protocol):
    """What the transport needs from the orchestrator; fakes satisfy it structurally in tests."""

    def run_turn(self, question: str, user: UserClaims) -> AsyncGenerator[TurnEvent, None]: ...


@dataclass(frozen=True)
class ChatRuntime:
    """Collaborators of the endpoint, stored on `app.state.chat` by the composition root."""

    runner: TurnRunner
    jwt_secret: str = field(repr=False)  # never printed (R-08)
    auth_timeout: float = AUTH_TIMEOUT_SECONDS
    turn_timeout: float = TURN_TIMEOUT_SECONDS


async def get_chat_runtime(websocket: WebSocket) -> ChatRuntime:
    return cast(ChatRuntime, websocket.app.state.chat)  # async: no threadpool hop per connect


@router.websocket("/ws/chat")
async def chat_endpoint(
    websocket: WebSocket, runtime: Annotated[ChatRuntime, Depends(get_chat_runtime)]
) -> None:
    await websocket.accept()
    try:
        user = await authenticate(websocket, runtime.jwt_secret, runtime.auth_timeout)
        if user is None:
            return
        logger.info("authenticated sub=%s", user.sub)
        await send_frame(
            websocket,
            AuthSuccessFrame(user_id=user.sub, department=user.department, level=user.level),
        )
        await _message_loop(websocket, runtime, user)
    except WebSocketDisconnect as disconnect:
        logger.info("connection closed code=%s", disconnect.code)


async def _message_loop(websocket: WebSocket, runtime: ChatRuntime, user: UserClaims) -> None:
    """One turn at a time; frames sent meanwhile wait in uvicorn's queue (D-08)."""
    while True:
        raw = await receive_text_frame(websocket)  # None for a binary frame (R-02)
        try:
            frame = parse_message_frame(raw)
        except FrameError as invalid:
            logger.warning("invalid frame from sub=%s", user.sub)
            await _send_error(websocket, invalid.message)
            continue
        await consume_turn(websocket, runtime.runner, frame.text, user, runtime.turn_timeout)


async def consume_turn(
    websocket: WebSocket,
    runner: TurnRunner,
    text: str,
    user: UserClaims,
    turn_timeout: float = TURN_TIMEOUT_SECONDS,
) -> None:
    """Run one turn. Any failure ends it with one `error` frame and no `done`; the socket stays
    open (FR-29, ARCHITECTURE §7.2), unless the client is already gone."""
    try:
        await _forward_turn(websocket, runner, text, user, turn_timeout)
    except TurnError as failure:
        logger.warning(
            "turn failed for sub=%s: %s cause=%s",
            user.sub,
            type(failure).__name__,
            type(failure.__cause__).__name__ if failure.__cause__ else "-",  # class only (§10)
        )
        await _send_error(websocket, failure.message)
    except WebSocketDisconnect:
        raise  # the client is gone: nothing to send; the endpoint returns (§13)
    except Exception:
        logger.exception("unexpected turn failure for sub=%s", user.sub)  # last resort (§10)
        await _send_error(websocket, TurnError.default_message)


async def _forward_turn(
    websocket: WebSocket, runner: TurnRunner, text: str, user: UserClaims, turn_timeout: float
) -> None:
    """Send each event as a frame the moment it arrives (R-03), under the turn deadline.

    The deadline wraps `aclosing`, so a timed-out or abandoned turn is closed — and through it
    the adapter stream — first; no timeout spans a `yield` (§7.3, E15). Only this deadline is
    the catalog's turn timeout: any other TimeoutError reaches the last resort (R-19).
    """
    deadline = asyncio.timeout(turn_timeout)
    try:
        async with deadline, contextlib.aclosing(runner.run_turn(text, user)) as turn:
            async for event in turn:
                await send_frame(websocket, _frame(event))
    except TimeoutError as expired:
        if not deadline.expired():
            raise
        logger.warning("turn deadline of %g s expired for sub=%s", turn_timeout, user.sub)
        raise LLMTimeoutError() from expired


def _frame(event: TurnEvent) -> ServerFrame:
    match event:
        case StreamTextEvent(text=text):
            return StreamFrame(text=text)
        case TurnDoneEvent():
            return DoneFrame()
        case _:
            assert_never(event)  # a new event type must be mapped, not reported as done (R-22)


async def _send_error(websocket: WebSocket, message: str) -> None:
    await send_frame(websocket, ErrorFrame(message=message))
