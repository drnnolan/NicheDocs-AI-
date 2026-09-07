"""Tests for the chunker.

The invariant that matters most here is page attribution: a chunk's
`page_number` is rendered directly to the user as a citation, so if it drifts,
the app is confidently wrong — the exact failure mode this project exists to
avoid.
"""

from __future__ import annotations

import pytest

from nichedocs.chunking import _is_heading, chunk_pages, estimate_tokens
from nichedocs.pdf import PageText


def _page(number: int, words: int, prefix: str = "word") -> PageText:
    return PageText(page_number=number, text=" ".join(f"{prefix}{i}" for i in range(words)))


def test_returns_nothing_for_empty_input():
    assert chunk_pages([]) == []


def test_single_short_page_becomes_one_chunk():
    pages = [PageText(page_number=1, text="Students must enrol before the census date.")]
    chunks = chunk_pages(pages, target_tokens=600, overlap_tokens=90)

    assert len(chunks) == 1
    assert chunks[0].page_number == 1
    assert chunks[0].chunk_index == 0
    assert "census date" in chunks[0].content


def test_chunk_indices_are_contiguous_from_zero():
    chunks = chunk_pages([_page(1, 4000)], target_tokens=200, overlap_tokens=30)

    assert len(chunks) > 1
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunks_respect_the_token_budget():
    target = 200
    chunks = chunk_pages([_page(1, 4000)], target_tokens=target, overlap_tokens=30)

    # The window stops as soon as it crosses the budget, so a chunk can exceed
    # target by at most one word. Allow generous slack for the merged tail.
    for chunk in chunks[:-1]:
        assert chunk.token_count <= target * 1.3


def test_consecutive_chunks_overlap():
    chunks = chunk_pages([_page(1, 3000)], target_tokens=200, overlap_tokens=60)

    assert len(chunks) >= 2
    first_words = chunks[0].content.split()
    second_words = chunks[1].content.split()
    # The tail of chunk N must reappear at the head of chunk N+1.
    assert set(first_words[-10:]) & set(second_words[:40])


def test_page_numbers_are_non_decreasing_and_real():
    pages = [_page(n, 400, prefix=f"p{n}w") for n in (1, 2, 3)]
    chunks = chunk_pages(pages, target_tokens=150, overlap_tokens=20)

    numbers = [c.page_number for c in chunks]
    assert numbers == sorted(numbers)
    assert set(numbers) <= {1, 2, 3}


def test_chunk_is_cited_to_the_page_where_it_starts():
    pages = [
        PageText(page_number=7, text=" ".join(["alpha"] * 200)),
        PageText(page_number=8, text=" ".join(["beta"] * 200)),
    ]
    chunks = chunk_pages(pages, target_tokens=400, overlap_tokens=40)

    first = chunks[0]
    assert first.page_number == 7
    # It spans the boundary, but the citation points at the start.
    assert "beta" in first.content


def test_headings_are_attached_as_sections():
    pages = [
        PageText(
            page_number=3,
            text=(
                "4.2 Attendance Policy\n"
                "Students are expected to attend at least eighty percent of "
                "scheduled classes in every enrolled unit."
            ),
        )
    ]
    chunks = chunk_pages(pages, target_tokens=600, overlap_tokens=60)

    assert chunks[0].section == "4.2 Attendance Policy"


def test_heading_text_is_kept_in_the_chunk_body():
    pages = [PageText(page_number=1, text="STUDENT CONDUCT\nBe excellent to each other.")]
    chunks = chunk_pages(pages, target_tokens=600, overlap_tokens=60)

    # The heading is often the most topical phrase available to the embedding.
    assert "STUDENT CONDUCT" in chunks[0].content


def test_overlap_must_be_smaller_than_target():
    with pytest.raises(ValueError):
        chunk_pages([_page(1, 100)], target_tokens=100, overlap_tokens=100)


def test_long_document_terminates():
    # Guards the sliding-window loop against the non-advancing case.
    chunks = chunk_pages([_page(1, 20_000)], target_tokens=120, overlap_tokens=110)
    assert len(chunks) > 10


@pytest.mark.parametrize(
    "line",
    [
        "4.2 Attendance Policy",
        "5 Academic Integrity",
        "Section 3: Enrolment",
        "Chapter II Student Rights",
        "Appendix B Fee Schedule",
        "STUDENT CONDUCT",
    ],
)
def test_recognises_headings(line):
    assert _is_heading(line)


@pytest.mark.parametrize(
    "line",
    [
        "",
        "A",
        "PhD",  # single all-caps-ish token
        "Students must attend eighty percent of classes.",
        "the quick brown fox jumps over the lazy dog and keeps on running well past ninety characters in total",
    ],
)
def test_rejects_non_headings(line):
    assert not _is_heading(line)


def test_token_estimate_is_positive_and_monotonic():
    assert estimate_tokens("") == 1
    assert estimate_tokens("hello") >= 1
    assert estimate_tokens("hello world " * 100) > estimate_tokens("hello world")
