from io import BytesIO

from starlette.datastructures import Headers, UploadFile

from app.features.history_ingest.application.ingest_history_use_case import (
    IngestHistoryUseCase,
)
from app.features.history_ingest.schemas.requests import HistoryIngestRequestOptions


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


class FakeEmbeddingService:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[list[str]] = []

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [self.vectors[index % len(self.vectors)] for index, _ in enumerate(texts)]


class FakeDocumentRepository:
    def __init__(self, existing_ids: set[str] | None = None) -> None:
        self.records: list[dict] = []
        self.existing_ids = existing_ids or set()

    def upsert_records(self, records: list[dict]) -> None:
        self.records.extend(records)

    def get_existing_record_ids(self, record_ids: list[str]) -> set[str]:
        return self.existing_ids.intersection(record_ids)


async def test_process_files_persists_json_upload_into_document_records() -> None:
    service = IngestHistoryUseCase(
        qa_embedding_service=FakeEmbeddingService([[0.1, 0.2, 0.3]]),
        document_repository=FakeDocumentRepository(),
    )

    response = await service.process_files(
        [
            make_upload_file(
                "history.json",
                b'{"hello":"world"}',
                "application/json",
            )
        ],
        request_options=HistoryIngestRequestOptions(
            output_format="excel",
            similarity_threshold=0.84,
        ),
    )

    assert response.total_file_count == 1
    assert response.processed_file_count == 1
    assert response.failed_file_count == 0
    assert response.request_options.output_format == "excel"
    assert response.request_options.similarity_threshold == 0.84
    assert response.files[0].status == "processed"
    assert response.files[0].storage_target == "document_records"


async def test_process_files_persists_markdown_and_json_uploads_individually() -> None:
    service = IngestHistoryUseCase(
        qa_embedding_service=FakeEmbeddingService([[0.1, 0.2, 0.3]]),
        document_repository=FakeDocumentRepository(),
    )

    response = await service.process_files(
        [
            make_upload_file("one.md", b"# one", "text/markdown"),
            make_upload_file("three.json", b'{"ok":true}', "application/json"),
        ]
    )

    assert response.total_file_count == 2
    assert response.processed_file_count == 2
    assert response.failed_file_count == 0
    assert [result.status for result in response.files] == [
        "processed",
        "processed",
    ]
    assert response.files[0].storage_target == "document_records"
    assert response.files[1].storage_target == "document_records"


async def test_process_files_continues_when_one_file_fails() -> None:
    service = IngestHistoryUseCase(
        qa_embedding_service=FakeEmbeddingService([[0.1, 0.2, 0.3]]),
        document_repository=FakeDocumentRepository(),
    )

    response = await service.process_files(
        [
            make_upload_file("bad.pdf", b"%PDF", "application/pdf"),
            make_upload_file("good.md", b"# ok", "text/markdown"),
        ]
    )

    assert response.total_file_count == 2
    assert response.processed_file_count == 1
    assert response.failed_file_count == 1
    assert response.files[0].status == "failed"
    assert response.files[0].error_code == "unsupported_extension"
    assert response.files[1].status == "processed"
    assert response.files[1].storage_target == "document_records"
