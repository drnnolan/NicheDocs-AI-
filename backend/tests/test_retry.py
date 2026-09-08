"""Tests for transient-failure retries.

Regression cover for an intermittent production bug: Supabase rejected requests
with PGRST303 "JWT issued at future" whenever the caller's clock sat a few
seconds behind Supabase's. The same request succeeded moments later, so the
failure appeared and vanished at random.
"""

from __future__ import annotations

import pytest

from nichedocs import retry
from nichedocs.retry import with_retry


@pytest.fixture(autouse=True)
def _no_sleeping(monkeypatch):
    """Keep the suite fast — the backoff duration is not what we're testing."""
    monkeypatch.setattr(retry.time, "sleep", lambda _seconds: None)


def test_returns_the_value_when_the_call_succeeds():
    assert with_retry(lambda: "ok") == "ok"


def test_does_not_retry_a_successful_call():
    calls = []

    def operation():
        calls.append(1)
        return "done"

    with_retry(operation)
    assert len(calls) == 1


def test_retries_and_recovers_from_a_clock_skew_error():
    attempts = []

    def operation():
        attempts.append(1)
        if len(attempts) < 2:
            raise RuntimeError(
                "{'message': 'JWT issued at future', 'code': 'PGRST303'}"
            )
        return "recovered"

    assert with_retry(operation) == "recovered"
    assert len(attempts) == 2


def test_matches_on_the_pgrst303_code():
    attempts = []

    def operation():
        attempts.append(1)
        if len(attempts) < 2:
            raise RuntimeError("PGRST303 something odd")
        return "ok"

    assert with_retry(operation) == "ok"


def test_gives_up_after_max_attempts_and_reraises():
    attempts = []

    def operation():
        attempts.append(1)
        raise RuntimeError("PGRST303: JWT issued at future")

    with pytest.raises(RuntimeError, match="issued at future"):
        with_retry(operation)

    assert len(attempts) == retry.MAX_ATTEMPTS


def test_does_not_retry_unrelated_errors():
    """A real failure must surface immediately, not after three slow attempts."""
    attempts = []

    def operation():
        attempts.append(1)
        raise ValueError("duplicate key violates unique constraint")

    with pytest.raises(ValueError, match="duplicate key"):
        with_retry(operation)

    assert len(attempts) == 1, "a non-transient error must not be retried"


def test_does_not_retry_an_authorisation_failure():
    attempts = []

    def operation():
        attempts.append(1)
        raise RuntimeError("401 Unauthorized: invalid API key")

    with pytest.raises(RuntimeError):
        with_retry(operation)

    assert len(attempts) == 1
