"""Tests for environment loading.

Regression cover for a real bug: nothing read `backend/.env`, so `uvicorn
main:app` started with no configuration at all and every request failed with a
502. It worked on Vercel (which injects env vars) which is exactly why it went
unnoticed.
"""

from __future__ import annotations

from nichedocs.config import _load_env_file


def test_loads_key_values_from_a_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("SUPABASE_URL=https://example.supabase.co\nOPENAI_API_KEY=sk-test\n")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    _load_env_file(env)

    import os

    assert os.environ["SUPABASE_URL"] == "https://example.supabase.co"
    assert os.environ["OPENAI_API_KEY"] == "sk-test"


def test_real_environment_variables_win(tmp_path, monkeypatch):
    """Vercel sets real env vars; a stray .env in the bundle must not override them."""
    env = tmp_path / ".env"
    env.write_text("SUPABASE_URL=https://from-file.supabase.co\n")
    monkeypatch.setenv("SUPABASE_URL", "https://from-real-env.supabase.co")

    _load_env_file(env)

    import os

    assert os.environ["SUPABASE_URL"] == "https://from-real-env.supabase.co"


def test_ignores_comments_and_blank_lines(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# a comment\n\n  \nNICHEDOCS_TEST_A=1\n# another\nNICHEDOCS_TEST_B=2\n")
    monkeypatch.delenv("NICHEDOCS_TEST_A", raising=False)
    monkeypatch.delenv("NICHEDOCS_TEST_B", raising=False)

    _load_env_file(env)

    import os

    assert os.environ["NICHEDOCS_TEST_A"] == "1"
    assert os.environ["NICHEDOCS_TEST_B"] == "2"


def test_strips_surrounding_quotes(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('NICHEDOCS_TEST_QUOTED="hello world"\n')
    monkeypatch.delenv("NICHEDOCS_TEST_QUOTED", raising=False)

    _load_env_file(env)

    import os

    assert os.environ["NICHEDOCS_TEST_QUOTED"] == "hello world"


def test_tolerates_a_utf8_bom(tmp_path, monkeypatch):
    """Windows editors often save .env with a BOM; it must not corrupt the first key."""
    env = tmp_path / ".env"
    env.write_text("NICHEDOCS_TEST_BOM=ok\n", encoding="utf-8-sig")
    monkeypatch.delenv("NICHEDOCS_TEST_BOM", raising=False)

    _load_env_file(env)

    import os

    assert os.environ["NICHEDOCS_TEST_BOM"] == "ok"


def test_missing_file_is_not_an_error(tmp_path):
    _load_env_file(tmp_path / "does-not-exist.env")
