"""PDF text extraction.

Deliberately uses `pypdf` (pure Python, no native wheels) rather than
`pdfplumber`. pdfplumber pulls in Pillow and does per-glyph layout analysis,
which we do not need for prose handbooks and which inflates the serverless
bundle. See docs/CASE_STUDY.md for the full trade-off.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .errors import UnprocessableDocument

# Collapse runs of whitespace, but keep newlines: heading detection in
# chunking.py works line by line.
_HORIZONTAL_WS = re.compile(r"[^\S\n]+")
_BLANK_LINES = re.compile(r"\n{3,}")
# pypdf sometimes emits soft hyphens and ligature artefacts.
_SOFT_HYPHEN = re.compile(r"­")
# "informa-\ntion" -> "information"
_HYPHEN_LINEBREAK = re.compile(r"(\w)-\n(\w)")


@dataclass(frozen=True)
class PageText:
    page_number: int  # 1-based, matches what the reader sees in a PDF viewer
    text: str


@dataclass(frozen=True)
class ExtractedDocument:
    # Every page in the file, including image-only ones we could not read. This
    # is the number we report to the user, because it is the number they see in
    # their PDF viewer.
    total_pages: int
    # Only the pages that yielded text.
    pages: list[PageText]


def _clean(raw: str) -> str:
    text = _SOFT_HYPHEN.sub("", raw)
    text = _HYPHEN_LINEBREAK.sub(r"\1\2", text)
    text = _HORIZONTAL_WS.sub(" ", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def extract_pages(data: bytes, *, max_pages: int) -> ExtractedDocument:
    """Extract per-page text from a PDF.

    Pages that yield no text (scans, full-page images) are dropped rather than
    stored as empty chunks. If *every* page is empty the document is almost
    certainly a scan, and we fail loudly instead of silently indexing nothing.
    """
    try:
        reader = PdfReader(io.BytesIO(data))
    except (PdfReadError, ValueError, OSError) as exc:
        raise UnprocessableDocument(f"Could not read this PDF: {exc}") from exc

    if reader.is_encrypted:
        # Many handbooks are "encrypted" only with an empty owner password,
        # which pypdf can open transparently.
        try:
            if reader.decrypt("") == 0:
                raise UnprocessableDocument(
                    "This PDF is password-protected. Remove the password and re-upload."
                )
        except (NotImplementedError, PdfReadError) as exc:
            raise UnprocessableDocument(
                f"This PDF uses an unsupported encryption scheme: {exc}"
            ) from exc

    total_pages = len(reader.pages)
    if total_pages == 0:
        raise UnprocessableDocument("This PDF has no pages.")
    if total_pages > max_pages:
        raise UnprocessableDocument(
            f"This PDF has {total_pages} pages, which is over the {max_pages}-page "
            "limit for a single document."
        )

    pages: list[PageText] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            raw = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - one bad page must not sink the upload
            raw = ""
        cleaned = _clean(raw)
        if cleaned:
            pages.append(PageText(page_number=index, text=cleaned))

    if not pages:
        raise UnprocessableDocument(
            "No selectable text found in this PDF. It looks like a scanned "
            "document — NicheDocs does not run OCR."
        )

    return ExtractedDocument(total_pages=total_pages, pages=pages)
