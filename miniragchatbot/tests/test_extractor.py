"""Text-layer extraction and the automatic RapidOCR fallback (FR-04, C-05, D-06)."""

from pathlib import Path

import pytest

from app.ingestion.extractor import OcrLine, extract_pages

DOCS = Path(__file__).resolve().parents[1] / "docs"


def test_extract_text_pdf_native_layer() -> None:
    images: list[object] = []

    def spy_ocr(image: object) -> list[OcrLine]:
        images.append(image)
        return []

    pages = extract_pages(DOCS / "hr" / "leave_policy.pdf", run_ocr=spy_ocr)
    assert [page.page for page in pages] == [1]
    assert pages[0].text.splitlines()[0].strip() == "Acme Corp - Leave Policy"
    assert "22 working days" in pages[0].text
    assert images == []  # a page that has a text layer is never OCR'd (D-06)


@pytest.mark.model
def test_extract_scanned_pdf_rapidocr_fallback() -> None:
    (page,) = extract_pages(DOCS / "exec" / "strategic_plan.pdf")
    assert page.page == 1 and page.text == ""
    assert len(page.ocr_lines) == 18
    assert page.ocr_lines[0].text == "Strategic Plan 2026-2028 (Scanned Copy)"
    joined = " ".join(line.text for line in page.ocr_lines)
    assert "Singapore" in joined and "Priority 4" in joined
