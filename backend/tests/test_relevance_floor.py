"""Guards the off-topic relevance floor.

The floor is the app's first line of defence: a question unrelated to the
uploaded document is refused on the retrieval score alone, without ever calling
the LLM. A model that is never invoked cannot hallucinate.

The number is easy to get wrong in a specific direction. Cosine similarity from
text-embedding-3-small does NOT span 0-1, so a threshold that *sounds* strict
(0.5, 0.7) silently breaks the app: every question, including good ones, falls
below it and returns "not found". These tests pin the value to the range that
was actually measured against a real 220-page document.
"""

from __future__ import annotations

import pytest

from nichedocs.config import get_settings

# Measured with text-embedding-3-small against a real 220-page book:
#   on-topic questions   -> 0.248, 0.249, 0.291
#   off-topic questions  -> 0.083 ("bake sourdough bread"), 0.153 ("capital of France")
OBSERVED_ON_TOPIC = (0.248, 0.249, 0.291)
OBSERVED_OFF_TOPIC = (0.083, 0.153, 0.177)


@pytest.fixture
def floor(monkeypatch) -> float:
    monkeypatch.delenv("RETRIEVAL_MIN_SIMILARITY", raising=False)
    get_settings.cache_clear()
    value = get_settings().min_similarity
    get_settings.cache_clear()
    return value


def test_floor_admits_real_questions(floor):
    """The critical direction: a floor above ~0.24 refuses legitimate questions."""
    for score in OBSERVED_ON_TOPIC:
        assert score > floor, (
            f"an on-topic question scoring {score} would be refused by a floor of "
            f"{floor}. Cosine scores here top out around 0.3 — raising the floor "
            f"further breaks the app rather than tightening it."
        )


def test_floor_rejects_off_topic_questions(floor):
    for score in OBSERVED_OFF_TOPIC:
        assert score < floor, (
            f"an off-topic question scoring {score} would reach the LLM with a "
            f"floor of {floor}"
        )


def test_floor_sits_inside_the_measured_separation_gap(floor):
    assert max(OBSERVED_OFF_TOPIC) < floor < min(OBSERVED_ON_TOPIC)


def test_floor_is_configurable(monkeypatch):
    monkeypatch.setenv("RETRIEVAL_MIN_SIMILARITY", "0.35")
    get_settings.cache_clear()
    try:
        assert get_settings().min_similarity == pytest.approx(0.35)
    finally:
        get_settings.cache_clear()
