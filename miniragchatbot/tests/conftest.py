"""Shared fixtures: token minting, a scripted fake turn runner, the app without its lifespan."""

import asyncio
import base64
import json
import logging
import socket
import time
from collections.abc import AsyncGenerator, Callable, Iterator
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import IngestConfig, ServerConfig
from app.domain.events import StreamTextEvent, TurnDoneEvent, TurnEvent
from app.domain.models import TextDelta, UserClaims
from app.main import create_app

TEST_SECRET = "test-secret-for-the-suite-" + "0123456789" * 4
CONFIG_VARIABLES = sorted(
    {name.upper() for name in ServerConfig.model_fields | IngestConfig.model_fields}
)


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False


def pytest_runtest_setup(item: pytest.Item) -> None:
    """A selected `qdrant` test skips (not fails) when no Qdrant server is running."""
    if item.get_closest_marker("qdrant") and not _port_open("localhost", 6333):
        pytest.skip("needs a Qdrant server on localhost:6333")


def make_token(
    sub: str = "emp-001",
    department: str = "hr",
    level: Any = 1,
    *,
    secret: str = TEST_SECRET,
    exp_offset: int = 3600,
    drop: tuple[str, ...] = (),
    algorithm: str = "HS256",
    **claims: Any,
) -> str:
    """Mint a token shaped like mint_tokens.py's, with knobs for the negative cases."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": sub,
        "email": f"{sub}@test.com",
        "department": department,
        "level": level,
        "iat": now,
        "exp": now + exp_offset,
        **claims,
    }
    for claim in drop:
        payload.pop(claim)
    return jwt.encode(payload, secret, algorithm=algorithm)


def make_unsigned_token() -> str:
    """A hand-built `alg: none` token (PyJWT refuses to encode one with a non-empty key)."""
    now = int(time.time())
    payload = {"sub": "emp-001", "department": "hr", "level": 1, "iat": now, "exp": now + 3600}

    def segment(data: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{segment({'alg': 'none', 'typ': 'JWT'})}.{segment(payload)}."


class ScriptedRunner:
    """Fake turn runner: yields scripted deltas (optionally delayed) and records each question."""

    def __init__(self, deltas: list[str] | None = None, delay: float = 0.0) -> None:
        self.deltas = deltas if deltas is not None else ["You are ", "entitled to ", "22 days."]
        self.delay = delay
        self.questions: list[str] = []

    async def run_turn(self, question: str, user: UserClaims) -> AsyncGenerator[TurnEvent, None]:
        self.questions.append(question)
        for text in self.deltas:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield StreamTextEvent(text)
        yield TurnDoneEvent()


@pytest.fixture(autouse=True)
def isolated_app_logger() -> Iterator[None]:
    """The lifespan gives the `app` logger a handler and the INFO level for the whole process;
    restore both, so a later DEBUG-level log test still sees every record."""
    app_logger = logging.getLogger("app")
    handlers, level = list(app_logger.handlers), app_logger.level
    yield
    app_logger.handlers[:] = handlers
    app_logger.setLevel(level)


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> ServerConfig:
    for name in CONFIG_VARIABLES:  # e.g. QDRANT_COLLECTION exported for an integration run
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test-placeholder")  # never sent: tests use fakes
    return ServerConfig(_env_file=None)


@pytest.fixture
def runner() -> ScriptedRunner:
    return ScriptedRunner()


@pytest.fixture
def make_user_token() -> Callable[..., str]:
    return make_token


@pytest.fixture
def make_client(settings: ServerConfig) -> Iterator[Callable[..., TestClient]]:
    """Build clients over create_app(..., use_lifespan=False); no Qdrant, model or key needed."""
    clients: list[TestClient] = []

    def factory(runner: Any = None, auth_timeout: float = 5.0, **timeouts: float) -> TestClient:
        app = create_app(
            settings,
            runner or ScriptedRunner(),
            use_lifespan=False,
            auth_timeout=auth_timeout,
            **timeouts,  # e.g. turn_timeout
        )
        client = TestClient(app)
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()


@pytest.fixture
def client(make_client: Callable[..., TestClient], runner: ScriptedRunner) -> TestClient:
    return make_client(runner)


class FakeQueryEmbedder:
    """QueryEmbedderPort fake: a constant 384-d vector, or a failure."""

    def __init__(self, fail: bool = False, log: list[str] | None = None) -> None:
        self.fail = fail
        self.log = log if log is not None else []
        self.queries: list[str] = []

    async def embed_query(self, text: str) -> list[float]:
        self.log.append("embed")
        self.queries.append(text)
        if self.fail:
            raise RuntimeError("embedder down")
        return [0.05] * 384


class FakeVectorReader:
    """VectorReaderPort test double for orchestrator tests only (production filters in Qdrant)."""

    def __init__(
        self, chunks: list[Any] | None = None, fail: bool = False, log: list[str] | None = None
    ) -> None:
        self.chunks = chunks or []
        self.fail = fail
        self.log = log if log is not None else []
        self.calls: list[tuple[Any, int]] = []

    async def query_chunks(self, vector: list[float], rbac: Any, top_k: int = 4) -> list[Any]:
        self.log.append("query")
        self.calls.append((rbac, top_k))
        if self.fail:
            raise RuntimeError("qdrant down")
        return self.chunks[:top_k]

    async def verify_collection_health(self, expected_dim: int, expected_model: str) -> None:
        return None


class RecordingLLM:
    """LLMPort fake: records the messages it receives and streams a fixed answer."""

    def __init__(
        self, words: tuple[str, ...] = ("one ", "two ", "three "), log: list[str] | None = None
    ) -> None:
        self.words = words
        self.log = log if log is not None else []
        self.closed = False
        self.messages: list[dict[str, Any]] = []

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncGenerator[Any, None]:
        self.log.append("llm")
        self.messages = messages
        try:
            for word in self.words:
                yield TextDelta(word)
        finally:
            self.closed = True


class ScriptedLLM:
    """LLMPort fake for multi-pass turns: each call streams the next scripted list of events."""

    def __init__(self, passes: list[list[Any]], log: list[str] | None = None) -> None:
        self.passes = list(passes)
        self.log = log if log is not None else []
        self.calls: list[dict[str, Any]] = []

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncGenerator[Any, None]:
        self.calls.append({"messages": messages, "tools": tools, "tool_choice": tool_choice})
        self.log.append(f"llm{len(self.calls)}")
        for event in self.passes.pop(0):
            if isinstance(event, TextDelta):
                self.log.append(f"text:{event.text}")
            yield event


class FakeEmployeeTool:
    """EmployeeToolPort fake: returns the brief's combined result instantly and records calls."""

    RESULT = {
        "profile": {"name": "Jane Doe", "grade": "Senior"},
        "manager": {"manager": "John Smith"},
        "team": {"team_size": 8, "team_name": "Platform"},
    }

    def __init__(self, log: list[str] | None = None) -> None:
        self.log = log if log is not None else []
        self.calls: list[str] = []

    async def get_employee_context(self, user_id: str) -> dict[str, Any]:
        self.log.append("tool")
        self.calls.append(user_id)
        return dict(self.RESULT)
