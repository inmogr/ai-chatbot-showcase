"""Ingestion pipeline: access-table check, extract, chunk, embed, write (ARCHITECTURE §11, D-24)."""

import time
from dataclasses import dataclass
from pathlib import Path

from app.domain.exceptions import IngestConfigError
from app.domain.models import PolicyChunk
from app.domain.ports import DocumentEmbedderPort, VectorWriterPort
from app.ingestion.chunker import chunk_page
from app.ingestion.extractor import PageText, extract_pages

ACCESS_TABLE: dict[str, int] = {  # the brief's table; `department` comes from the folder
    "hr/leave_policy.pdf": 1,
    "hr/code_of_conduct.pdf": 1,
    "hr/performance_review.pdf": 2,
    "finance/expense_policy.pdf": 1,
    "finance/travel_reimbursement.pdf": 1,
    "exec/compensation_committee.pdf": 3,
    "exec/strategic_plan.pdf": 3,
}


@dataclass(frozen=True)
class DocumentSpec:
    path: Path
    department: str
    access_level: int


@dataclass(frozen=True)
class IngestReport:
    files: int
    chunks: int
    seconds: float


def discover_documents(docs_dir: Path) -> list[DocumentSpec]:
    """Match the PDFs on disk to the access table exactly; anything else fails fast."""
    if not docs_dir.is_dir():
        raise IngestConfigError(f"docs directory not found: {docs_dir}")
    found = {
        path.relative_to(docs_dir).as_posix(): path
        for path in sorted(docs_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() == ".pdf"  # .DS_Store and notes are ignored
    }
    unmapped = sorted(set(found) - set(ACCESS_TABLE))
    missing = sorted(set(ACCESS_TABLE) - set(found))
    if unmapped or missing:
        raise IngestConfigError(
            f"files do not match the access table: unmapped={unmapped} missing={missing}"
        )
    return [
        DocumentSpec(found[rel], department=Path(rel).parts[0], access_level=level)
        for rel, level in ACCESS_TABLE.items()
    ]


def build_policy_chunks(
    spec: DocumentSpec, chunk_texts: list[tuple[int, str]], model_name: str
) -> list[PolicyChunk]:
    """Attach the RBAC metadata to each (page, text) chunk of one document."""
    return [
        PolicyChunk(
            text=text,
            department=spec.department,
            access_level=spec.access_level,
            source_file=spec.path.name,
            page=page,
            chunk_index=index,
            model_name=model_name,
        )
        for index, (page, text) in enumerate(chunk_texts)
    ]


def chunk_texts(pages: list[PageText]) -> list[tuple[int, str]]:
    return [(page.page, text) for page in pages for text in chunk_page(page)]


def run_ingestion(
    specs: list[DocumentSpec],
    writer: VectorWriterPort,
    embedder: DocumentEmbedderPort,
    *,
    model_name: str,
    dimension: int,
) -> IngestReport:
    """Rebuild the collection from scratch, so no stale chunk survives a re-run (D-24)."""
    started = time.perf_counter()
    chunks = [
        chunk
        for spec in specs
        for chunk in build_policy_chunks(spec, chunk_texts(extract_pages(spec.path)), model_name)
    ]
    vectors = embedder.embed_documents([chunk.text for chunk in chunks])
    writer.recreate_collection(dimension)
    writer.create_payload_indexes()
    writer.upsert_chunks(chunks, vectors)
    return IngestReport(len(specs), len(chunks), round(time.perf_counter() - started, 1))
