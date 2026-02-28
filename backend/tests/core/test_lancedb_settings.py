from pathlib import Path

from app.core.config import Settings


def test_lancedb_uri_defaults_to_repo_data_directory() -> None:
    settings = Settings()
    expected = Path(__file__).resolve().parents[3] / "data" / "lancedb"
    assert Path(settings.lancedb_uri) == expected


def test_lancedb_table_names_have_expected_defaults() -> None:
    settings = Settings()

    assert settings.lancedb_qa_table_name == "qa_records"
    assert settings.lancedb_document_table_name == "document_records"
