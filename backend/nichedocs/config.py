"""Runtime configuration, read once from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# backend/nichedocs/config.py -> backend/.env
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _load_env_file(path: Path = _ENV_FILE) -> None:
    """Load `backend/.env` into os.environ for local development.

    Real environment variables always win, so this is a no-op on Vercel (and
    anywhere else that injects config properly) while making `uvicorn main:app`
    work locally without the caller having to export anything by hand.

    Deliberately hand-rolled rather than pulling in python-dotenv: the format we
    need is `KEY=value` plus comments, and this keeps the deployed bundle free
    of a dependency that only ever runs on a developer laptop.
    """
    if not path.is_file():
        return

    try:
        # utf-8-sig: editors on Windows commonly save .env with a BOM, which
        # would otherwise become part of the first key's name.
        raw = path.read_text(encoding="utf-8-sig")
    except OSError:
        return

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Tolerate quoted values, e.g. KEY="value with spaces".
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


class ConfigError(RuntimeError):
    """Raised at startup when a required environment variable is missing."""


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(
            f"Missing required environment variable {name!r}. "
            "See backend/.env.example for the full list."
        )
    return value


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


def _csv(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    # --- Supabase -----------------------------------------------------------
    supabase_url: str
    # Service role key: bypasses RLS. Server-side only, never sent to the browser.
    supabase_service_key: str
    storage_bucket: str

    # --- OpenAI -------------------------------------------------------------
    openai_api_key: str
    embedding_model: str
    embedding_dimensions: int
    chat_model: str

    # --- Ingestion ----------------------------------------------------------
    max_upload_bytes: int
    max_pages: int
    chunk_target_tokens: int
    chunk_overlap_tokens: int
    embedding_batch_size: int

    # --- Retrieval ----------------------------------------------------------
    top_k: int
    min_similarity: float

    # --- HTTP ---------------------------------------------------------------
    allowed_origins: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Build (and memoise) settings from the environment.

    Cached because Vercel reuses a warm function instance across requests and
    there is no reason to re-read os.environ every time.
    """
    _load_env_file()
    return Settings(
        supabase_url=_required("SUPABASE_URL").rstrip("/"),
        supabase_service_key=_required("SUPABASE_SERVICE_ROLE_KEY"),
        storage_bucket=os.environ.get("SUPABASE_STORAGE_BUCKET", "documents").strip(),
        openai_api_key=_required("OPENAI_API_KEY"),
        embedding_model=os.environ.get(
            "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
        ).strip(),
        # Must match the vector(N) column width in the migration.
        embedding_dimensions=_int("OPENAI_EMBEDDING_DIMENSIONS", 1536),
        chat_model=os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini").strip(),
        max_upload_bytes=_int("MAX_UPLOAD_BYTES", 20 * 1024 * 1024),
        max_pages=_int("MAX_PAGES", 500),
        chunk_target_tokens=_int("CHUNK_TARGET_TOKENS", 600),
        chunk_overlap_tokens=_int("CHUNK_OVERLAP_TOKENS", 90),
        # OpenAI's embeddings endpoint accepts an array of inputs; batching turns
        # ~600 round trips into ~6 for a large handbook.
        embedding_batch_size=_int("EMBEDDING_BATCH_SIZE", 96),
        top_k=_int("RETRIEVAL_TOP_K", 5),
        min_similarity=_float("RETRIEVAL_MIN_SIMILARITY", 0.20),
        allowed_origins=_csv("ALLOWED_ORIGINS", ["http://localhost:3000"]),
    )
