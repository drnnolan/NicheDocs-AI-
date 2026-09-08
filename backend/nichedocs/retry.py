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

# Dropped-connection failures. The cached Supabase client keeps a pooled
# keep-alive socket; Supabase closes its end while the process is idle, and we
# only find out when the next write fails. Retrying alone is not enough — the
# stale client has to be rebuilt first, which is what `reset` below does.
STALE_CONNECTION_MARKERS = (
    "server disconnected",
    "connection reset",
    "connection aborted",
    "remotedisconnected",
    "connection broken",
    "peer closed connection",
    "connectionterminated",
    # httpx raises this when the pooled client itself has been closed, rather
    # than just the socket. Same cause, same cure: rebuild the client.
    "client has been closed",
    "event loop is closed",
)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.5
# Reconnecting is fast and deterministic, unlike waiting out clock skew.
RECONNECT_BACKOFF_SECONDS = 0.4


def _is_stale_connection(exc: Exception) -> bool:
    text = str(exc).lower()
    if any(marker in text for marker in STALE_CONNECTION_MARKERS):
        return True
    # httpx/httpcore surface these as typed errors whose str() is often empty,
    # so fall back to the exception's class name.
    name = type(exc).__name__.lower()
    return name in {"remoteprotocolerror", "connecterror", "readerror", "writeerror"}


def _is_clock_skew(exc: Exception) -> bool:
    text = str(exc).lower()
    if any(code.lower() in text for code in TRANSIENT_CODES):
        return True
    return any(marker in text for marker in TRANSIENT_MARKERS)


def _is_transient(exc: Exception) -> bool:
    return _is_clock_skew(exc) or _is_stale_connection(exc)


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
            if attempt >= MAX_ATTEMPTS:
                break

            if _is_stale_connection(exc):
                # Imported here, not at module scope: clients.py has no reason
                # to know about retries, and a top-level import would make the
                # two modules circular.
                from .clients import reset_supabase

                logger.warning(
                    "Stale connection on %s (attempt %d/%d); rebuilding the Supabase "
                    "client and retrying in %.1fs.",
                    description,
                    attempt,
                    MAX_ATTEMPTS,
                    RECONNECT_BACKOFF_SECONDS,
                )
                reset_supabase()
                time.sleep(RECONNECT_BACKOFF_SECONDS)
            else:
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
