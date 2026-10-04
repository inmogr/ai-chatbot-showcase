"""The /ws/chat protocol over Starlette's sync TestClient (FR-12…FR-18, FR-30, NFR-07, NFR-12)."""

import json
import logging
import os
import statistics
import subprocess
import sys
import time
from collections.abc import AsyncGenerator
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest
from conftest import TEST_SECRET, ScriptedRunner, make_token, make_unsigned_token
from fastapi.testclient import TestClient
from qdrant_client import AsyncQdrantClient, QdrantClient, models
from starlette.websockets import WebSocketDisconnect

import app.main as main_module
from app.config import ServerConfig
from app.domain.events import StreamTextEvent, TurnDoneEvent, TurnEvent
from app.domain.exceptions import StartupCheckError
from app.domain.models import UserClaims
from app.domain.orchestrator import TurnOrchestrator
from app.main import app as production_app
from app.main import create_app
from app.transport.websocket.routes import router as chat_router

WS = "/ws/chat"
SERVER_FRAME_TYPES = {"auth_success", "auth_failed", "stream", "done", "error"}
LENGTH_TEXT = "Message text must be between 1 and 2000 characters"
STRUCTURE_TEXT = "Invalid message structure"


def auth_ok(ws: Any, token: str | None = None) -> dict[str, Any]:
    ws.send_json({"type": "auth", "token": token or make_token()})
    reply: dict[str, Any] = ws.receive_json()
    assert reply["type"] == "auth_success"
    return reply


def collect_turn(ws: Any, text: str | None = None) -> list[dict[str, Any]]:
    """Send a message (unless already sent) and read frames up to `done` or `error`."""
    if text is not None:
        ws.send_json({"type": "message", "text": text})
    frames: list[dict[str, Any]] = []
    while True:
        frame = ws.receive_json()
        frames.append(frame)
        if frame["type"] in ("done", "error"):
            return frames


def expect_auth_failed(ws: Any, message: str) -> None:
    assert ws.receive_json() == {"type": "auth_failed", "message": message}
    with pytest.raises(WebSocketDisconnect) as closed:
        ws.receive_json()
    assert closed.value.code == 1008


def test_ws_chat_endpoint_accepts_connection(client: TestClient) -> None:
    with client.websocket_connect(WS) as ws:  # plain upgrade, no auth headers
        auth_ok(ws)


def test_first_frame_auth_payload_received(client: TestClient) -> None:
    with client.websocket_connect(WS) as ws:
        reply = auth_ok(ws, make_token("mgr-002", "hr", 2))
    assert (reply["user_id"], reply["level"]) == ("mgr-002", 2)


def test_auth_success_payload_emission(client: TestClient) -> None:
    with client.websocket_connect(WS) as ws:
        ws.send_json({"type": "auth", "token": make_token()})
        assert ws.receive_json() == {
            "type": "auth_success",
            "user_id": "emp-001",
            "department": "hr",
            "level": 1,
        }


@pytest.mark.parametrize(
    ("first_frame", "message"),
    [
        (None, "Authentication timed out"),
        ("not json", "Invalid JSON frame"),
        (json.dumps({"type": "message", "text": "hi"}), "Authentication required as first frame"),
        (json.dumps({"type": "auth"}), "Authentication required as first frame"),
        (json.dumps({"type": "auth", "token": "invalid.token.value"}), "Invalid or expired token"),
    ],
    ids=["timeout", "non_json", "message_first", "missing_token", "bad_token"],
)
def test_auth_failure_emits_frame_and_closes_1008(
    make_client: Any, first_frame: str | None, message: str
) -> None:
    client = make_client(auth_timeout=0.2 if first_frame is None else 5.0)  # short only when timed
    with client.websocket_connect(WS) as ws:
        if first_frame is not None:
            ws.send_text(first_frame)
        expect_auth_failed(ws, message)


JWT_CASES = {
    "expired": lambda: make_token(exp_offset=-60),
    "wrong_secret": lambda: make_token(secret="another-secret-" + "z" * 50),
    "alg_none": make_unsigned_token,
    "missing_sub": lambda: make_token(drop=("sub",)),
    "missing_department": lambda: make_token(drop=("department",)),
    "missing_level": lambda: make_token(drop=("level",)),
    "level_string": lambda: make_token(level="1"),
    "level_bool": lambda: make_token(level=True),
    "level_float": lambda: make_token(level=1.0),
    "missing_exp": lambda: make_token(drop=("exp",)),
}


