"""Access table, chunk metadata and the ingestion CLI end to end (FR-05…FR-11, D-24, D-64)."""

import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import IngestConfig
from app.domain.exceptions import IngestConfigError
from app.domain.models import PolicyChunk
from app.ingestion.pipeline import (
    ACCESS_TABLE,
    DocumentSpec,
    build_policy_chunks,
    discover_documents,
)
from scripts import ingest

DOCS = Path(__file__).resolve().parents[1] / "docs"
BRIEF_TABLE = {
    "hr/leave_policy.pdf": ("hr", 1),
    "hr/code_of_conduct.pdf": ("hr", 1),
    "hr/performance_review.pdf": ("hr", 2),
    "finance/expense_policy.pdf": ("finance", 1),
    "finance/travel_reimbursement.pdf": ("finance", 1),
    "exec/compensation_committee.pdf": ("exec", 3),
    "exec/strategic_plan.pdf": ("exec", 3),
}


def make_docs(root: Path, files: list[str]) -> Path:
    for relative in files:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"%PDF-1.4 placeholder")
    return root


def relative_of(spec: DocumentSpec) -> str:
    return spec.path.relative_to(DOCS).as_posix()


def chunks_for(relative: str) -> list[PolicyChunk]:
    spec = next(spec for spec in discover_documents(DOCS) if relative_of(spec) == relative)
    texts = [(1, "Title\n\n1. Section\nBody one."), (1, "Title\n\n2. Next\nBody two.")]
    return build_policy_chunks(spec, texts, "BAAI/bge-small-en-v1.5")


def test_point_ids_are_deterministic_uuid5() -> None:
    chunk = PolicyChunk("text", "hr", 1, "leave_policy.pdf", 1, 3)
    assert chunk.point_id == str(uuid.uuid5(uuid.NAMESPACE_URL, "file://leave_policy.pdf/1#3"))
    assert chunk.point_id == PolicyChunk("other", "hr", 1, "leave_policy.pdf", 1, 3).point_id


def test_access_level_canonical_mapping_and_fail_fast(tmp_path: Path) -> None:
    assert {rel: level for rel, (_, level) in BRIEF_TABLE.items()} == ACCESS_TABLE
    found = {
        relative_of(spec): (spec.department, spec.access_level) for spec in discover_documents(DOCS)
    }
    assert found == BRIEF_TABLE  # the department from the folder matches the brief's column
    # RF-1: stray non-PDF files (macOS .DS_Store, notes) are ignored.
    clean = make_docs(tmp_path / "clean", [*BRIEF_TABLE, "hr/.DS_Store", "finance/notes.txt"])
    assert len(discover_documents(clean)) == 7
    broken_layouts = {
        "unmapped_pdf": [*BRIEF_TABLE, "hr/extra_policy.pdf"],
        "missing_file": [rel for rel in BRIEF_TABLE if rel != "exec/strategic_plan.pdf"],
        "wrong_case": ["HR/leave_policy.pdf", *[r for r in BRIEF_TABLE if not r.startswith("hr/")]],
    }
    for name, files in broken_layouts.items():
        with pytest.raises(IngestConfigError):
            discover_documents(make_docs(tmp_path / name, files))
    with pytest.raises(IngestConfigError):
        discover_documents(tmp_path / "no-such-dir")


def test_metadata_department_extracted_from_folder() -> None:
    assert {chunk.department for chunk in chunks_for("finance/travel_reimbursement.pdf")} == {
        "finance"
    }


def test_metadata_access_level_integer_type() -> None:
    levels = [chunk.access_level for chunk in chunks_for("hr/performance_review.pdf")]
    assert levels == [2, 2]
    assert all(type(level) is int for level in levels)


def test_metadata_source_file_persisted() -> None:
    assert {chunk.source_file for chunk in chunks_for("hr/leave_policy.pdf")} == {
        "leave_policy.pdf"
    }


def test_metadata_page_number_1_based() -> None:
    chunks = chunks_for("exec/compensation_committee.pdf")
    assert [chunk.page for chunk in chunks] == [1, 1]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]


def test_ingest_rejects_unknown_embedding_provider(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    with pytest.raises(ValidationError):
        IngestConfig(_env_file=None)
    assert ingest.main(["--docs-dir", str(DOCS)]) == 1  # stops before touching Qdrant or a model
    assert "embedding_provider" in capsys.readouterr().err


def test_docs_dir_flag_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCS_DIR", "/somewhere/else")
    config = IngestConfig(_env_file=None)
    assert ingest.resolve_docs_dir("./docs", config) == Path("./docs")
    assert ingest.resolve_docs_dir(None, config) == Path("/somewhere/else")


@pytest.mark.model
@pytest.mark.qdrant
def test_ingest_cli_execution_and_exit_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from qdrant_client import QdrantClient

    monkeypatch.setenv("QDRANT_COLLECTION", "acme_policies_test")
    for _ in range(2):  # the second run recreates the collection: still 42 points
        assert ingest.main(["--docs-dir", str(DOCS)]) == 0
    assert "ingested 7 files, 42 chunks" in capsys.readouterr().out
    client = QdrantClient(url="http://localhost:6333")
    assert client.count("acme_policies_test", exact=True).count == 42
    vectors = client.get_collection("acme_policies_test").config.params.vectors
    assert getattr(vectors, "size", None) == 384
    points, _ = client.scroll("acme_policies_test", limit=100, with_payload=True)
    expected = {Path(rel).name: level for rel, (_, level) in BRIEF_TABLE.items()}
    for point in points:
        payload = point.payload or {}
        assert type(payload["access_level"]) is int
        assert payload["access_level"] == expected[payload["source_file"]]
        assert payload["page"] == 1 and payload["model_name"] == "BAAI/bge-small-en-v1.5"
    assert sum((p.payload or {})["source_file"] == "strategic_plan.pdf" for p in points) == 6
