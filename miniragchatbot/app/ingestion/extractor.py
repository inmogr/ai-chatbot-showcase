"""Text extraction: the PDF text layer, and RapidOCR for pages that have none (D-05…D-07)."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium

from app.domain.constants import OCR_RENDER_DPI


@dataclass(frozen=True)
class OcrLine:
    """One recognised line and its vertical extent in pixels (for paragraph grouping)."""

    text: str
    top: float
    bottom: float


@dataclass(frozen=True)
class PageText:
    """A 1-based page: its text layer, or — when that is empty — the OCR lines."""

    page: int
    text: str
    ocr_lines: tuple[OcrLine, ...] = ()


OcrRunner = Callable[[Any], list[OcrLine]]


@cache
def _ocr_engine() -> Any:
    from rapidocr import RapidOCR  # imported lazily: loads onnxruntime and the bundled models

    return RapidOCR()


def rapid_ocr_lines(image: Any) -> list[OcrLine]:
    """Run RapidOCR (bundled ONNX models, no system packages) and sort the lines top-down."""
    result = _ocr_engine()(image)
    if result.boxes is None:
        return []
    lines = [
        OcrLine(
            text=str(text), top=float(min(p[1] for p in box)), bottom=float(max(p[1] for p in box))
        )
        for box, text in zip(result.boxes, result.txts, strict=True)
    ]
    return sorted(lines, key=lambda line: line.top)


def extract_pages(pdf_path: Path, run_ocr: OcrRunner = rapid_ocr_lines) -> list[PageText]:
    """Extract every page; OCR only a page whose text layer is empty (`len(text.strip()) == 0`)."""
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        return [_extract_page(pdf[index], index + 1, run_ocr) for index in range(len(pdf))]
    finally:
        pdf.close()


def _extract_page(page: Any, number: int, run_ocr: OcrRunner) -> PageText:
    try:
        textpage = page.get_textpage()
        text = str(textpage.get_text_range())
        textpage.close()
        if text.strip():
            return PageText(page=number, text=text)
        bitmap = page.render(scale=OCR_RENDER_DPI / 72)
        try:
            image = bitmap.to_numpy()
            if image.ndim == 3 and image.shape[2] == 4:
                image = image[:, :, :3]
            lines = run_ocr(image)
        finally:
            bitmap.close()
        return PageText(page=number, text="", ocr_lines=tuple(lines))
    finally:
        page.close()
