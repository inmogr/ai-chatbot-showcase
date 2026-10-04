"""Ingestion CLI — the second, CLI-only composition root (D-04, D-24, D-66).

    uv run python -m scripts.ingest --docs-dir ./docs

Checks Qdrant first, validates the files against the access table, then extracts (OCR only for a
page with no text layer), chunks, embeds and rebuilds the collection. Exit 0 on success, 1 on a
configuration or input error.
"""

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError
from qdrant_client import QdrantClient

from app.adapters.embedder.sentence_transformer import (
    SentenceTransformerAdapter,
    load_sentence_transformer,
)
from app.adapters.vector_store.qdrant_writer import QdrantVectorWriter
from app.config import IngestConfig
from app.domain.exceptions import IngestConfigError
from app.ingestion.pipeline import IngestReport, discover_documents, run_ingestion


def resolve_docs_dir(flag: str | None, config: IngestConfig) -> Path:
    """`--docs-dir` overrides `DOCS_DIR` (D-64)."""
    return Path(flag) if flag else Path(config.docs_dir)


def ingest(docs_flag: str | None) -> tuple[IngestReport, str]:
    config = IngestConfig()
    api_key = config.qdrant_api_key.get_secret_value() if config.qdrant_api_key else None
    writer = QdrantVectorWriter(
        QdrantClient(url=config.qdrant_url, api_key=api_key), config.qdrant_collection
    )
    writer.ping()  # before any model loads
    specs = discover_documents(resolve_docs_dir(docs_flag, config))
    embedder = SentenceTransformerAdapter(
        load_sentence_transformer(config.embedding_model), config.embedding_model
    )
    report = run_ingestion(
        specs, writer, embedder, model_name=config.embedding_model, dimension=embedder.dimension
    )
    return report, config.qdrant_collection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Index the policy PDFs into Qdrant.")
    parser.add_argument("--docs-dir", default=None, help="overrides DOCS_DIR (default ./docs)")
    args = parser.parse_args(argv)
    try:
        report, collection = ingest(args.docs_dir)
    except (IngestConfigError, ValidationError) as error:
        print(f"ingestion failed: {error}", file=sys.stderr)
        return 1
    print(
        f"ingested {report.files} files, {report.chunks} chunks into '{collection}' "
        f"in {report.seconds:.1f} s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
