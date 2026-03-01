"""Environment-loading helpers for live E2E tests."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def load_openai_api_key_from_dotenv(dotenv_path: Path | None = None) -> str | None:
    """Load `.env` into the test process and return the resolved OpenAI API key."""

    if dotenv_path is not None:
        load_dotenv(dotenv_path=dotenv_path, override=True)
        return os.getenv("OPENAI_API_KEY")

    backend_dotenv_path = BACKEND_ROOT / ".env"
    if backend_dotenv_path.exists():
        load_dotenv(dotenv_path=backend_dotenv_path, override=False)
        return os.getenv("OPENAI_API_KEY")

    # Fall back to python-dotenv's parent-directory search so tests still work
    # when a developer keeps shared credentials in a repository-level `.env`.
    load_dotenv(override=False)
    return os.getenv("OPENAI_API_KEY")
