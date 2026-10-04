"""Async Qdrant reader: the RBAC filter runs inside `query_points` (D-26, D-27, D-28, NFR-05)."""

from typing import Any

from qdrant_client import AsyncQdrantClient, models

from app.domain.constants import HR_DEPARTMENT, TOP_K
from app.domain.exceptions import StartupCheckError
from app.domain.models import PolicyChunk, RbacScope

REINGEST_HINT = "run `uv run python -m scripts.ingest --docs-dir ./docs`"


def build_rbac_filter(scope: RbacScope) -> models.Filter:
    """`department ∈ {own, "hr"} AND access_level ≤ own level` as one must-clause (D-27).

    The hr exception waives only the department condition; the level check still applies,
    so emp-001 (hr, 1) never sees the manager-only performance review.
    """
    return models.Filter(
        must=[
            models.FieldCondition(
                key="department", match=models.MatchAny(any=[scope.department, HR_DEPARTMENT])
            ),
            models.FieldCondition(key="access_level", range=models.Range(lte=scope.level)),
        ]
    )


class QdrantVectorReader:
    """Satisfies VectorReaderPort; it never drops returned points in Python (the brief: filter
    "at the vector DB query layer", not on Python lists after retrieval)."""

    def __init__(self, client: AsyncQdrantClient, collection: str) -> None:
        self._client = client
        self._collection = collection

    async def query_chunks(
        self, vector: list[float], rbac: RbacScope, top_k: int = TOP_K
    ) -> list[PolicyChunk]:
        response = await self._client.query_points(
            collection_name=self._collection,
            query=vector,
            query_filter=build_rbac_filter(rbac),
            limit=top_k,
            with_payload=True,
        )
        return [_chunk(point.payload or {}) for point in response.points]

    async def verify_collection_health(self, expected_dim: int, expected_model: str) -> None:
        """Startup check (D-25): the collection exists, matches the model's size and model name."""
        if not await self._client.collection_exists(collection_name=self._collection):
            raise StartupCheckError(f"collection '{self._collection}' not found: {REINGEST_HINT}")
        info = await self._client.get_collection(collection_name=self._collection)
        size = getattr(info.config.params.vectors, "size", None)
        if size != expected_dim:
            raise StartupCheckError(
                f"collection is {size}-d but the model is {expected_dim}-d: {REINGEST_HINT}"
            )
        points, _ = await self._client.scroll(
            collection_name=self._collection, limit=1, with_payload=True
        )
        built_with = (points[0].payload or {}).get("model_name") if points else None
        if built_with != expected_model:
            raise StartupCheckError(
                f"collection was built with {built_with!r}, EMBEDDING_MODEL is "
                f"{expected_model!r}: {REINGEST_HINT}"
            )


def _chunk(payload: dict[str, Any]) -> PolicyChunk:
    return PolicyChunk(
        text=str(payload["text"]),
        department=str(payload["department"]),
        access_level=int(payload["access_level"]),
        source_file=str(payload["source_file"]),
        page=int(payload["page"]),
        chunk_index=int(payload["chunk_index"]),
        model_name=str(payload.get("model_name", "")),
    )
