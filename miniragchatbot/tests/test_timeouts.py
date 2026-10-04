"""The consumer's turn deadline and disconnect cleanup (NFR-10, D-62, E15, ARCHITECTURE §7.3)."""

import asyncio
import inspect
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from conftest import FakeEmployeeTool, FakeQueryEmbedder, FakeVectorReader, make_token
from fastapi import WebSocketDisconnect

from app.adapters.employee_tool.mock_service import MockEmployeeService
from app.adapters.llm.openai_adapter import OpenAICompatibleLLMAdapter
from app.domain.constants import TURN_TIMEOUT_SECONDS
from app.domain.events import StreamTextEvent, TurnDoneEvent, TurnEvent
from app.domain.models import TextDelta, UserClaims
from app.domain.orchestrator import TurnOrchestrator
from app.main import create_app
from app.transport.websocket.auth import authenticate as authenticate_first_frame
from app.transport.websocket.routes import consume_turn

WS = "/ws/chat"
USER = UserClaims(sub="emp-001", exp=1, department="hr", level=1)
TIMEOUT_TEXT = "Response generation timed out. Please try again."


class StallingRunner:
    """Turn 1 streams one delta, then stalls past any test deadline; later turns answer at once."""

    def __init__(self) -> None:
        self.turns = 0
        self.closed: list[int] = []

    async def run_turn(self, question: str, user: UserClaims) -> AsyncGenerator[TurnEvent, None]:
        self.turns += 1
        turn = self.turns
        try:
            yield StreamTextEvent("partial ")
            if turn == 1:
                await asyncio.sleep(60)
            yield StreamTextEvent("answer")
            yield TurnDoneEvent()
        finally:
            self.closed.append(turn)


class SlowLLM:
    """LLMPort fake streaming delayed deltas; counts the streams it opened and closed."""

    def __init__(self, delay: float = 0.05) -> None:
        self.delay = delay
        self.opened = 0
        self.closed = 0

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncGenerator[Any, None]:
        self.opened += 1
        try:
            for word in ("one ", "two ", "three"):
                await asyncio.sleep(self.delay)
                yield TextDelta(word)
        finally:
            self.closed += 1


class VanishedClientSocket:
    """A socket whose client is gone: the n-th send raises as Starlette does over uvicorn (E11)."""

    def __init__(self, fail_on_send: int) -> None:
        self.fail_on_send = fail_on_send
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, data: dict[str, Any]) -> None:
        if len(self.sent) + 1 == self.fail_on_send:
            raise WebSocketDisconnect(code=1006)
        self.sent.append(data)


def orchestrator_over(llm: SlowLLM) -> TurnOrchestrator:
    return TurnOrchestrator(FakeQueryEmbedder(), FakeVectorReader(), llm, FakeEmployeeTool())


def authenticate(ws: Any) -> None:
    ws.send_json({"type": "auth", "token": make_token()})
    assert ws.receive_json()["type"] == "auth_success"


def test_turn_timeout_30s_terminates_turn(make_client: Any) -> None:
    runner = StallingRunner()
    assert TURN_TIMEOUT_SECONDS == 30.0
    assert make_client(runner).app.state.chat.turn_timeout == TURN_TIMEOUT_SECONDS  # the default
    with make_client(runner, turn_timeout=0.2).websocket_connect(WS) as ws:
        authenticate(ws)
        started = time.monotonic()
        ws.send_json({"type": "message", "text": "slow question"})
        assert ws.receive_json() == {"type": "stream", "text": "partial "}
        assert ws.receive_json() == {"type": "error", "message": TIMEOUT_TEXT}  # and no done
        assert time.monotonic() - started < 2.0  # the deadline ended it, not the 60 s stall
        assert runner.closed == [1]  # the abandoned turn generator was closed
        ws.send_json({"type": "message", "text": "next question"})  # the socket stays open
        assert [ws.receive_json() for _ in range(3)] == [
            {"type": "stream", "text": "partial "},
            {"type": "stream", "text": "answer"},
            {"type": "done"},
        ]


