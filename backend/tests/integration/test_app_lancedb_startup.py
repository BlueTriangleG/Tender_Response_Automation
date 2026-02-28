from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.lancedb_client import get_lancedb_connection
from app.main import app


def test_app_startup_bootstraps_lancedb_tables(tmp_path: Path, monkeypatch) -> None:
    db_uri = tmp_path / "lancedb"

    monkeypatch.setattr(settings, "lancedb_uri", str(db_uri))
    monkeypatch.setattr(settings, "lancedb_qa_table_name", "qa_records")
    monkeypatch.setattr(settings, "lancedb_document_table_name", "document_records")

    with TestClient(app):
        assert app.state.lancedb_ready is True

    connection = get_lancedb_connection(db_uri)

    assert db_uri.exists()
    assert sorted(connection.list_tables().tables) == ["document_records", "qa_records"]
