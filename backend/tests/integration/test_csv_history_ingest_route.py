from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.lancedb_client import get_lancedb_connection
from app.main import app


async def fake_embed_texts(self, texts: list[str]) -> list[list[float]]:
    return [[0.1] * 1536 for _ in texts]


def test_csv_history_ingest_route_persists_rows_to_qa_table(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_uri = tmp_path / "lancedb"
    monkeypatch.setattr(settings, "lancedb_uri", str(db_uri))
    monkeypatch.setattr(
        "app.services.qa_embedding_service.QaEmbeddingService.embed_texts",
        fake_embed_texts,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/ingest/history",
            files={
                "file": (
                    "history.csv",
                    b"question,answer,domain\nWhat is TLS?,TLS 1.2+,Security\n",
                    "text/csv",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["processed_file_count"] == 1
    assert payload["failed_file_count"] == 0
    assert payload["files"][0]["ingested_row_count"] == 1
    assert payload["files"][0]["storage_target"] == "qa_records"

    connection = get_lancedb_connection(db_uri)
    table = connection.open_table(settings.lancedb_qa_table_name)
    rows = table.to_arrow().to_pylist()

    assert len(rows) == 1
    assert rows[0]["question"] == "What is TLS?"
    assert rows[0]["answer"] == "TLS 1.2+"
    assert rows[0]["domain"] == "Security"
