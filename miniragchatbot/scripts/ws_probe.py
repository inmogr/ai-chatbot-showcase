"""Command-line WebSocket client for /ws/chat (D-84).

    uv run python -m scripts.ws_probe --token <jwt> "How many leave days do I get?"

Prints every frame with the seconds elapsed since its question was sent, so the streaming cadence
is visible. `--origin null` sends the same Origin header as the file:// test client.
"""

import argparse
import asyncio
import json
import time

from websockets.asyncio.client import ClientConnection, connect
from websockets.typing import Origin

DEFAULT_URL = "ws://localhost:8000/ws/chat"
TERMINAL_TYPES = frozenset({"done", "error"})


async def converse(url: str, token: str, questions: list[str], origin: str | None) -> int:
    """Authenticate, ask each question in turn and print every frame; 0 means success."""
    async with connect(url, origin=Origin(origin) if origin else None) as ws:
        await ws.send(json.dumps({"type": "auth", "token": token}))
        auth = json.loads(await ws.recv())
        print(f"auth     {json.dumps(auth)}")
        if auth.get("type") != "auth_success":
            await ws.wait_closed()
            print(f"closed   code={ws.close_code}")
            return 1
        for question in questions:
            await _ask(ws, question)
    return 0


async def _ask(ws: ClientConnection, question: str) -> None:
    await ws.send(json.dumps({"type": "message", "text": question}))
    started = time.perf_counter()
    while True:
        frame = json.loads(await ws.recv())
        print(f"+{time.perf_counter() - started:6.3f}s {json.dumps(frame)}")
        if frame.get("type") in TERMINAL_TYPES:
            return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Talk to /ws/chat from the command line.")
    parser.add_argument("questions", nargs="*", help="messages to send, one turn each")
    parser.add_argument("--token", required=True, help="a JWT, e.g. from mint_tokens.py")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--origin", default=None, help='e.g. "null" to mimic the file:// client')
    args = parser.parse_args(argv)
    return asyncio.run(converse(args.url, args.token, args.questions, args.origin))


if __name__ == "__main__":
    raise SystemExit(main())
