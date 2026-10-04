"""Structural chunking (D-22): one chunk per numbered section or scan paragraph, title prefixed.

Sizes come from the documents (35-74 bge tokens per section), not from a tutorial window; a body
over CHUNK_OVERSIZE_LIMIT bge tokens is split into sentences and packed evenly (never triggered
on this corpus). Overlap is 0: each section is a self-contained rule.
"""

import math
import re
import statistics
from collections.abc import Sequence
from functools import cache
from itertools import pairwise
from typing import Any

from app.domain.constants import CHUNK_OVERSIZE_LIMIT, CHUNK_TOKENIZER_MODEL, PARAGRAPH_GAP_FACTOR
from app.ingestion.extractor import OcrLine, PageText

HEADING = re.compile(r"^\d+\.\s+[A-Z]")  # "number, dot, capital": wrapped lines start with digits
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def segment_text_layer(text: str) -> tuple[str, list[str]]:
    """Return (title, sections): the first line is the title; each section is its heading,
    a newline, and its wrapped lines joined with spaces."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "", []
    groups: list[list[str]] = []
    for line in lines[1:]:
        if HEADING.match(line) or not groups:
            groups.append([line])
        else:
            groups[-1].append(line)
    return lines[0], [f"{group[0]}\n{' '.join(group[1:])}".rstrip() for group in groups]


def group_scan_lines(
    lines: Sequence[OcrLine], gap_factor: float = PARAGRAPH_GAP_FACTOR
) -> tuple[str, list[str]]:
    """Return (title, paragraphs): the top-most line is the title; a vertical gap larger than
    gap_factor x the median line gap starts a new paragraph (E02: 2.9-3.9x vs 0.7-1.4x)."""
    ordered = sorted(lines, key=lambda line: line.top)
    if not ordered:
        return "", []
    gaps = [below.top - above.bottom for above, below in pairwise(ordered)]
    threshold = gap_factor * statistics.median(gaps) if gaps else 0.0
    groups: list[list[str]] = [[ordered[0].text]]
    for gap, line in zip(gaps, ordered[1:], strict=True):
        if gap > threshold:
            groups.append([line.text])
        else:
            groups[-1].append(line.text)
    groups[0] = groups[0][1:]  # the title line itself is not body text
    return ordered[0].text, [" ".join(group) for group in groups if group]


def split_sentences(body: str) -> list[str]:
    return [sentence for sentence in SENTENCE_BREAK.split(body) if sentence]


def pack_evenly(sentences: list[str], parts: int) -> list[str]:
    """Group consecutive sentences into `parts` chunks of near-equal sentence counts."""
    parts = max(1, min(parts, len(sentences)))
    size, extra = divmod(len(sentences), parts)
    packed: list[str] = []
    start = 0
    for index in range(parts):
        end = start + size + (1 if index < extra else 0)
        packed.append(" ".join(sentences[start:end]))
        start = end
    return packed


@cache
def _tokenizer() -> Any:
    from transformers import AutoTokenizer  # the embedding model's own tokenizer (D-70)

    return AutoTokenizer.from_pretrained(CHUNK_TOKENIZER_MODEL)


def bge_token_count(text: str) -> int:
    return len(_tokenizer()(text, add_special_tokens=False)["input_ids"])


def fit_to_limit(body: str, limit: int = CHUNK_OVERSIZE_LIMIT) -> list[str]:
    """Keep a body whole, or split it into ceil(tokens / limit) evenly packed parts."""
    tokens = bge_token_count(body)
    if tokens <= limit:
        return [body]
    return pack_evenly(split_sentences(body), math.ceil(tokens / limit))


def chunk_page(page: PageText) -> list[str]:
    """Chunk texts for one page, each `"{title}\\n\\n{section or paragraph}"`."""
    if page.ocr_lines:
        title, bodies = group_scan_lines(page.ocr_lines)
    else:
        title, bodies = segment_text_layer(page.text)
    return [f"{title}\n\n{part}" for body in bodies for part in _fit_section(body)]


def _fit_section(section: str) -> list[str]:
    heading, _, text = section.partition("\n")
    if not text:  # a scan paragraph has no heading line
        return fit_to_limit(section)
    return [f"{heading}\n{part}" for part in fit_to_limit(text)]
