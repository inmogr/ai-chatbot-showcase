"""Ports the domain depends on; adapters satisfy them structurally (ARCHITECTURE §5, D-45, D-53)."""

from collections.abc import AsyncGenerator
from typing import Any, Protocol

from app.domain.constants import TOP_K
from app.domain.models import LLMStreamEvent, PolicyChunk, RbacScope


class DocumentEmbedderPort(Protocol):
    """Ingestion side (synchronous CLI): embeds chunk texts."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class VectorWriterPort(Protocol):
    """Ingestion side (synchronous Qdrant client): rebuilds the collection."""

    def recreate_collection(self, vector_size: int) -> None: ...

    def create_payload_indexes(self) -> None: ...

    def upsert_chunks(self, chunks: list[PolicyChunk], vectors: list[list[float]]) -> None: ...


class QueryEmbedderPort(Protocol):
    """Server side (async): embeds the current question."""

    async def embed_query(self, text: str) -> list[float]: ...


class VectorReaderPort(Protocol):
    """Server side (async): RBAC-filtered retrieval, evaluated by the vector database."""

    async def query_chunks(
        self, vector: list[float], rbac: RbacScope, top_k: int = TOP_K
    ) -> list[PolicyChunk]: ...

    async def verify_collection_health(self, expected_dim: int, expected_model: str) -> None: ...


class EmployeeToolPort(Protocol):
    """The one LLM tool; no caller id: the orchestrator does the IDOR check (D-52)."""

    async def get_employee_context(self, user_id: str) -> dict[str, Any]: ...


class LLMPort(Protocol):
    """Streams one chat completion: text deltas as they arrive, then any complete tool calls."""

    def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncGenerator[LLMStreamEvent, None]: ...
