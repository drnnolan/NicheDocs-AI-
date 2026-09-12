"""Tests for the database boundary helpers."""

from __future__ import annotations

from nichedocs.store import _pg_safe, build_storage_path


def test_strips_null_bytes():
    assert _pg_safe("before\x00after") == "beforeafter"


def test_passes_clean_text_through_unchanged():
    assert _pg_safe("4.2 Attendance Policy") == "4.2 Attendance Policy"


def test_preserves_none_for_nullable_columns():
    # `section` is nullable; turning None into "" would lose that distinction.
    assert _pg_safe(None) is None


def test_handles_a_string_that_is_only_nulls():
    assert _pg_safe("\x00\x00") == ""


def test_keeps_non_ascii_text():
    """Stripping NUL must not touch legitimate Unicode."""
    assert _pg_safe("sixty (60) days — “the Licensee”") == "sixty (60) days — “the Licensee”"


def test_storage_path_is_namespaced_by_document_id():
    path = build_storage_path("abc-123", "My Contract.pdf")
    assert path.startswith("abc-123/")
    assert path.endswith(".pdf")


def test_storage_path_sanitises_awkward_filenames():
    path = build_storage_path("abc-123", "wéird name/../file.pdf")
    assert "/" not in path.split("/", 1)[1], "filename segment must not contain slashes"
