"""RBAC at the vector-DB query layer (FR-03, FR-19, FR-20, NFR-05, C-04, D-25, D-27)."""

import time
import warnings
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from qdrant_client import AsyncQdrantClient, QdrantClient, models

from app.adapters.vector_store.qdrant_reader import QdrantVectorReader, build_rbac_filter
from app.adapters.vector_store.qdrant_writer import QdrantVectorWriter
from app.domain.exceptions import StartupCheckError
from app.domain.models import PolicyChunk, RbacScope
from app.ingestion.pipeline import ACCESS_TABLE

TEST_COLLECTION = "acme_policies_test"


class SpyQdrant:
    """Records query_points calls; has no `search`, so calling it would fail the test."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def query_points(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(points=[])


async def test_qdrant_rbac_department_and_level_filter() -> None:
    spy = SpyQdrant()
    reader = QdrantVectorReader(spy, "c")  # type: ignore[arg-type]
    assert await reader.query_chunks([0.1] * 384, RbacScope("finance", 1)) == []
    (call,) = spy.calls
    assert call["limit"] == 4
    assert call["query_filter"] == models.Filter(
        must=[
            models.FieldCondition(key="department", match=models.MatchAny(any=["finance", "hr"])),
            models.FieldCondition(key="access_level", range=models.Range(lte=1)),
        ]
    )


class FakeCollections:
    def __init__(self, *, exists: bool = True, size: int = 384, model: str | None = "bge") -> None:
        self.exists, self.size, self.model = exists, size, model

    async def collection_exists(self, **_: Any) -> bool:
        return self.exists

    async def get_collection(self, **_: Any) -> Any:
        vectors = SimpleNamespace(size=self.size)
        return SimpleNamespace(config=SimpleNamespace(params=SimpleNamespace(vectors=vectors)))

    async def scroll(self, **_: Any) -> Any:
        if self.model is None:  # an empty collection: nothing to sample
            return [], None
        return [SimpleNamespace(payload={"model_name": self.model})], None


async def test_verify_collection_health_rejects_bad_collections() -> None:
    healthy = QdrantVectorReader(FakeCollections(), "c")  # type: ignore[arg-type]
    await healthy.verify_collection_health(384, "bge")
    for broken in (
        FakeCollections(exists=False),
        FakeCollections(size=768),
        FakeCollections(model="all-MiniLM-L6-v2"),
        FakeCollections(model=None),  # an empty collection is no index
    ):
        with pytest.raises(StartupCheckError):
            await QdrantVectorReader(broken, "c").verify_collection_health(384, "bge")  # type: ignore[arg-type]


def seed(client: QdrantClient) -> QdrantClient:
    """The 42 real payloads (6 per file, levels from the access table) with synthetic vectors."""
    if client.collection_exists(collection_name=TEST_COLLECTION):
        client.delete_collection(collection_name=TEST_COLLECTION)
    client.create_collection(
        collection_name=TEST_COLLECTION,
        vectors_config=models.VectorParams(size=4, distance=models.Distance.COSINE),
    )
    for field, schema in (("department", "keyword"), ("access_level", "integer")):
        client.create_payload_index(
            collection_name=TEST_COLLECTION, field_name=field, field_schema=schema
        )
    points = [
        models.PointStruct(
            id=index * 10 + chunk,
            vector=[1.0, float(chunk), float(index), 0.5],
            payload={
                "text": f"{rel} chunk {chunk}",
                "department": rel.split("/")[0],
                "access_level": level,
                "source_file": rel.split("/")[1],
                "page": 1,
                "chunk_index": chunk,
                "model_name": "synthetic",
            },
        )
        for index, (rel, level) in enumerate(ACCESS_TABLE.items())
        for chunk in range(6)
    ]
    client.upsert(collection_name=TEST_COLLECTION, points=points, wait=True)
    return client


@pytest.fixture(scope="module")
def seeded_server() -> QdrantClient:
    return seed(QdrantClient(url="http://localhost:6333"))


@pytest.fixture(scope="module")
def seeded_memory() -> QdrantClient:
    # Local mode applies the same filter semantics, so the counts run offline too (it has no
    # payload indexes, hence the filtered warning).
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", "Payload indexes have no effect", UserWarning)
        return seed(QdrantClient(":memory:"))


@pytest.fixture(params=["memory", pytest.param("server", marks=pytest.mark.qdrant)])
def seeded(request: pytest.FixtureRequest) -> QdrantClient:
    return cast(QdrantClient, request.getfixturevalue(f"seeded_{request.param}"))


def visible(client: QdrantClient, department: str, level: int) -> tuple[int, set[str]]:
    scope_filter = build_rbac_filter(RbacScope(department, level))
    count = client.count(collection_name=TEST_COLLECTION, count_filter=scope_filter, exact=True)
    points, _ = client.scroll(
        collection_name=TEST_COLLECTION, scroll_filter=scope_filter, limit=100, with_payload=True
    )
    return count.count, {(point.payload or {})["source_file"] for point in points}


def test_rbac_filter_emp001_sees_12_chunks(seeded: QdrantClient) -> None:
    count, files = visible(seeded, "hr", 1)
    assert count == 12 and files == {"leave_policy.pdf", "code_of_conduct.pdf"}


def test_rbac_filter_mgr002_sees_18_chunks(seeded: QdrantClient) -> None:
    count, files = visible(seeded, "hr", 2)
    assert count == 18 and "performance_review.pdf" in files


def test_rbac_filter_fin001_sees_24_chunks(seeded: QdrantClient) -> None:
    count, files = visible(seeded, "finance", 1)
    assert count == 24 and "performance_review.pdf" not in files  # hr exception keeps the level


def test_rbac_filter_exec003_sees_30_chunks_and_no_finance(seeded: QdrantClient) -> None:
    count, files = visible(seeded, "exec", 3)
    assert count == 30
    assert not files & {"expense_policy.pdf", "travel_reimbursement.pdf"}


def test_rbac_filter_unknown_department_sees_hr_only(seeded: QdrantClient) -> None:
    for department in ("HR", "legal"):  # RF-3: unknown or differently-cased departments
        count, files = visible(seeded, department, 1)
        assert count == 12 and files == {"leave_policy.pdf", "code_of_conduct.pdf"}


@pytest.mark.qdrant
async def test_filtered_query_returns_at_most_4_under_200ms(seeded_server: QdrantClient) -> None:
    client = AsyncQdrantClient(url="http://localhost:6333")
    reader = QdrantVectorReader(client, TEST_COLLECTION)
    scope, vector = RbacScope("hr", 1), [1.0, 0.0, 0.0, 0.5]
    try:
        await reader.query_chunks(vector, scope)  # warm the connection: time the query only
        started = time.perf_counter()
        chunks = await reader.query_chunks(vector, scope)
        elapsed = time.perf_counter() - started
    finally:
        await client.close()
    assert 0 < len(chunks) <= 4 and elapsed < 0.2
    assert {chunk.source_file for chunk in chunks} <= {"leave_policy.pdf", "code_of_conduct.pdf"}


@pytest.mark.filterwarnings("ignore:Payload indexes have no effect:UserWarning")
async def test_writer_and_reader_round_trip_the_payload(tmp_path: Path) -> None:
    # Offline, through the real writer and reader: payload keys, int levels, recreate, the RBAC
    # filter and the payload-to-chunk mapping must all agree.
    leave = PolicyChunk("Leave text", "hr", 1, "leave_policy.pdf", 1, 0, "bge")
    plan = PolicyChunk("Plan text", "exec", 3, "strategic_plan.pdf", 1, 0, "bge")
    store = QdrantClient(path=str(tmp_path))
    writer = QdrantVectorWriter(store, "round_trip")
    writer.recreate_collection(4)
    writer.create_payload_indexes()
    stale = replace(plan, chunk_index=1)
    writer.upsert_chunks(
        [leave, plan, stale], [[1.0, 0, 0, 0.5], [0, 1.0, 0, 0.5], [0, 1.0, 0, 0.6]]
    )
    writer.recreate_collection(4)  # a re-run starts clean: the stale point must go
    writer.upsert_chunks([leave, plan], [[1.0, 0, 0, 0.5], [0, 1.0, 0, 0.5]])
    stored, _ = store.scroll(collection_name="round_trip", limit=10, with_payload=True)
    assert len(stored) == 2
    assert {type((point.payload or {})["access_level"]) for point in stored} == {int}
    store.close()
    client = AsyncQdrantClient(path=str(tmp_path))
    reader = QdrantVectorReader(client, "round_trip")
    try:
        await reader.verify_collection_health(4, "bge")
        assert await reader.query_chunks([1.0, 0, 0, 0.5], RbacScope("hr", 1)) == [leave]
        found = await reader.query_chunks([0, 1.0, 0, 0.5], RbacScope("exec", 3))
        assert sorted(chunk.source_file for chunk in found) == [
            "leave_policy.pdf",
            "strategic_plan.pdf",
        ]
    finally:
        await client.close()


@pytest.mark.live_llm
async def test_unauthorized_query_returns_refusal() -> None:
    from pydantic import ValidationError

    from app.config import ServerConfig
    from app.domain.models import UserClaims
    from app.main import production_orchestrator

    try:
        config = ServerConfig(_env_file=".env")
    except ValidationError:
        pytest.skip("needs a real provider key in miniragchatbot/.env")
    refusal = "I cannot find that information in the authorised company policies."
    user = UserClaims(sub="emp-001", exp=1, department="hr", level=1)
    async with production_orchestrator(config) as orchestrator:
        for question in (
            "What are the strategic priorities for APAC expansion?",
            "What is the capital of France?",
        ):
            text = ""
            async for event in orchestrator.run_turn(question, user):
                text += getattr(event, "text", "")
            assert text.strip() == refusal, question
