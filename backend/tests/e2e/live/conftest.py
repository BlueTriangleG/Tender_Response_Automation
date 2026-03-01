"""Fixtures for live edge-case E2E tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.e2e.live.edge_case_suite.models import ARTIFACT_ROOT
from tests.e2e.live.env_support import load_openai_api_key_from_dotenv


@pytest.fixture(autouse=True)
def require_openai_api_key(request) -> None:
    """Skip live E2E tests when the OpenAI API key is missing."""

    if request.node.get_closest_marker("live_e2e") and not (
        os.getenv("OPENAI_API_KEY") or load_openai_api_key_from_dotenv()
    ):
        pytest.skip("OPENAI_API_KEY is required for live_e2e tests")


@pytest.fixture
def artifact_root() -> Path:
    """Return the artifact directory used for the current live suite run."""

    root = ARTIFACT_ROOT / "latest"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def live_client(tmp_path: Path, monkeypatch) -> TestClient:
    """Return a TestClient backed by an isolated temporary LanceDB directory."""

    from app.core.config import settings
    from app.main import app

    db_uri = tmp_path / "lancedb"
    monkeypatch.setattr(settings, "lancedb_uri", str(db_uri))
    monkeypatch.setattr(settings, "tender_workflow_debug", False)

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