def test_disconnect_mid_stream_closes_generators_and_reconnect_works(make_client: Any) -> None:
    llm = SlowLLM()
    client = make_client(orchestrator_over(llm))
    with client.websocket_connect(WS) as ws:
        authenticate(ws)
        ws.send_json({"type": "message", "text": "question"})
        assert ws.receive_json() == {"type": "stream", "text": "one "}
    # Leaving the block disconnected mid-stream; the session waits for the handler to finish.
    assert (llm.opened, llm.closed) == (1, 1)  # the turn closed the adapter stream it consumed
    with client.websocket_connect(WS) as ws:  # a fresh connection is served normally
        authenticate(ws)
        ws.send_json({"type": "message", "text": "question"})
        frames = [ws.receive_json() for _ in range(4)]
    assert frames == [
        {"type": "stream", "text": "one "},
        {"type": "stream", "text": "two "},
        {"type": "stream", "text": "three"},
        {"type": "done"},
    ]
    assert (llm.opened, llm.closed) == (2, 2)


async def test_vanished_client_reraises_disconnect_and_closes_streams_at_once() -> None:
    # The uvicorn path (ARCHITECTURE §13): the next send raises WebSocketDisconnect(1006).
    llm = SlowLLM(delay=0.01)
    socket = VanishedClientSocket(fail_on_send=2)
    with pytest.raises(WebSocketDisconnect):
        await consume_turn(
            socket,  # type: ignore[arg-type]
            orchestrator_over(llm),
            "question",
            USER,
            turn_timeout=0.5,
        )
    assert socket.sent == [{"type": "stream", "text": "one "}]  # no error frame to a gone client
    assert (llm.opened, llm.closed) == (1, 1)  # closed before consume_turn returned (aclosing)
    await asyncio.sleep(0.6)  # E15: no stray cancellation reaches this task after the deadline


class ClosingSocket(VanishedClientSocket):
    """Starlette (after a failed send) and uvicorn (once its close frame is out) raise
    RuntimeError instead of WebSocketDisconnect for a send on a closing socket."""

    async def send_json(self, data: dict[str, Any]) -> None:
        if len(self.sent) + 1 == self.fail_on_send:
            raise RuntimeError('Cannot call "send" once a close message has been sent.')
        self.sent.append(data)

    async def receive(self) -> dict[str, Any]:
        return {"type": "websocket.receive", "text": "not json"}

    async def close(self, code: int = 1000) -> None:
        raise RuntimeError("already closing")


async def test_send_on_a_closing_socket_counts_as_a_disconnect(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # R-21: not an "unexpected turn failure", and no second send to the closing socket.
    llm = SlowLLM(delay=0.01)
    socket = ClosingSocket(fail_on_send=2)
    with caplog.at_level(logging.ERROR), pytest.raises(WebSocketDisconnect):
        await consume_turn(socket, orchestrator_over(llm), "question", USER)  # type: ignore[arg-type]
    assert socket.sent == [{"type": "stream", "text": "one "}]
    assert (llm.opened, llm.closed) == (1, 1)
    assert [record for record in caplog.records if record.exc_info] == []


@pytest.mark.parametrize("fail_on_send", [1, 2], ids=["send_fails", "close_fails"])
async def test_auth_rejection_on_a_closing_socket_returns_quietly(fail_on_send: int) -> None:
    socket = ClosingSocket(fail_on_send=fail_on_send)  # 2: auth_failed is sent, close() raises
    assert await authenticate_first_frame(socket, "secret", 1.0) is None  # type: ignore[arg-type]


def test_timeout_defaults_match_the_spec() -> None:
    # ARCHITECTURE §9.4: each limit is the default of the parameter that applies it.
    def default(applier: Any, name: str) -> Any:
        return inspect.signature(applier).parameters[name].default

    assert {
        "auth": default(authenticate_first_frame, "timeout_seconds"),
        "first chunk": default(OpenAICompatibleLLMAdapter, "first_token_timeout"),
        "turn": default(consume_turn, "turn_timeout"),
        "tool": default(MockEmployeeService, "timeout"),
        "app auth": default(create_app, "auth_timeout"),
        "app turn": default(create_app, "turn_timeout"),
    } == {
        "auth": 10.0,
        "first chunk": 8.0,
        "turn": 30.0,
        "tool": 2.0,
        "app auth": 10.0,
        "app turn": 30.0,
    }
