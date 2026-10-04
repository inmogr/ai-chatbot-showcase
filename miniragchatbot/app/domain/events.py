"""Events the orchestrator yields; only the transport turns them into protocol frames."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StreamTextEvent:
    """One text delta, forwarded immediately as a `stream` frame."""

    text: str


@dataclass(frozen=True)
class TurnDoneEvent:
    """The turn finished successfully; the transport sends `done`."""


TurnEvent = StreamTextEvent | TurnDoneEvent
