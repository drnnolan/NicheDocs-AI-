"""All Supabase access — Postgres tables, the vector RPC, and Storage.

Keeping every query in one module means the route handlers stay readable and
there is exactly one place to look when the schema changes.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from .chunking import Chunk
from .clients import get_supabase
from .config import get_settings
from .errors import NotFound, UpstreamError

logger = logging.getLogger(__name__)

DOCUMENT_FIELDS = (
    "id, filename, title, page_count, chunk_count, status, error_message, "
    "uploaded_at, processed_at"
)

# Chunks are inserted in batches: one 600-row insert can exceed PostgREST's
# request size limit once 1536-float embeddings are attached.
_CHUNK_INSERT_BATCH = 50


def _now() -> str:
    return datetime.now(UTC).isoformat()


def build_storage_path(document_id: str, filename: str) -> str:
    """Namespace each upload by document id so filenames can safely collide."""
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in filename)[-120:]
    return f"{document_id}/{safe or 'document.pdf'}"


# ---------------------------------------------------------------------------
# documents
# ---------------------------------------------------------------------------


def create_document(*, filename: str, title: str | None, byte_size: int) -> dict[str, Any]:
    """Insert a `pending` document row and return it.

    The row is created *before* the file is uploaded so the browser has a
    document id to attach the upload to, and so an abandoned upload leaves a
    visible `pending` row rather than an orphaned object in Storage.
    """
    document_id = str(uuid.uuid4())
    payload = {
        "id": document_id,
        "filename": filename,
        "title": title or filename.rsplit(".", 1)[0],
        "storage_path": build_storage_path(document_id, filename),
        "byte_size": byte_size,
        "status": "pending",
    }
    try:
        response = get_supabase().table("documents").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001 - supabase-py raises varied types
        logger.exception("Failed to insert document row")
        raise UpstreamError(f"Could not create the document record: {exc}") from exc

    if not response.data:
        raise UpstreamError("Could not create the document record.")
    return response.data[0]


def get_document(document_id: str) -> dict[str, Any]:
    try:
        response = (
            get_supabase()
            .table("documents")
            .select("*")
            .eq("id", document_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to fetch document %s", document_id)
        raise UpstreamError(f"Could not load the document: {exc}") from exc

    if not response.data:
        raise NotFound(f"No document with id {document_id}.")
    return response.data[0]


def list_documents(limit: int = 50) -> list[dict[str, Any]]:
    try:
        response = (
            get_supabase()
            .table("documents")
            .select(DOCUMENT_FIELDS)
            .order("uploaded_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to list documents")
        raise UpstreamError(f"Could not list documents: {exc}") from exc
    return response.data or []


def update_document(document_id: str, **fields: Any) -> dict[str, Any]:
    try:
        response = (
            get_supabase()
            .table("documents")
            .update(fields)
            .eq("id", document_id)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to update document %s", document_id)
        raise UpstreamError(f"Could not update the document: {exc}") from exc

    if not response.data:
        raise NotFound(f"No document with id {document_id}.")
    return response.data[0]


def mark_processing(document_id: str) -> None:
    update_document(document_id, status="processing", error_message=None)


def mark_ready(document_id: str, *, page_count: int, chunk_count: int) -> dict[str, Any]:
    return update_document(
        document_id,
        status="ready",
        page_count=page_count,
        chunk_count=chunk_count,
        error_message=None,
        processed_at=_now(),
    )


def mark_failed(document_id: str, message: str) -> None:
    """Record a processing failure. Never raises — it runs inside except blocks."""
    try:
        update_document(document_id, status="failed", error_message=message[:500])
    except Exception:  # noqa: BLE001
        logger.exception("Could not mark document %s as failed", document_id)


def delete_document(document_id: str) -> None:
    """Remove the document, its chunks (via ON DELETE CASCADE), and its PDF."""
    document = get_document(document_id)
    storage_path = document.get("storage_path")

    if storage_path:
        # Best-effort: a missing object must not block deleting the record,
        # otherwise a failed upload leaves a row the user cannot get rid of.
        try:
            get_supabase().storage.from_(
                get_settings().storage_bucket
            ).remove([storage_path])
        except Exception:  # noqa: BLE001
            logger.warning("Could not remove %s from storage", storage_path, exc_info=True)

    try:
        get_supabase().table("documents").delete().eq("id", document_id).execute()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to delete document %s", document_id)
        raise UpstreamError(f"Could not delete the document: {exc}") from exc


# ---------------------------------------------------------------------------
# chunks
# ---------------------------------------------------------------------------


def replace_chunks(
    document_id: str, chunks: list[Chunk], embeddings: list[list[float]]
) -> int:
    """Delete any existing chunks for the document, then insert the new set.

    Delete-then-insert makes re-processing a document idempotent, which matters
    because the browser can legitimately retry /process after a timeout.
    """
    if len(chunks) != len(embeddings):
        raise UpstreamError("Chunk and embedding counts do not match.")

    client = get_supabase()
    try:
        client.table("chunks").delete().eq("document_id", document_id).execute()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to clear chunks for %s", document_id)
        raise UpstreamError(f"Could not clear previous chunks: {exc}") from exc

    rows = [
        {
            "document_id": document_id,
            "chunk_index": chunk.chunk_index,
            "page_number": chunk.page_number,
            "section": chunk.section,
            "content": chunk.content,
            "token_count": chunk.token_count,
            "embedding": embedding,
        }
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]

    for start in range(0, len(rows), _CHUNK_INSERT_BATCH):
        batch = rows[start : start + _CHUNK_INSERT_BATCH]
        try:
            client.table("chunks").insert(batch).execute()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to insert chunk batch at %d", start)
            raise UpstreamError(f"Could not store document chunks: {exc}") from exc

    return len(rows)


def match_chunks(
    *, document_id: str, query_embedding: list[float], match_count: int, min_similarity: float
) -> list[dict[str, Any]]:
    """Vector similarity search, scoped to one document."""
    try:
        response = get_supabase().rpc(
            "match_chunks",
            {
                "query_embedding": query_embedding,
                "p_document_id": document_id,
                "match_count": match_count,
                "match_threshold": min_similarity,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Vector search failed for document %s", document_id)
        raise UpstreamError(f"Similarity search failed: {exc}") from exc
    return response.data or []


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------


def create_signed_upload_url(storage_path: str) -> str:
    """Mint a short-lived URL the browser can PUT the PDF to directly.

    This is the crux of the upload design: Vercel Functions cap request bodies
    at 4.5 MB, so a 20 MB handbook can never be POSTed to this API. The bytes go
    browser -> Supabase Storage, and only the path comes back to us.
    """
    try:
        result = (
            get_supabase()
            .storage.from_(get_settings().storage_bucket)
            .create_signed_upload_url(storage_path)
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Could not sign an upload URL for %s", storage_path)
        raise UpstreamError(f"Could not prepare the upload: {exc}") from exc

    signed_url = result.get("signed_url") or result.get("signedUrl")
    if not signed_url:
        raise UpstreamError("Storage did not return a signed upload URL.")
    return signed_url


def upload_pdf(storage_path: str, data: bytes) -> None:
    """Server-side upload, used by the small-file /upload convenience route."""
    try:
        get_supabase().storage.from_(get_settings().storage_bucket).upload(
            storage_path,
            data,
            {"content-type": "application/pdf", "upsert": "true"},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Could not upload %s", storage_path)
        raise UpstreamError(f"Could not store the PDF: {exc}") from exc


def download_pdf(storage_path: str) -> bytes:
    """Fetch the PDF back from Storage for processing.

    Outbound, so the 4.5 MB body limit does not apply here.
    """
    try:
        return get_supabase().storage.from_(get_settings().storage_bucket).download(
            storage_path
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Could not download %s", storage_path)
        raise NotFound(
            "The uploaded file could not be found in storage. It may still be "
            "uploading, or the upload failed."
        ) from exc
