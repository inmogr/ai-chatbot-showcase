"""Structural chunking (D-22, C-01): headings, scan paragraphs, title prefix, fallback, counts."""

import json
from pathlib import Path

import pytest

from app.ingestion import chunker
from app.ingestion.chunker import (
    chunk_page,
    fit_to_limit,
    group_scan_lines,
    segment_text_layer,
    split_sentences,
)
from app.ingestion.extractor import OcrLine, PageText, extract_pages
from app.ingestion.pipeline import ACCESS_TABLE

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent / "docs"


def test_structural_heading_chunks() -> None:
    text = (
        "Acme Corp - Compensation Committee Charter\r\n"
        "1. Purpose\r\n"
        "The committee reviews pay.\r\n"
        "2. Membership\r\n"
        "Three independent directors review the\r\n"
        "2026 peer group composition annually.\r\n"
    )
    title, sections = segment_text_layer(text)
    assert title == "Acme Corp - Compensation Committee Charter"
    # A wrapped line that starts with digits ("2026 peer…") is not a heading.
    assert sections == [
        "1. Purpose\nThe committee reviews pay.",
        "2. Membership\nThree independent directors review the "
        "2026 peer group composition annually.",
    ]


def test_scanned_gap_chunks() -> None:
    data = json.loads((HERE / "fixtures" / "strategic_plan_ocr_boxes.json").read_text())
    lines = [OcrLine(line["text"], line["top"], line["bottom"]) for line in data["lines"]]
    title, paragraphs = group_scan_lines(lines)
    assert title == "Strategic Plan 2026-2028 (Scanned Copy)"
    assert len(paragraphs) == 6
    assert paragraphs[0].startswith("Acme Corp Strategic Plan 2026 to 2028.")
    assert [p.split(":")[0] for p in paragraphs[1:5]] == [f"Priority {n}" for n in range(1, 5)]
    assert paragraphs[5].startswith("Board approval")


def test_sentence_regex_documents_initials_limitation() -> None:
    text = "Cost is USD 2,500. Next is Q2 2026. John D. Doe agreed."
    # Documented limitation: initials split ("John D." / "Doe agreed."); none occur in the corpus.
    assert split_sentences(text) == [
        "Cost is USD 2,500.",
        "Next is Q2 2026.",
        "John D.",
        "Doe agreed.",
    ]


@pytest.mark.model
def test_oversize_fallback_packs_sentences_evenly() -> None:
    sentence = "Employees must submit every expense claim within thirty days of the purchase date."
    parts = fit_to_limit(" ".join([sentence] * 12))  # roughly 180-300 bge tokens -> 2 parts
    assert len(parts) == 2
    assert all(part.count(sentence) == 6 for part in parts)
    assert fit_to_limit(sentence) == [sentence]  # short bodies stay whole


@pytest.mark.model
def test_total_corpus_chunk_count_is_42() -> None:
    chunks = {
        rel: [c for page in extract_pages(DOCS / rel) for c in chunk_page(page)]
        for rel in ACCESS_TABLE
    }
    assert sum(len(found) for found in chunks.values()) == 42
    assert all(len(found) == 6 for found in chunks.values())  # incl. 6 from the scan
    titles = ("Acme Corp - ", "Strategic Plan 2026-2028")
    assert all(chunk.startswith(titles) for found in chunks.values() for chunk in found)


def fixture_lines() -> tuple[OcrLine, ...]:
    data = json.loads((HERE / "fixtures" / "strategic_plan_ocr_boxes.json").read_text())
    return tuple(OcrLine(line["text"], line["top"], line["bottom"]) for line in data["lines"])


def test_scan_chunks_carry_the_title_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    # chunk_page on the recorded OCR lines; a word count stands in for the bge tokenizer
    # (every paragraph is far below the 150-token fallback either way).
    monkeypatch.setattr(chunker, "bge_token_count", lambda text: len(text.split()))
    chunks = chunk_page(PageText(page=1, text="", ocr_lines=fixture_lines()))
    assert len(chunks) == 6
    assert all(c.startswith("Strategic Plan 2026-2028 (Scanned Copy)\n\n") for c in chunks)


def test_the_scanned_pdf_goes_through_ocr() -> None:
    # The real PDF has no text layer, so its page is rendered and handed to the OCR runner.
    seen: list[tuple[int, ...]] = []

    def spy(image: object) -> list[OcrLine]:
        seen.append(getattr(image, "shape", ()))
        return [OcrLine("Title", 0.0, 10.0)]

    pages = extract_pages(DOCS / "exec" / "strategic_plan.pdf", run_ocr=spy)
    assert len(seen) == 1 and len(seen[0]) == 3  # one rendered page, an H x W x 3 image
    assert pages[0].ocr_lines == (OcrLine("Title", 0.0, 10.0),)
