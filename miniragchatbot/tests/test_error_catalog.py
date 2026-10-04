"""Turn failures reach the client as one error frame and the socket stays open (FR-29, NFR-11)."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from conftest import make_token

from app.domain.events import StreamTextEvent, TurnDoneEvent, TurnEvent
from app.domain.exceptions import (
    EmbeddingError,
    LLMBusyError,
    LLMConfigurationError,
    LLMCutShortError,
    LLMTimeoutError,
    LLMUnavailableError,
    ToolExecutionError,
    VectorSearchError,
)
from app.domain.models import UserClaims

WS = "/ws/chat"
GENERIC_TEXT = "Something went wrong. Please try again."

# ARCHITECTURE §10 rows 7-14, verbatim; several conditions share one text.
TURN_CATALOG: list[tuple[Exception, str]] = [
    (EmbeddingError(), "Knowledge base search temporarily unavailable"),
    (VectorSearchError(), "Knowledge base search temporarily unavailable"),
    (ToolExecutionError(), "Failed to execute employee lookup."),
    (LLMBusyError(), "System is busy due to high demand. Please try again shortly."),
    (LLMConfigurationError(), "System configuration error. Please contact support."),
    (LLMTimeoutError(), "Response generation timed out. Please try again."),
    (LLMCutShortError(), "The answer was cut short. Please ask a narrower question."),
    (LLMUnavailableError(), "AI service temporarily unavailable. Please try again."),
    # Row 11 for the consumer is its own 30 s deadline only (test_timeouts.py); a bare
    # TimeoutError from inside the turn is an unmapped fault, so the last resort logs it (R-19).
    (TimeoutError(), GENERIC_TEXT),
    (RuntimeError("internal detail"), GENERIC_TEXT),  # row 14: the last resort
]


class FailingOnceRunner:
    """The first turn streams one delta, then raises `failure`; later turns succeed."""

    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure or LLMBusyError()
        self.calls = 0

    async def run_turn(self, question: str, user: UserClaims) -> AsyncGenerator[TurnEvent, None]:
        self.calls += 1
        if self.calls == 1:
            yield StreamTextEvent("partial ")
            raise self.failure
        yield StreamTextEvent("fine")
        yield TurnDoneEvent()


class EchoRunner:
    """Answers with two delayed deltas naming the question, so interleaved turns would show."""

    def __init__(self, delay: float = 0.05) -> None:
        self.delay = delay
        self.questions: list[str] = []

    async def run_turn(self, question: str, user: UserClaims) -> AsyncGenerator[TurnEvent, None]:
        self.questions.append(question)
        for part in (1, 2):
            await asyncio.sleep(self.delay)
            yield StreamTextEvent(f"{question}-{part}")
        yield TurnDoneEvent()


def authenticate(ws: Any) -> None:
    ws.send_json({"type": "auth", "token": make_token()})
    assert ws.receive_json()["type"] == "auth_success"


def fail_then_recover(make_client: Any, runner: FailingOnceRunner, expected_text: str) -> None:
    """One failed turn (partial delta, then the error frame), then a normal turn on the socket."""
    with make_client(runner).websocket_connect(WS) as ws:
        authenticate(ws)
        ws.send_json({"type": "message", "text": "first"})
        assert ws.receive_json() == {"type": "stream", "text": "partial "}
        assert ws.receive_json() == {"type": "error", "message": expected_text}
        ws.send_json({"type": "message", "text": "second"})
        assert ws.receive_json() == {"type": "stream", "text": "fine"}
        assert ws.receive_json() == {"type": "done"}


@pytest.mark.parametrize(
    ("failure", "text"), TURN_CATALOG, ids=[type(failure).__name__ for failure, _ in TURN_CATALOG]
)
def test_catalog_exact_strings_mapped_verbatim(
    make_client: Any, failure: Exception, text: str
) -> None:
    fail_then_recover(make_client, FailingOnceRunner(failure), text)


def test_downstream_failure_emits_error_frame_and_keeps_socket_open(make_client: Any) -> None:
    runner = FailingOnceRunner()
    fail_then_recover(
        make_client, runner, "System is busy due to high demand. Please try again shortly."
    )
    assert runner.calls == 2  # the failed turn was not retried


def test_unexpected_failure_logs_traceback_and_hides_detail(
    make_client: Any, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        fail_then_recover(
            make_client, FailingOnceRunner(RuntimeError("internal detail")), GENERIC_TEXT
        )
    tracebacks = [record for record in caplog.records if record.exc_info]
    assert len(tracebacks) == 1  # logger.exception in the last-resort handler (§13)
    assert isinstance(tracebacks[0].exc_info[1], RuntimeError)  # type: ignore[index]


def test_turn_error_log_names_its_cause(make_client: Any, caplog: pytest.LogCaptureFixture) -> None:
    # R-20: §10 sends details to the server log only — the cause's class, never its text.
    failure = ToolExecutionError()
    failure.__cause__ = KeyError("team-service-detail")
    with caplog.at_level(logging.WARNING):
        fail_then_recover(
            make_client, FailingOnceRunner(failure), "Failed to execute employee lookup."
        )
    assert "ToolExecutionError" in caplog.text and "cause=KeyError" in caplog.text
    assert "team-service-detail" not in caplog.text


class UnknownEventRunner:
    """Streams one delta, then yields an object that is not a TurnEvent."""

    async def run_turn(self, question: str, user: UserClaims) -> AsyncGenerator[Any, None]:
        yield StreamTextEvent("partial ")
        yield object()


def test_unknown_turn_event_is_not_reported_as_done(make_client: Any) -> None:
    # R-22: only TurnDoneEvent may produce `done`; anything else is an unexpected failure.
    with make_client(UnknownEventRunner()).websocket_connect(WS) as ws:
        authenticate(ws)
        ws.send_json({"type": "message", "text": "question"})
        assert ws.receive_json() == {"type": "stream", "text": "partial "}
        assert ws.receive_json() == {"type": "error", "message": GENERIC_TEXT}


def test_back_to_back_messages_answered_in_order(make_client: Any) -> None:
    runner = EchoRunner()
    with make_client(runner).websocket_connect(WS) as ws:
        authenticate(ws)
        ws.send_json({"type": "message", "text": "first"})
        ws.send_json({"type": "message", "text": "second"})  # sent before any answer arrives
        frames = [ws.receive_json() for _ in range(6)]
    assert frames == [
        {"type": "stream", "text": "first-1"},
        {"type": "stream", "text": "first-2"},
        {"type": "done"},
        {"type": "stream", "text": "second-1"},
        {"type": "stream", "text": "second-2"},
        {"type": "done"},
    ]
    assert runner.questions == ["first", "second"]
