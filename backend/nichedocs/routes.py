"""HTTP routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, UploadFile

from . import ingest, qa, store
from .config import get_settings
from .errors import BadRequest, PayloadTooLarge
from .schemas import (
    AskRequest,
    AskResponse,
    DeleteResponse,
    Document,
    DocumentList,
    ProcessResponse,
    SignUploadRequest,
    SignUploadResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Vercel Functions reject request bodies over 4.5 MB before our code runs, so
# the direct-upload route is capped below that. Larger files must go through
# the signed-URL flow.
DIRECT_UPLOAD_LIMIT = 4 * 1024 * 1024


def _validate_pdf(filename: str, byte_size: int) -> None:
    if not filename.lower().endswith(".pdf"):
        raise BadRequest("Only PDF files are supported.")
    if byte_size <= 0:
        raise BadRequest("The file appears to be empty.")

    limit = get_settings().max_upload_bytes
    if byte_size > limit:
        raise PayloadTooLarge(
            f"This file is {byte_size / 1_048_576:.1f} MB, over the "
            f"{limit / 1_048_576:.0f} MB limit."
        )


@router.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


@router.post("/upload/sign", response_model=SignUploadResponse, tags=["documents"])
def sign_upload(payload: SignUploadRequest) -> SignUploadResponse:
    """Step 1 of 3: reserve a document and mint a signed Storage upload URL.

    The browser then PUTs the PDF straight to Supabase (step 2) and calls
    /documents/{id}/process (step 3). The bytes never traverse this API.
    """
    _validate_pdf(payload.filename, payload.byte_size)

    document = store.create_document(
        filename=payload.filename,
        title=payload.title,
        byte_size=payload.byte_size,
    )
    upload_url = store.create_signed_upload_url(document["storage_path"])

    return SignUploadResponse(
        document_id=document["id"],
        upload_url=upload_url,
        storage_path=document["storage_path"],
    )


@router.post("/documents/{document_id}/process", response_model=ProcessResponse, tags=["documents"])
def process(document_id: str) -> ProcessResponse:
    """Step 3 of 3: extract, chunk, embed, and index the uploaded PDF."""
    document = ingest.process_document(document_id)
    return ProcessResponse(
        document_id=document["id"],
        page_count=document.get("page_count") or 0,
        chunk_count=document.get("chunk_count") or 0,
        status=document.get("status") or "ready",
    )


@router.post("/upload", response_model=ProcessResponse, tags=["documents"])
def upload(
    file: UploadFile = File(..., description="PDF, up to 4 MB on this route."),
    title: str | None = Form(default=None),
) -> ProcessResponse:
    """Single-call upload: store the PDF and index it in one request.

    Convenience route for local development, curl, and the API docs. Capped at
    4 MB because Vercel rejects larger bodies at the platform edge — the web UI
    uses the signed-URL flow above instead, which has no such ceiling.
    """
    data = file.file.read()
    filename = file.filename or "document.pdf"
    _validate_pdf(filename, len(data))

    if len(data) > DIRECT_UPLOAD_LIMIT:
        raise PayloadTooLarge(
            f"This route accepts files up to {DIRECT_UPLOAD_LIMIT / 1_048_576:.0f} MB. "
            "Use POST /upload/sign for larger documents."
        )

    document = store.create_document(
        filename=filename, title=title, byte_size=len(data)
    )
    store.upload_pdf(document["storage_path"], data)
    processed = ingest.process_document(document["id"])

    return ProcessResponse(
        document_id=processed["id"],
        page_count=processed.get("page_count") or 0,
        chunk_count=processed.get("chunk_count") or 0,
        status=processed.get("status") or "ready",
    )


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@router.get("/documents", response_model=DocumentList, tags=["documents"])
def get_documents() -> DocumentList:
    return DocumentList(
        documents=[Document(**row) for row in store.list_documents()]
    )


@router.get("/documents/{document_id}", response_model=Document, tags=["documents"])
def get_one_document(document_id: str) -> Document:
    row = store.get_document(document_id)
    return Document(**{key: row[key] for key in Document.model_fields if key in row})


@router.delete("/documents/{document_id}", response_model=DeleteResponse, tags=["documents"])
def remove_document(document_id: str) -> DeleteResponse:
    store.delete_document(document_id)
    return DeleteResponse(document_id=document_id)


# ---------------------------------------------------------------------------
# Ask
# ---------------------------------------------------------------------------


@router.post("/ask", response_model=AskResponse, tags=["ask"])
def ask(payload: AskRequest) -> AskResponse:
    return qa.answer_question(
        document_id=payload.document_id, question=payload.question
    )
