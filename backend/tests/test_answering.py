"""Tests for prompt building and answer parsing.

These cover the grounding guarantees (FR4/FR5) without touching the network:
a hallucinated citation index must be dropped, and a "not found" verdict must
survive parsing intact.
"""

from __future__ import annotations

import json

from nichedocs.answering import NOT_FOUND_ANSWER, _parse, build_context

MATCHES = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "page_number": 12,
        "section": "4.2 Attendance Policy",
        "content": "Students must attend at least 80% of scheduled classes.",
        "similarity": 0.71,
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "page_number": 13,
        "section": None,
        "content": "Absences may be excused with documentation.",
        "similarity": 0.55,
    },
]


def test_context_numbers_excerpts_from_one():
    context = build_context(MATCHES)
    assert context.startswith("[1] (page 12, section “4.2 Attendance Policy”)")
    assert "[2] (page 13)" in context


def test_context_omits_section_label_when_absent():
    context = build_context(MATCHES)
    assert "section “None”" not in context


def test_context_truncates_very_long_excerpts():
    long_match = [{"page_number": 1, "section": None, "content": "x" * 10_000}]
    context = build_context(long_match)
    assert len(context) < 3_000
    assert context.rstrip().endswith("…")


def test_parses_a_grounded_answer():
    raw = json.dumps(
        {"found": True, "answer": "You must attend 80% of classes.", "citations": [1]}
    )
    result = _parse(raw, excerpt_count=2)

    assert result.found is True
    assert result.answer == "You must attend 80% of classes."
    assert result.cited_indices == {1}


def test_parses_a_not_found_answer():
    raw = json.dumps(
        {"found": False, "answer": "The handbook does not cover parking.", "citations": []}
    )
    result = _parse(raw, excerpt_count=2)

    assert result.found is False
    assert result.cited_indices == set()
    assert "does not cover" in result.answer


def test_drops_citation_indices_outside_the_supplied_range():
    # The model claiming excerpt [9] when it was given two is a hallucination;
    # surfacing it would render a citation that points at nothing.
    raw = json.dumps({"found": True, "answer": "Yes.", "citations": [1, 9, 0, -3]})
    result = _parse(raw, excerpt_count=2)

    assert result.cited_indices == {1}


def test_ignores_non_integer_citations():
    raw = json.dumps({"found": True, "answer": "Yes.", "citations": ["1", None, "abc"]})
    result = _parse(raw, excerpt_count=2)

    assert result.cited_indices == {1}


def test_found_is_false_when_the_answer_is_empty():
    raw = json.dumps({"found": True, "answer": "   ", "citations": [1]})
    result = _parse(raw, excerpt_count=2)

    assert result.found is False
    assert result.answer == NOT_FOUND_ANSWER


def test_falls_back_gracefully_on_malformed_json():
    result = _parse("I am not JSON at all.", excerpt_count=2)

    assert result.answer == "I am not JSON at all."
    assert result.cited_indices == set()


def test_handles_json_that_is_not_an_object():
    result = _parse("[1, 2, 3]", excerpt_count=2)

    assert result.found is False
    assert result.answer == NOT_FOUND_ANSWER
