"""Lazily-constructed singletons for the two external services we talk to."""

from __future__ import annotations

from functools import lru_cache

from openai import OpenAI
from supabase import Client, create_client

from .config import get_settings


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """Supabase client authenticated with the service role key.

    Built once per warm function instance so we reuse the underlying HTTP
    connection pool instead of paying a TLS handshake per request.
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


@lru_cache(maxsize=1)
def get_openai() -> OpenAI:
    settings = get_settings()
    # Embedding a large handbook is the long pole; the default 10 min timeout is
    # far longer than Vercel's 300s ceiling, so cap it ourselves to fail fast.
    return OpenAI(api_key=settings.openai_api_key, timeout=120.0, max_retries=3)
