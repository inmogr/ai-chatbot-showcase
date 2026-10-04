"""Synchronous Qdrant writer for the ingestion CLI (D-24, D-26, D-27, ARCHITECTURE §11)."""

from qdrant_client import QdrantClient, models

from app.domain.exceptions import IngestConfigError
from app.domain.models import PolicyChunk


class QdrantVectorWriter:
    """Satisfies VectorWriterPort: recreate, index the RBAC fields, upsert."""

    def __init__(self, client: QdrantClient, collection: str) -> None:
        self._client = client
        self._collection = collection

    def ping(self) -> None:
        """Fail before any model loads if Qdrant is unreachable (K03)."""
        try:
            self._client.get_collections()
        except Exception as exc:  # any transport failure becomes one clear CLI error
            raise IngestConfigError(f"Qdrant is not reachable: {type(exc).__name__}") from exc

    def recreate_collection(self, vector_size: int) -> None:
        if self._client.collection_exists(collection_name=self._collection):
            self._client.delete_collection(collection_name=self._collection)
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )

    def create_payload_indexes(self) -> None:
        """Index the two fields the RBAC filter uses, so Qdrant filters inside its index."""
        self._client.create_payload_index(
            collection_name=self._collection,
            field_name="department",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        self._client.create_payload_index(
            collection_name=self._collection,
            field_name="access_level",
            field_schema=models.PayloadSchemaType.INTEGER,
        )

    def upsert_chunks(self, chunks: list[PolicyChunk], vectors: list[list[float]]) -> None:
        points = [
            models.PointStruct(id=chunk.point_id, vector=vector, payload=_payload(chunk))
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        self._client.upsert(collection_name=self._collection, points=points, wait=True)


def _payload(chunk: PolicyChunk) -> dict[str, object]:
    return {
        "text": chunk.text,
        "department": chunk.department,
        "access_level": chunk.access_level,  # an int, never a float (E03)
        "source_file": chunk.source_file,
        "page": chunk.page,
        "model_name": chunk.model_name,
        "chunk_index": chunk.chunk_index,
    }
