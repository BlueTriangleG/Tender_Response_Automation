from io import BytesIO
from pathlib import Path

from starlette.datastructures import Headers, UploadFile

from app.core.config import settings
from app.db.lancedb_client import get_lancedb_connection
from app.features.history_ingest.application.ingest_history_use_case import (
    IngestHistoryUseCase,
)


def make_upload_file(
    filename: str,
    content: bytes,
    content_type: str,
) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


async def fake_embed_texts(self, texts: list[str]) -> list[list[float]]:
    return [[0.1] * 1536 for _ in texts]


async def test_process_files_persists_markdown_into_document_table(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "lancedb_uri", str(tmp_path / "lancedb"))
    monkeypatch.setattr(
        "app.features.history_ingest.infrastructure.services.qa_embedding_service.QaEmbeddingService.embed_texts",
        fake_embed_texts,
    )
    service = IngestHistoryUseCase()

    response = await service.process_files(
        [
            make_upload_file(
                "operations.md",
                b"# Operations\n\nProduction changes require peer review.\n",
                "text/markdown",
            )
        ]
    )

    assert response.processed_file_count == 1
    assert response.failed_file_count == 0
    assert response.files[0].storage_target == "document_records"
    assert response.files[0].ingested_row_count == 1

    connection = get_lancedb_connection(tmp_path / "lancedb")
    rows = connection.open_table(settings.lancedb_document_table_name).to_arrow().to_pylist()

    assert len(rows) == 1
    assert rows[0]["source_doc"] == "operations.md"
    assert "Production changes require peer review." in rows[0]["text"]


async def test_process_files_persists_json_into_document_table(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "lancedb_uri", str(tmp_path / "lancedb"))
    monkeypatch.setattr(
        "app.features.history_ingest.infrastructure.services.qa_embedding_service.QaEmbeddingService.embed_texts",
        fake_embed_texts,
    )
    service = IngestHistoryUseCase()

    response = await service.process_files(
        [
            make_upload_file(
                "security.json",
                b'{"controls":["tls","rbac"],"reviewed":true}',
                "application/json",
            )
        ]
    )

    assert response.processed_file_count == 1
    assert response.failed_file_count == 0
    assert response.files[0].storage_target == "document_records"
    assert response.files[0].ingested_row_count == 1

    connection = get_lancedb_connection(tmp_path / "lancedb")
    rows = connection.open_table(settings.lancedb_document_table_name).to_arrow().to_pylist()

    assert len(rows) == 1
    assert rows[0]["source_doc"] == "security.json"
    assert '"controls"' in rows[0]["text"]


async def test_process_files_persists_text_into_document_table(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "lancedb_uri", str(tmp_path / "lancedb"))
    monkeypatch.setattr(
        "app.features.history_ingest.infrastructure.services.qa_embedding_service.QaEmbeddingService.embed_texts",
        fake_embed_texts,
    )
    service = IngestHistoryUseCase()

    response = await service.process_files(
        [
            make_upload_file(
                "operations.txt",
                b"Escalate customer incidents within 30 minutes.\n",
                "text/plain",
            )
        ]
    )

    assert response.processed_file_count == 1
    assert response.failed_file_count == 0
    assert response.files[0].storage_target == "document_records"
    assert response.files[0].ingested_row_count == 1

    connection = get_lancedb_connection(tmp_path / "lancedb")
    rows = connection.open_table(settings.lancedb_document_table_name).to_arrow().to_pylist()

    assert len(rows) == 1
    assert rows[0]["source_doc"] == "operations.txt"
    assert "Escalate customer incidents within 30 minutes." in rows[0]["text"]
