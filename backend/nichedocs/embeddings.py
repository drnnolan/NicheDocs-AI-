"""Embedding generation."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from openai import OpenAIError

from .clients import get_openai
from .config import get_settings
from .errors import UpstreamError

logger = logging.getLogger(__name__)


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """Embed many texts, batched.

    The embeddings endpoint accepts an array of inputs, so a 600-chunk handbook
    costs ~7 HTTP round trips instead of 600. That difference is what keeps
    ingestion inside Vercel's 300s function ceiling.

    Returns vectors in the same order as `texts`.
    """
    if not texts:
        return []

    settings = get_settings()
    client = get_openai()
    vectors: list[list[float]] = []

    for start in range(0, len(texts), settings.embedding_batch_size):
        batch = list(texts[start : start + settings.embedding_batch_size])
        try:
            response = client.embeddings.create(
                model=settings.embedding_model,
                input=batch,
                dimensions=settings.embedding_dimensions,
            )
        except OpenAIError as exc:
            logger.exception("Embedding batch starting at %d failed", start)
            raise UpstreamError(f"Embedding request failed: {exc}") from exc

        # The API documents that it preserves input order, but it also returns
        # an explicit index. Sort by it rather than trusting the ordering.
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors.extend(item.embedding for item in ordered)

    if len(vectors) != len(texts):
        raise UpstreamError(
            f"Expected {len(texts)} embeddings but received {len(vectors)}."
        )
    return vectors


def embed_query(text: str) -> list[float]:
    """Embed a single user question."""
    return embed_texts([text])[0]
