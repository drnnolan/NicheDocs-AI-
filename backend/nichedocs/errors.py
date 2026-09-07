"""Domain errors that map onto HTTP status codes."""

from __future__ import annotations


class AppError(Exception):
    """Base class for errors we deliberately surface to the client."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BadRequest(AppError):
    status_code = 400
    code = "bad_request"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class PayloadTooLarge(AppError):
    status_code = 413
    code = "payload_too_large"


class UnprocessableDocument(AppError):
    """The file was accepted but we could not turn it into searchable text."""

    status_code = 422
    code = "unprocessable_document"


class UpstreamError(AppError):
    """OpenAI or Supabase failed in a way we cannot recover from."""

    status_code = 502
    code = "upstream_error"
