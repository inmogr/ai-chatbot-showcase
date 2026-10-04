"""Turn errors carry the exact client-facing catalog text (ARCHITECTURE §10, D-67)."""

from typing import ClassVar


class TurnError(Exception):
    """A failure that ends one turn with a single `error` frame; the socket stays open."""

    default_message: ClassVar[str] = "Something went wrong. Please try again."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class EmbeddingError(TurnError):
    default_message = "Knowledge base search temporarily unavailable"


class VectorSearchError(TurnError):
    default_message = "Knowledge base search temporarily unavailable"


class ToolExecutionError(TurnError):
    default_message = "Failed to execute employee lookup."


class LLMBusyError(TurnError):
    default_message = "System is busy due to high demand. Please try again shortly."


class LLMConfigurationError(TurnError):
    default_message = "System configuration error. Please contact support."


class LLMTimeoutError(TurnError):
    default_message = "Response generation timed out. Please try again."


class LLMCutShortError(TurnError):
    default_message = "The answer was cut short. Please ask a narrower question."


class LLMUnavailableError(TurnError):
    default_message = "AI service temporarily unavailable. Please try again."


class StartupCheckError(Exception):
    """The collection is missing or was built for another model; startup aborts (exit 3)."""


class IngestConfigError(Exception):
    """Ingestion cannot proceed (Qdrant unreachable, files vs access table); the CLI exits 1."""
