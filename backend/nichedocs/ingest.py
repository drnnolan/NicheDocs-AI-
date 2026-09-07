"""The ingestion pipeline: stored PDF -> searchable, page-attributed chunks."""

from __future__ import annotations

import logging
from typing import Any

from . import store
from .chunking import chunk_pages
from .config import get_settings
from .embeddings import embed_texts
from .errors import AppError, PayloadTooLarge, UnprocessableDocument
from .pdf import extract_pages

logger = logging.getLogger(__name__)


def process_document(document_id: str) -> dict[str, Any]:
    """Extract, chunk, embed, and index an already-uploaded PDF.

    Idempotent: re-running replaces the document's chunks rather than
    duplicating them, so the client is free to retry.
    """
    document = store.get_document(document_id)
    settings = get_settings()

    store.mark_processing(document_id)
    try:
        data = store.download_pdf(document["storage_path"])

        if len(data) > settings.max_upload_bytes:
            raise PayloadTooLarge(
                f"This file is {len(data) / 1_048_576:.1f} MB, over the "
                f"{settings.max_upload_bytes / 1_048_576:.0f} MB limit."
            )

        extracted = extract_pages(data, max_pages=settings.max_pages)
        chunks = chunk_pages(
            extracted.pages,
            target_tokens=settings.chunk_target_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
        )
        if not chunks:
            raise UnprocessableDocument(
                "This PDF produced no readable text to index."
            )

        logger.info(
            "Embedding %d chunks from %d pages for document %s",
            len(chunks),
            extracted.total_pages,
            document_id,
        )
        embeddings = embed_texts([chunk.content for chunk in chunks])
        chunk_count = store.replace_chunks(document_id, chunks, embeddings)

        updated = store.mark_ready(
            document_id,
            page_count=extracted.total_pages,
            chunk_count=chunk_count,
        )
    except AppError as exc:
        # Expected failure (bad PDF, upstream hiccup): record why, so the UI can
        # show the user something actionable instead of a generic error.
        store.mark_failed(document_id, exc.message)
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected failure processing document %s", document_id)
        store.mark_failed(document_id, "Unexpected error while processing this file.")
        raise UnprocessableDocument(f"Could not process this document: {exc}") from exc

    return updated
