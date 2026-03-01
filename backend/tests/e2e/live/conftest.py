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
    """Return a TestClient backed by an isolated temporary LanceDB directory.

    The ``get_tender_response_runner`` dependency is decorated with
    ``@lru_cache``, so its ``QaAlignmentRepository`` would otherwise retain
    the LanceDB connection from the first test case for all subsequent ones —
    causing alignment searches to target the wrong (stale) database directory.
    Clearing the cache here guarantees a fresh runner is constructed against
    the patched ``settings.lancedb_uri`` for each test.
    """

    from app.core.config import settings
    from app.features.tender_response.api.dependencies import get_tender_response_runner
    from app.features.tender_response.infrastructure.workflows.registry import (
        TenderWorkflowRegistry,
    )
    from app.main import app

    db_uri = tmp_path / "lancedb"
    monkeypatch.setattr(settings, "lancedb_uri", str(db_uri))
    monkeypatch.setattr(settings, "tender_workflow_debug", False)

    # Two layers of lru_cache must be cleared so that every test case builds
    # fresh service objects that read the patched settings.lancedb_uri:
    #
    # 1. get_tender_response_runner — the FastAPI dependency that holds the
    #    TenderResponseRunner (and its TenderWorkflowRegistry).
    # 2. TenderWorkflowRegistry._parallel_graph — static
    #    lru_cache method that embeds a QaAlignmentRepository.  If only the
    #    outer runner cache is cleared the compiled graph (and its repository
    #    connection) from the first test case is silently reused by all later
    #    cases, causing alignment searches to target the wrong database.
    get_tender_response_runner.cache_clear()
    TenderWorkflowRegistry._parallel_graph.cache_clear()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    get_tender_response_runner.cache_clear()
    TenderWorkflowRegistry._parallel_graph.cache_clear()
