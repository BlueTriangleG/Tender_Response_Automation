from pathlib import Path

import pytest

from app.core.config import Settings


def test_lancedb_uri_defaults_to_repo_data_directory() -> None:
    settings = Settings()
    expected = Path(__file__).resolve().parents[3] / "data" / "lancedb"
    assert Path(settings.lancedb_uri) == expected


def test_lancedb_table_names_have_expected_defaults() -> None:
    settings = Settings()

    assert settings.lancedb_qa_table_name == "qa_records"
    assert settings.lancedb_document_table_name == "document_records"


def test_openai_model_defaults_have_feature_specific_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PANS_BACKEND_TENDER_WORKFLOW_DEBUG", raising=False)
    settings = Settings()

    assert settings.openai_chat_model == "gpt-4o-mini"
    assert settings.openai_csv_column_model == "gpt-4o-mini"
    assert settings.openai_tender_response_model == "gpt-5-mini-2025-08-07"
    assert settings.tender_workflow_debug is False
