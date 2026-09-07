"""End-to-end tests for extraction, against real PDF bytes.

These build a minimal but genuinely valid PDF in-memory rather than committing
a binary fixture, so the tests stay readable and the repo stays text-only.
"""

from __future__ import annotations

import pytest

from nichedocs.chunking import chunk_pages
from nichedocs.errors import UnprocessableDocument
from nichedocs.pdf import extract_pages


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def build_pdf(pages: list[list[str]]) -> bytes:
    """Assemble a valid uncompressed PDF whose pages contain `pages[i]` lines."""
    page_count = len(pages)
    first_page_obj = 3
    first_stream_obj = first_page_obj + page_count
    font_obj = first_stream_obj + page_count

    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: (
            "<< /Type /Pages /Count {count} /Kids [{kids}] >>".format(
                count=page_count,
                kids=" ".join(f"{first_page_obj + i} 0 R" for i in range(page_count)),
            ).encode()
        ),
        font_obj: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }

    for index, lines in enumerate(pages):
        objects[first_page_obj + index] = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {first_stream_obj + index} 0 R /Resources << /Font << /F1 {font_obj} 0 R >> >> >>".encode()
        )

        body_parts = ["BT", "/F1 12 Tf", "14 TL", "72 720 Td"]
        for line_index, line in enumerate(lines):
            if line_index:
                body_parts.append("T*")
            body_parts.append(f"({_escape(line)}) Tj")
        body_parts.append("ET")
        stream = "\n".join(body_parts).encode()
        objects[first_stream_obj + index] = (
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )

    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += f"{number} 0 obj\n".encode() + objects[number] + b"\nendobj\n"

    xref_offset = len(out)
    max_obj = max(objects)
    out += f"xref\n0 {max_obj + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for number in range(1, max_obj + 1):
        out += f"{offsets[number]:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {max_obj + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    ).encode()

    return bytes(out)


def test_extracts_text_from_a_real_pdf():
    pdf = build_pdf([["Hello handbook", "Second line of page one"]])
    result = extract_pages(pdf, max_pages=100)

    assert result.total_pages == 1
    assert len(result.pages) == 1
    assert "Hello handbook" in result.pages[0].text
    assert result.pages[0].page_number == 1


def test_page_numbers_are_one_based_and_ordered():
    pdf = build_pdf([["Page one text"], ["Page two text"], ["Page three text"]])
    result = extract_pages(pdf, max_pages=100)

    assert [page.page_number for page in result.pages] == [1, 2, 3]
    assert "two" in result.pages[1].text


def test_reports_total_pages_including_empty_ones():
    # Middle page has no text: it is skipped for indexing, but the user-facing
    # page count must still match what their PDF viewer shows.
    pdf = build_pdf([["First"], [], ["Third"]])
    result = extract_pages(pdf, max_pages=100)

    assert result.total_pages == 3
    assert [page.page_number for page in result.pages] == [1, 3]


def test_rejects_a_pdf_with_no_extractable_text():
    pdf = build_pdf([[], []])
    with pytest.raises(UnprocessableDocument, match="No selectable text"):
        extract_pages(pdf, max_pages=100)


def test_rejects_a_document_over_the_page_limit():
    pdf = build_pdf([["a"], ["b"], ["c"]])
    with pytest.raises(UnprocessableDocument, match="over the 2-page limit"):
        extract_pages(pdf, max_pages=2)


def test_rejects_bytes_that_are_not_a_pdf():
    with pytest.raises(UnprocessableDocument):
        extract_pages(b"this is definitely not a pdf", max_pages=100)


# Each page is filled with a marker word unique to that page, so a chunk's true
# origin can be recovered from its text and checked against its citation.
_PAGE_MARKERS = {1: "alpha", 2: "bravo", 3: "charlie"}


def test_full_pipeline_cites_the_page_a_passage_starts_on():
    """The invariant the whole product rests on: the citation must be the truth.

    A chunk is cited to the page its text begins on, even when it runs over a
    page boundary. If this drifts, the app becomes confidently wrong.
    """
    pdf = build_pdf(
        [
            [f"PAGE {number} SECTION", " ".join([marker] * 60)]
            for number, marker in _PAGE_MARKERS.items()
        ]
    )
    result = extract_pages(pdf, max_pages=100)
    chunks = chunk_pages(result.pages, target_tokens=60, overlap_tokens=8)

    assert len(chunks) > 3, "expected the document to split into several chunks"

    for chunk in chunks:
        first_word = chunk.content.split()[0]
        # Chunks starting mid-page begin with that page's marker word; chunks
        # starting at a heading begin with "PAGE".
        if first_word in {"alpha", "bravo", "charlie"}:
            expected = next(n for n, m in _PAGE_MARKERS.items() if m == first_word)
            assert chunk.page_number == expected, (
                f"chunk starting with {first_word!r} was cited to page "
                f"{chunk.page_number}, expected {expected}"
            )

    # Page 3's content must be reachable, and cited no earlier than page 2 —
    # a chunk starting on page 1 is far too short to reach page 3.
    charlie_chunks = [c for c in chunks if "charlie" in c.content]
    assert charlie_chunks
    assert min(c.page_number for c in charlie_chunks) >= 2
    assert any(c.page_number == 3 for c in charlie_chunks)


def test_headings_survive_the_full_pipeline():
    pdf = build_pdf(
        [
            ["4.2 Attendance Policy", " ".join(["attendance"] * 60)],
        ]
    )
    result = extract_pages(pdf, max_pages=100)
    chunks = chunk_pages(result.pages, target_tokens=60, overlap_tokens=8)

    assert all(chunk.section == "4.2 Attendance Policy" for chunk in chunks)


def test_tail_merge_does_not_duplicate_overlapping_text():
    """Folding a short tail into the previous chunk must not repeat the overlap."""
    pdf = build_pdf([["ZULU SECTION", " ".join(f"w{i}" for i in range(70))]])
    result = extract_pages(pdf, max_pages=100)
    chunks = chunk_pages(result.pages, target_tokens=40, overlap_tokens=10)

    for chunk in chunks:
        words = [w for w in chunk.content.split() if w.startswith("w")]
        assert len(words) == len(set(words)), f"duplicated words in: {chunk.content}"