@pytest.mark.parametrize("case", list(JWT_CASES))
def test_jwt_matrix_ten_cases(client: TestClient, case: str) -> None:
    assert len(JWT_CASES) == 10
    with client.websocket_connect(WS) as ws:
        ws.send_json({"type": "auth", "token": JWT_CASES[case]()})
        expect_auth_failed(ws, "Invalid or expired token")


VALIDATION_CASES = [
    ({"type": "message", "text": "  hello  "}, "hello"),
    ({"type": "message", "text": "hi", "extra": 1}, "hi"),
    ({"type": "message", "text": "a" * 2000}, "a" * 2000),
    ({"type": "message", "text": "👍"}, "👍"),
    ({"type": "message", "text": "   "}, LENGTH_TEXT),
    ({"type": "message", "text": "a" * 2001}, LENGTH_TEXT),
    ({"type": "ping"}, STRUCTURE_TEXT),
    ({"text": "hi"}, STRUCTURE_TEXT),
    ({"type": "message", "text": 5}, STRUCTURE_TEXT),
    ("not json", STRUCTURE_TEXT),
    ({"type": "auth", "token": "again"}, STRUCTURE_TEXT),
]


@pytest.mark.parametrize(
    ("frame", "expected"),
    VALIDATION_CASES,
    ids=[
        "stripped",
        "extra_field",
        "exactly_2000",
        "emoji",
        "whitespace",
        "over_2000",
        "unknown_type",
        "missing_type",
        "non_string_text",
        "non_json",
        "second_auth",
    ],
)
def test_chat_message_frame_validated(
    client: TestClient, runner: ScriptedRunner, frame: Any, expected: str
) -> None:
    with client.websocket_connect(WS) as ws:
        auth_ok(ws)
        ws.send_text(frame if isinstance(frame, str) else json.dumps(frame))
        frames = collect_turn(ws)
        if expected in (LENGTH_TEXT, STRUCTURE_TEXT):
            assert frames == [{"type": "error", "message": expected}]
            assert runner.questions == []
        else:
            assert frames[-1] == {"type": "done"}
            assert runner.questions == [expected]
        assert collect_turn(ws, "still open?")[-1] == {"type": "done"}


def test_stream_tokens_progressive_frames(make_client: Any) -> None:
    deltas = [f"part{i} " for i in range(7)]
    client = make_client(ScriptedRunner(deltas, delay=0.03))
    stamps: list[float] = []
    texts: list[str] = []
    with client.websocket_connect(WS) as ws:
        auth_ok(ws)
        ws.send_json({"type": "message", "text": "stream please"})
        for _ in deltas:
            frame = ws.receive_json()
            stamps.append(time.monotonic())
            assert frame["type"] == "stream"
            texts.append(frame["text"])
        assert ws.receive_json() == {"type": "done"}
    assert "".join(texts) == "".join(deltas)
    assert stamps[-1] - stamps[0] >= 0.15
    # Median, not minimum (R-15): a loaded scheduler may bunch two frames; a burst has ~0 gaps.
    assert statistics.median(later - earlier for earlier, later in pairwise(stamps)) >= 0.02


def test_stream_finishes_with_done_frame(client: TestClient) -> None:
    with client.websocket_connect(WS) as ws:
        auth_ok(ws)
        first = collect_turn(ws, "How many leave days do I get?")
        second = collect_turn(ws, "And sick leave?")  # the socket stays open after `done`
    assert first[-1] == second[-1] == {"type": "done"}
    assert all(frame["type"] == "stream" for frame in first[:-1])


def test_client_html_exact_protocol_flow(client: TestClient) -> None:
    received: list[Any] = []
    with client.websocket_connect(WS) as ws:
        ws.send_text(json.dumps({"type": "auth", "token": make_token()}))
        received.append(json.loads(ws.receive_text()))
        for question in ("How many leave days do I get?", "Who is my manager?"):
            ws.send_text(json.dumps({"type": "message", "text": question}))
            while True:
                received.append(json.loads(ws.receive_text()))
                if received[-1]["type"] == "done":
                    break
    assert received[0]["type"] == "auth_success"
    assert all(isinstance(f, dict) and f["type"] in SERVER_FRAME_TYPES for f in received)
    assert [f["type"] for f in received].count("done") == 2


