from app.schemas.history_ingest import (
    DetectedCsvColumns,
    HistoryIngestRequestOptions,
    ParsedFilePayload,
    ProcessedHistoryFileResult,
)
from app.services.csv_column_detection_service import CsvColumnDetectionResult
from app.services.csv_qa_normalization_service import CsvQaNormalizationResult, NormalizedQaRecord
from app.services.history_ingest_service import HistoryIngestService


class DummyUploadFile:
    def __init__(self, filename: str) -> None:
        self.filename = filename


class FakeFileProcessingService:
    def __init__(self, results: list[ProcessedHistoryFileResult]) -> None:
        self.results = results
        self.calls = 0

    async def process_upload(self, upload_file) -> ProcessedHistoryFileResult:
        result = self.results[self.calls]
        self.calls += 1
        return result


class FakeCsvColumnDetectionService:
    def __init__(self, result: CsvColumnDetectionResult) -> None:
        self.result = result
        self.calls = 0

    async def detect_columns(self, headers, sample_rows, deterministic_result):
        self.calls += 1
        return self.result


class FakeNormalizationService:
    def __init__(self, result: CsvQaNormalizationResult) -> None:
        self.result = result
        self.calls = 0

    def normalize_rows(self, file_name, detected_columns, rows):
        self.calls += 1
        return self.result


class FakeEmbeddingService:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[list[str]] = []

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return self.vectors


class FakeQaRepository:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def upsert_records(self, records: list[dict]) -> None:
        self.records.extend(records)


async def test_process_files_runs_csv_parse_detect_normalize_embed_and_upsert() -> None:
    file_processing_service = FakeFileProcessingService(
        [
            ProcessedHistoryFileResult(
                status="processed",
                payload=ParsedFilePayload(
                    file_name="history.csv",
                    extension=".csv",
                    content_type="text/csv",
                    size_bytes=64,
                    parsed_kind="csv",
                    raw_text="question,answer,domain\nQ,A,Security\n",
                    structured_data=[{"question": "Q", "answer": "A", "domain": "Security"}],
                    row_count=1,
                    warnings=[],
                ),
            )
        ]
    )
    detection_service = FakeCsvColumnDetectionService(
        CsvColumnDetectionResult(
            detected_columns=DetectedCsvColumns(
                question_col="question",
                answer_col="answer",
                domain_col="domain",
            ),
            used_llm=False,
        )
    )
    normalization_service = FakeNormalizationService(
        CsvQaNormalizationResult(
            records=[
                NormalizedQaRecord(
                    id="row-1",
                    domain="Security",
                    question="Q",
                    answer="A",
                    text="Question: Q\nAnswer: A\nDomain: Security",
                    client=None,
                    source_doc="history.csv",
                    tags=[],
                    risk_topics=[],
                    created_at="2026-02-28T00:00:00+00:00",
                    updated_at="2026-02-28T00:00:00+00:00",
                )
            ],
            failed_row_count=0,
        )
    )
    embedding_service = FakeEmbeddingService([[0.1, 0.2, 0.3]])
    repository = FakeQaRepository()

    service = HistoryIngestService(
        file_processing_service=file_processing_service,
        csv_column_detection_service=detection_service,
        csv_qa_normalization_service=normalization_service,
        qa_embedding_service=embedding_service,
        qa_repository=repository,
    )

    response = await service.process_files(
        [DummyUploadFile("history.csv")],
        request_options=HistoryIngestRequestOptions(),
    )

    assert response.total_file_count == 1
    assert response.processed_file_count == 1
    assert response.failed_file_count == 0
    assert response.files[0].detected_columns is not None
    assert response.files[0].ingested_row_count == 1
    assert response.files[0].storage_target == "qa_records"
    assert repository.records[0]["id"] == "row-1"
    assert repository.records[0]["vector"] == [0.1, 0.2, 0.3]


async def test_process_files_marks_non_csv_files_as_unsupported_for_persistence() -> None:
    file_processing_service = FakeFileProcessingService(
        [
            ProcessedHistoryFileResult(
                status="processed",
                payload=ParsedFilePayload(
                    file_name="notes.md",
                    extension=".md",
                    content_type="text/markdown",
                    size_bytes=10,
                    parsed_kind="markdown",
                    raw_text="# Notes",
                    structured_data=None,
                    row_count=None,
                    warnings=[],
                ),
            )
        ]
    )

    service = HistoryIngestService(file_processing_service=file_processing_service)

    response = await service.process_files([DummyUploadFile("notes.md")])

    assert response.processed_file_count == 0
    assert response.failed_file_count == 1
    assert response.files[0].error_code == "unsupported_ingest_type"


async def test_process_files_continues_when_csv_column_detection_fails() -> None:
    file_processing_service = FakeFileProcessingService(
        [
            ProcessedHistoryFileResult(
                status="processed",
                payload=ParsedFilePayload(
                    file_name="bad.csv",
                    extension=".csv",
                    content_type="text/csv",
                    size_bytes=64,
                    parsed_kind="csv",
                    raw_text="a,b,c\n1,2,3\n",
                    structured_data=[{"a": "1", "b": "2", "c": "3"}],
                    row_count=1,
                    warnings=[],
                ),
            ),
            ProcessedHistoryFileResult(
                status="processed",
                payload=ParsedFilePayload(
                    file_name="good.csv",
                    extension=".csv",
                    content_type="text/csv",
                    size_bytes=64,
                    parsed_kind="csv",
                    raw_text="question,answer,domain\nQ,A,Security\n",
                    structured_data=[{"question": "Q", "answer": "A", "domain": "Security"}],
                    row_count=1,
                    warnings=[],
                ),
            ),
        ]
    )
    detection_results = [
        CsvColumnDetectionResult(
            detected_columns=None,
            used_llm=True,
            error_code="column_mapping_failed",
            error_message="Could not determine CSV columns.",
        ),
        CsvColumnDetectionResult(
            detected_columns=DetectedCsvColumns(
                question_col="question",
                answer_col="answer",
                domain_col="domain",
            ),
            used_llm=False,
        ),
    ]

    class SequencedDetectionService:
        def __init__(self) -> None:
            self.calls = 0

        async def detect_columns(self, headers, sample_rows, deterministic_result):
            result = detection_results[self.calls]
            self.calls += 1
            return result

    normalization_service = FakeNormalizationService(
        CsvQaNormalizationResult(
            records=[
                NormalizedQaRecord(
                    id="row-1",
                    domain="Security",
                    question="Q",
                    answer="A",
                    text="Question: Q\nAnswer: A\nDomain: Security",
                    client=None,
                    source_doc="good.csv",
                    tags=[],
                    risk_topics=[],
                    created_at="2026-02-28T00:00:00+00:00",
                    updated_at="2026-02-28T00:00:00+00:00",
                )
            ],
            failed_row_count=0,
        )
    )
    embedding_service = FakeEmbeddingService([[0.1, 0.2, 0.3]])
    repository = FakeQaRepository()

    service = HistoryIngestService(
        file_processing_service=file_processing_service,
        csv_column_detection_service=SequencedDetectionService(),
        csv_qa_normalization_service=normalization_service,
        qa_embedding_service=embedding_service,
        qa_repository=repository,
    )

    response = await service.process_files(
        [DummyUploadFile("bad.csv"), DummyUploadFile("good.csv")]
    )

    assert response.total_file_count == 2
    assert response.processed_file_count == 1
    assert response.failed_file_count == 1
    assert response.files[0].error_code == "column_mapping_failed"
    assert response.files[1].ingested_row_count == 1
    assert len(repository.records) == 1
