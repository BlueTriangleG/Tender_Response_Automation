from __future__ import annotations

import os
from pathlib import Path

from tests.e2e.live import env_support
from tests.e2e.live.env_support import load_openai_api_key_from_dotenv


def test_load_openai_api_key_from_dotenv_reads_backend_dotenv(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("OPENAI_API_KEY=test-from-dotenv\n", encoding="utf-8")

    api_key = load_openai_api_key_from_dotenv(dotenv_path)

    assert api_key == "test-from-dotenv"


def test_load_openai_api_key_from_dotenv_uses_backend_root_dotenv(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(env_support, "BACKEND_ROOT", tmp_path)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=backend-dotenv-key\n", encoding="utf-8")

    api_key = load_openai_api_key_from_dotenv()

    assert api_key == "backend-dotenv-key"
    assert os.getenv("OPENAI_API_KEY") == "backend-dotenv-key"


def test_load_openai_api_key_from_dotenv_does_not_override_existing_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "already-set")
    monkeypatch.setattr(env_support, "BACKEND_ROOT", tmp_path)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=dotenv-value\n", encoding="utf-8")

    api_key = load_openai_api_key_from_dotenv()

    assert api_key == "already-set"
