"""In-band authentication of the first WebSocket frame (D-14, D-39; ARCHITECTURE §10 rows 1-4)."""

import asyncio
import logging

import jwt
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.domain.constants import (
    AUTH_TIMEOUT_SECONDS,
    JWT_LEEWAY_SECONDS,
    MAX_TOKEN_CHARS,
    POLICY_VIOLATION_CLOSE_CODE,
)
from app.domain.models import UserClaims
from app.transport.websocket.frames import (
    CLIENT_FRAME,
    AuthFailedFrame,
    AuthFrame,
    receive_text_frame,
    send_frame,
)

logger = logging.getLogger(__name__)

AUTH_TIMEOUT_TEXT = "Authentication timed out"
INVALID_JSON_TEXT = "Invalid JSON frame"
AUTH_REQUIRED_TEXT = "Authentication required as first frame"
INVALID_TOKEN_TEXT = "Invalid or expired token"
REQUIRED_CLAIMS = ["sub", "exp", "department", "level"]


class InvalidTokenError(Exception):
    """The token failed signature, expiry, algorithm or claim validation."""


class AuthRejectedError(Exception):
    """The first frame was rejected; `message` is the client-facing `auth_failed` text."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def decode_claims(token: str, secret: str) -> UserClaims:
    """Verify an HS256 token signed with `secret` and return its validated claims."""
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": REQUIRED_CLAIMS},
            leeway=JWT_LEEWAY_SECONDS,
        )
        return UserClaims.model_validate(payload)
    except (jwt.PyJWTError, ValidationError) as exc:
        raise InvalidTokenError(type(exc).__name__) from exc


def verify_first_frame(raw: str, secret: str) -> UserClaims:
    """Return the claims carried by a valid auth frame, or raise AuthRejectedError."""
    try:
        frame = CLIENT_FRAME.validate_json(raw)
    except ValidationError as exc:
        if exc.errors()[0]["type"] == "json_invalid":
            raise AuthRejectedError(INVALID_JSON_TEXT) from exc
        raise AuthRejectedError(AUTH_REQUIRED_TEXT) from exc
    if not isinstance(frame, AuthFrame):
        raise AuthRejectedError(AUTH_REQUIRED_TEXT)
    if len(frame.token) > MAX_TOKEN_CHARS:  # refuse before any decoding work (R-01)
        logger.warning("authentication rejected: token longer than %d characters", MAX_TOKEN_CHARS)
        raise AuthRejectedError(INVALID_TOKEN_TEXT)
    try:
        return decode_claims(frame.token, secret)
    except InvalidTokenError as exc:
        logger.warning("authentication rejected: %s", exc)
        raise AuthRejectedError(INVALID_TOKEN_TEXT) from exc


async def authenticate(
    websocket: WebSocket, secret: str, timeout_seconds: float = AUTH_TIMEOUT_SECONDS
) -> UserClaims | None:
    """Wait for the first frame; on failure send `auth_failed`, close with 1008 and return None."""
    try:
        async with asyncio.timeout(timeout_seconds):
            raw = await receive_text_frame(websocket)
        if raw is None:  # a binary first frame is not a JSON auth frame (R-02)
            raise AuthRejectedError(INVALID_JSON_TEXT)
        return verify_first_frame(raw, secret)
    except TimeoutError:
        logger.warning("authentication timed out")
        await _reject(websocket, AUTH_TIMEOUT_TEXT)
    except AuthRejectedError as rejected:
        await _reject(websocket, rejected.message)
    return None


async def _reject(websocket: WebSocket, message: str) -> None:
    try:
        await send_frame(websocket, AuthFailedFrame(message=message))
        await websocket.close(code=POLICY_VIOLATION_CLOSE_CODE)
    except (WebSocketDisconnect, RuntimeError):  # RuntimeError: close on a closing socket (R-21)
        logger.info("client left before the auth rejection completed")
