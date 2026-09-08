"""Retry helper for transient Supabase failures.

Exists for one specific, real failure: PostgREST rejects a request with
PGRST303 ("JWT issued at future") when the token's issued-at timestamp is ahead
of Supabase's own clock. A few seconds of drift between a developer laptop (or a
serverless host) and Supabase's servers is enough to trigger it.

It is genuinely transient — the same request succeeds moments later, once wall
clocks line up again — so retrying is the correct response rather than
surfacing a cryptic error to the user. The alternative, telling people to fix
their system clock, does not work on hosts whose clock you do not control.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)

# PostgREST codes worth a second attempt. Deliberately narrow: retrying a
# genuine authorisation failure or a constraint violation would just add
# latency to an error the caller still has to handle.
TRANSIENT_CODES = ("PGRST303",)
TRANSIENT_MARKERS = ("jwt issued at future", "issued at future")

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.5


def _is_transient(exc: Exception) -> bool:
    text = str(exc).lower()
    if any(code.lower() in text for code in TRANSIENT_CODES):
        return True
    return any(marker in text for marker in TRANSIENT_MARKERS)


def with_retry[T](operation: Callable[[], T], *, description: str = "request") -> T:
    """Run `operation`, retrying briefly on transient clock-skew failures.

    Non-transient exceptions propagate immediately and untouched.
    """
    last: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return operation()
        except Exception as exc:  # noqa: BLE001 - re-raised below unless transient
            if not _is_transient(exc):
                raise
            last = exc
            if attempt < MAX_ATTEMPTS:
                logger.warning(
                    "Transient clock-skew error on %s (attempt %d/%d); retrying in %.1fs. "
                    "This usually means the system clock differs from Supabase's.",
                    description,
                    attempt,
                    MAX_ATTEMPTS,
                    BACKOFF_SECONDS,
                )
                # Sleeping lets the clocks converge. The waits are short enough
                # to stay well inside any request timeout.
                time.sleep(BACKOFF_SECONDS)

    assert last is not None  # only reachable after a transient failure
    raise last