def test_fastapi_app_lifespan_and_startup(
    settings: ServerConfig, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    # Importing app.main needed no JWT_SECRET (no settings at import), and /ws/chat is routed.
    # FastAPI 0.142 keeps included routers nested, so the route is read from the router.
    assert_imports_without_settings(tmp_path)  # R-16: a scrubbed env and no .env at import
    assert TestClient(production_app).get("/docs").status_code == 404  # R-09
    assert WS in {getattr(route, "path", None) for route in chat_router.routes}
    with pytest.raises(ValueError):
        create_app(settings, None, use_lifespan=False)
    monkeypatch.chdir(
        tmp_path
    )  # no .env here: the lifespan reads its settings from the environment
    with (
        TestClient(create_app(orchestrator=ScriptedRunner())) as live,
        live.websocket_connect(WS) as ws,
    ):
        auth_ok(ws)
        assert collect_turn(ws, "hello world")[-1] == {"type": "done"}


def test_logs_exclude_message_text_tokens_and_jwt(
    make_client: Any, caplog: pytest.LogCaptureFixture
) -> None:
    question, delta, token = "my-private-question", "private-answer-delta", make_token()
    client = make_client(ScriptedRunner([delta]))
    with caplog.at_level(logging.DEBUG):
        with client.websocket_connect(WS) as ws:
            auth_ok(ws, token)
            collect_turn(ws, question)
        with client.websocket_connect(WS) as ws:
            ws.send_json({"type": "auth", "token": token + "tampered"})
            expect_auth_failed(ws, "Invalid or expired token")
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert caplog.records, "the server should log connection metadata"
    for forbidden in (question, delta, token):
        assert forbidden not in logged


def assert_imports_without_settings(workdir: Any) -> None:
    """Import app.main in a fresh interpreter with no JWT_SECRET, no keys and no .env."""
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    done = subprocess.run(
        [sys.executable, "-c", "import app.main"], cwd=workdir, env=env, capture_output=True
    )
    assert done.returncode == 0, done.stderr.decode()


def test_oversized_token_rejected_before_decoding(client: TestClient) -> None:
    # R-01: jwt.decode costs ~86 ns per token byte on the event loop; cap it before decoding.
    with client.websocket_connect(WS) as ws:
        # A correctly signed token that is only too long: accepted before the cap.
        ws.send_json({"type": "auth", "token": make_token(pad="x" * 5000)})
        expect_auth_failed(ws, "Invalid or expired token")


def test_binary_frames_are_rejected_without_crashing(client: TestClient) -> None:
    # R-02: Starlette's receive_text() raised KeyError on a binary frame.
    with client.websocket_connect(WS) as ws:
        ws.send_bytes(b'{"type": "auth"}')
        expect_auth_failed(ws, "Invalid JSON frame")
    with client.websocket_connect(WS) as ws:
        auth_ok(ws)
        ws.send_bytes(b"\x00\x01")
        assert ws.receive_json() == {"type": "error", "message": STRUCTURE_TEXT}
        assert collect_turn(ws, "still open?")[-1] == {"type": "done"}


class StubModel:
    """Stands in for the SentenceTransformer so the lifespan test needs no model download."""

    def get_embedding_dimension(self) -> int:
        return 384


class SpyQdrant(AsyncQdrantClient):
    """An empty in-memory store in place of the server (no collection); records close()."""

    def __init__(self) -> None:
        super().__init__(location=":memory:")
        self.closed = False

    async def close(self, **kwargs: Any) -> None:
        self.closed = True
        await super().close(**kwargs)


def test_lifespan_health_check_aborts_startup_and_closes_clients(
    settings: ServerConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    # D-25: a missing collection fails startup (uvicorn then exits with code 3, drill 2).
    spies: list[SpyQdrant] = []

    def spy_factory(url: str, api_key: str | None) -> SpyQdrant:
        spies.append(SpyQdrant())
        return spies[-1]

    monkeypatch.setattr(main_module, "load_sentence_transformer", lambda name: StubModel())
    monkeypatch.setattr(main_module, "AsyncQdrantClient", spy_factory)
    with (
        pytest.raises(StartupCheckError, match="collection 'acme_policies' not found"),
        TestClient(create_app(settings)),
    ):
        pass  # startup must not complete
    assert [spy.closed for spy in spies] == [True]  # no client leaks from a failed startup


LOGGING_PROBE = """
from fastapi.testclient import TestClient
from conftest import ScriptedRunner, make_token
from app.main import create_app

with TestClient(create_app(orchestrator=ScriptedRunner())) as client:
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"type": "auth", "token": make_token()})
        ws.receive_json()
"""


def test_lifespan_sends_app_logs_to_the_console(tmp_path: Path) -> None:
    # R-12: uvicorn configures only its own loggers, so `app.*` INFO records were dropped.
    root = Path(__file__).resolve().parents[1]
    env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": os.pathsep.join([str(root), str(root / "tests")]),
        "JWT_SECRET": TEST_SECRET,
        "GROQ_API_KEY": "gsk-test-placeholder",
    }
    done = subprocess.run(
        [sys.executable, "-c", LOGGING_PROBE], cwd=tmp_path, env=env, capture_output=True, text=True
    )
    assert done.returncode == 0, done.stderr
    assert "authenticated sub=emp-001" in done.stderr


class RecordingRunner:
    """Records the verified claims each turn runs with."""

    def __init__(self) -> None:
        self.turns: list[tuple[str, str, str, int]] = []

    async def run_turn(self, question: str, user: UserClaims) -> AsyncGenerator[TurnEvent, None]:
        self.turns.append((question, user.sub, user.department, user.level))
        yield StreamTextEvent(f"answer for {user.sub}")
        yield TurnDoneEvent()


def test_each_connection_runs_its_turns_with_its_own_claims(make_client: Any) -> None:
    # The RBAC scope is built from the claims handed to run_turn: two open sockets never mix.
    runner = RecordingRunner()
    client = make_client(runner)
    with client.websocket_connect(WS) as emp, client.websocket_connect(WS) as exe:
        auth_ok(emp, make_token("emp-001", "hr", 1))
        auth_ok(exe, make_token("exec-003", "exec", 3))
        for ws, question in ((exe, "q1"), (emp, "q2"), (exe, "q3")):
            collect_turn(ws, question)
    assert runner.turns == [
        ("q1", "exec-003", "exec", 3),
        ("q2", "emp-001", "hr", 1),
        ("q3", "exec-003", "exec", 3),
    ]


@pytest.mark.parametrize("origin", ["null", "https://elsewhere.example"])
def test_any_origin_is_accepted(client: TestClient, origin: str) -> None:
    # The provided client runs from file:// (Origin: null); auth is the in-band JWT, not cookies.
    with client.websocket_connect(WS, headers={"origin": origin}) as ws:
        auth_ok(ws)
        assert collect_turn(ws, "hello")[-1] == {"type": "done"}


def seed_local_collection(path: Path, name: str, size: int, model: str) -> None:
    store = QdrantClient(path=str(path))
    store.create_collection(
        name, vectors_config=models.VectorParams(size=size, distance=models.Distance.COSINE)
    )
    store.upsert(
        name, points=[models.PointStruct(id=1, vector=[0.1] * size, payload={"model_name": model})]
    )
    store.close()


def use_local_store(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setattr(main_module, "load_sentence_transformer", lambda name: StubModel())
    monkeypatch.setattr(
        main_module, "AsyncQdrantClient", lambda url, api_key: AsyncQdrantClient(path=str(path))
    )


def test_lifespan_starts_on_a_healthy_collection(
    settings: ServerConfig, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seed_local_collection(tmp_path, settings.qdrant_collection, 384, settings.embedding_model)
    use_local_store(monkeypatch, tmp_path)
    with TestClient(create_app(settings)) as client:
        runtime = client.app.state.chat  # type: ignore[attr-defined]
        assert isinstance(runtime.runner, TurnOrchestrator)
        assert (runtime.auth_timeout, runtime.turn_timeout) == (10.0, 30.0)


def test_lifespan_refuses_a_collection_of_another_dimension(
    settings: ServerConfig, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seed_local_collection(tmp_path, settings.qdrant_collection, 768, settings.embedding_model)
    use_local_store(monkeypatch, tmp_path)
    with (
        pytest.raises(StartupCheckError, match="768-d but the model is 384-d"),
        TestClient(create_app(settings)),
    ):
        pass
