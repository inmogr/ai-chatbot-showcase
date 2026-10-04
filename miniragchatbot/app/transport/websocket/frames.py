"""Frame schemas in both directions and the authenticated-state validation texts (§10, 5-6)."""

from typing import Annotated, Literal

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, StrictStr, StringConstraints, TypeAdapter, ValidationError

from app.domain.constants import ABNORMAL_CLOSURE_CODE, MAX_MESSAGE_CHARS

INVALID_STRUCTURE_TEXT = "Invalid message structure"
INVALID_LENGTH_TEXT = f"Message text must be between 1 and {MAX_MESSAGE_CHARS} characters"
_LENGTH_ERRORS = frozenset({"string_too_short", "string_too_long"})


class AuthFrame(BaseModel):
    """`{"type": "auth", "token": "<jwt>"}` — must be the first frame."""

    type: Literal["auth"]
    token: StrictStr


class MessageFrame(BaseModel):
    """`{"type": "message", "text": "..."}`; the text is stripped, then 1-2000 characters."""

    type: Literal["message"]
    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS)
    ]


CLIENT_FRAME: TypeAdapter[AuthFrame | MessageFrame] = TypeAdapter(
    Annotated[AuthFrame | MessageFrame, Field(discriminator="type")]
)


class FrameError(Exception):
    """An authenticated frame failed validation; `message` is the client-facing text."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AuthSuccessFrame(BaseModel):
    type: Literal["auth_success"] = "auth_success"
    user_id: str
    department: str
    level: int


class AuthFailedFrame(BaseModel):
    type: Literal["auth_failed"] = "auth_failed"
    message: str


class StreamFrame(BaseModel):
    type: Literal["stream"] = "stream"
    text: str


class DoneFrame(BaseModel):
    type: Literal["done"] = "done"


class ErrorFrame(BaseModel):
    type: Literal["error"] = "error"
    message: str


ServerFrame = AuthSuccessFrame | AuthFailedFrame | StreamFrame | DoneFrame | ErrorFrame
"""Every frame the server sends, exactly as the brief's protocol names it."""


async def send_frame(websocket: WebSocket, frame: ServerFrame) -> None:
    """Send one frame as JSON. A RuntimeError means the socket is already closing — Starlette
    raises one for any send after a failed send, uvicorn once its close frame is out — so the
    client is gone, exactly as with WebSocketDisconnect (R-21)."""
    try:
        await websocket.send_json(frame.model_dump())
    except RuntimeError as closing:
        raise WebSocketDisconnect(code=ABNORMAL_CLOSURE_CODE) from closing


async def receive_text_frame(websocket: WebSocket) -> str | None:
    """The next frame's text, or None for a binary frame (R-02: receive_text() raised KeyError)."""
    message = await websocket.receive()
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message.get("code", 1000), message.get("reason"))
    text = message.get("text")
    return text if isinstance(text, str) else None


def parse_message_frame(raw: str | None) -> MessageFrame:
    """Parse a frame received after authentication, or raise FrameError."""
    if raw is None:
        raise FrameError(INVALID_STRUCTURE_TEXT)
    try:
        frame = CLIENT_FRAME.validate_json(raw)
    except ValidationError as exc:
        raise FrameError(_error_text(exc)) from exc
    if not isinstance(frame, MessageFrame):
        raise FrameError(INVALID_STRUCTURE_TEXT)
    return frame


def _error_text(exc: ValidationError) -> str:
    first = exc.errors()[0]
    if first["type"] in _LENGTH_ERRORS and first["loc"][-1:] == ("text",):
        return INVALID_LENGTH_TEXT
    return INVALID_STRUCTURE_TEXT
