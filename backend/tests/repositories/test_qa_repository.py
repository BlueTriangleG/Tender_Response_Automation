from pathlib import Path

from app.db.lancedb_client import ensure_lancedb_ready
from app.features.history_ingest.infrastructure.repositories.qa_lancedb_repository import (
    QaLanceDbRepository,
)


def test_upsert_records_inserts_rows_into_qa_table(tmp_path: Path) -> None:
    connection = ensure_lancedb_ready(uri=tmp_path / "lancedb")
    repository = QaLanceDbRepository(connection=connection)

    repository.upsert_records(
        [
            {
                "id": "row-1",
                "domain": "Security",
                "question": "What is TLS?",
                "answer": "TLS 1.2+",
                "text": "Question: What is TLS?\nAnswer: TLS 1.2+\nDomain: Security",
                "vector": [0.1] * 1536,
                "client": None,
                "source_doc": "history.csv",
                "tags": [],
                "risk_topics": [],
                "created_at": "2026-02-28T00:00:00+00:00",
                "updated_at": "2026-02-28T00:00:00+00:00",
            }
        ]
    )

    table = connection.open_table("qa_records")
    rows = table.to_arrow().to_pylist()

    assert len(rows) == 1
    assert rows[0]["id"] == "row-1"
    assert rows[0]["answer"] == "TLS 1.2+"


def test_upsert_records_updates_existing_ids_without_duplication(tmp_path: Path) -> None:
    connection = ensure_lancedb_ready(uri=tmp_path / "lancedb")
    repository = QaLanceDbRepository(connection=connection)
    updated_text = (
        "Question: What is TLS?\n"
        "Answer: TLS 1.3 available where supported\n"
        "Domain: Security"
    )

    repository.upsert_records(
        [
            {
                "id": "row-1",
                "domain": "Security",
                "question": "What is TLS?",
                "answer": "TLS 1.2+",
                "text": "Question: What is TLS?\nAnswer: TLS 1.2+\nDomain: Security",
                "vector": [0.1] * 1536,
                "client": None,
                "source_doc": "history.csv",
                "tags": [],
                "risk_topics": [],
                "created_at": "2026-02-28T00:00:00+00:00",
                "updated_at": "2026-02-28T00:00:00+00:00",
            }
        ]
    )
    repository.upsert_records(
        [
            {
                "id": "row-1",
                "domain": "Security",
                "question": "What is TLS?",
                "answer": "TLS 1.3 available where supported",
                "text": updated_text,
                "vector": [0.2] * 1536,
                "client": None,
                "source_doc": "history.csv",
                "tags": [],
                "risk_topics": [],
                "created_at": "2026-02-28T00:00:00+00:00",
                "updated_at": "2026-02-28T01:00:00+00:00",
            }
        ]
    )

    table = connection.open_table("qa_records")
    rows = table.to_arrow().to_pylist()

    assert len(rows) == 1
    assert rows[0]["answer"] == "TLS 1.3 available where supported"


def test_get_existing_record_ids_returns_only_ids_already_in_table(tmp_path: Path) -> None:
    connection = ensure_lancedb_ready(uri=tmp_path / "lancedb")
    repository = QaLanceDbRepository(connection=connection)
    repository.upsert_records(
        [
            {
                "id": "row-1",
                "domain": "Security",
                "question": "What is TLS?",
                "answer": "TLS 1.2+",
                "text": "Question: What is TLS?\nAnswer: TLS 1.2+\nDomain: Security",
                "vector": [0.1] * 1536,
                "client": None,
                "source_doc": "history.csv",
                "tags": [],
                "risk_topics": [],
                "created_at": "2026-02-28T00:00:00+00:00",
                "updated_at": "2026-02-28T00:00:00+00:00",
            }
        ]
    )

    existing_ids = repository.get_existing_record_ids(["row-1", "row-2"])

    assert existing_ids == {"row-1"}
