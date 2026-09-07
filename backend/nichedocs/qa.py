"""Question answering: retrieve, ground, cite."""

from __future__ import annotations

import logging

from . import store
from .answering import NOT_FOUND_ANSWER, generate_answer
from .config import get_settings
from .embeddings import embed_query
from .errors import BadRequest
from .schemas import AskResponse, Source

logger = logging.getLogger(__name__)

# Length of the excerpt shown under a citation in the UI. Long enough to see
# the sentence the answer came from, short enough not to dominate the chat.
EXCERPT_CHARS = 320


def _excerpt(content: str) -> str:
    text = " ".join(content.split())
    if len(text) <= EXCERPT_CHARS:
        return text
    return text[:EXCERPT_CHARS].rsplit(" ", 1)[0] + "…"


def answer_question(*, document_id: str, question: str) -> AskResponse:
    document = store.get_document(document_id)
    status = document.get("status")

    if status != "ready":
        if status == "failed":
            raise BadRequest(
                document.get("error_message")
                or "This document failed to process, so it cannot be queried."
            )
        raise BadRequest(
            "This document is still being processed. Wait for it to finish, then ask again."
        )

    settings = get_settings()
    matches = store.match_chunks(
        document_id=document_id,
        query_embedding=embed_query(question),
        match_count=settings.top_k,
        min_similarity=settings.min_similarity,
    )

    if not matches:
        # Nothing in the document was even loosely related. Answer without
        # calling the LLM: it is faster, cheaper, and cannot hallucinate.
        logger.info("No chunks above threshold for document %s", document_id)
        return AskResponse(
            answer=NOT_FOUND_ANSWER,
            found=False,
            sources=[],
            document_id=document_id,
            question=question,
        )

    grounded = generate_answer(question=question, matches=matches)

    sources = [
        Source(
            chunk_id=str(match.get("id")),
            page_number=int(match.get("page_number") or 0),
            section=match.get("section"),
            excerpt=_excerpt(match.get("content") or ""),
            similarity=round(float(match.get("similarity") or 0.0), 4),
            cited=position in grounded.cited_indices,
        )
        for position, match in enumerate(matches, start=1)
    ]

    # When the model answered but named no excerpts, the citations are still
    # the retrieved set — mark them all so the UI never shows an uncited answer.
    if grounded.found and not grounded.cited_indices:
        logger.info("Model returned an answer with no citations; showing all matches")
        sources = [source.model_copy(update={"cited": True}) for source in sources]

    # A "not found" reply cites nothing, but we still return the near-misses so
    # the user can see what the search actually turned up.
    return AskResponse(
        answer=grounded.answer,
        found=grounded.found,
        sources=sources,
        document_id=document_id,
        question=question,
    )
