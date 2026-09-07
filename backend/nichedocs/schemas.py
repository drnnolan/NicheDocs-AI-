"""Request and response models for the public API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DocumentStatus = Literal["pending", "processing", "ready", "failed"]


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class Document(BaseModel):
    id: str
    filename: str
    title: str | None = None
    page_count: int = 0
    chunk_count: int = 0
    status: DocumentStatus
    error_message: str | None = None
    uploaded_at: datetime
    processed_at: datetime | None = None


class DocumentList(BaseModel):
    documents: list[Document]


class SignUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    byte_size: int = Field(gt=0, description="Size of the PDF in bytes.")
    title: str | None = Field(default=None, max_length=200)


class SignUploadResponse(BaseModel):
    """Everything the browser needs to PUT the file straight to Supabase.

    The file never passes through this API, which is what keeps us under
    Vercel's 4.5 MB request body ceiling.
    """

    document_id: str
    upload_url: str
    storage_path: str


class ProcessResponse(BaseModel):
    document_id: str
    page_count: int
    chunk_count: int
    status: DocumentStatus


class DeleteResponse(BaseModel):
    document_id: str
    deleted: bool = True


# ---------------------------------------------------------------------------
# Ask
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    document_id: str
    question: str = Field(min_length=3, max_length=2000)


class Source(BaseModel):
    """A retrieved chunk, shown in the UI as a citation."""

    chunk_id: str
    page_number: int
    section: str | None = None
    excerpt: str
    similarity: float
    # True when the model actually leaned on this chunk, as opposed to it merely
    # being retrieved. Lets the UI foreground the chunks that mattered.
    cited: bool = False


class AskResponse(BaseModel):
    answer: str
    # False => the document does not contain the answer. The UI renders this as
    # an explicit "not found in this document" state rather than a normal reply.
    found: bool
    sources: list[Source]
    document_id: str
    question: str
