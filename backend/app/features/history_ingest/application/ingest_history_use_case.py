"""Application service for importing historical QA CSV files."""

import csv
from collections.abc import Sequence
from io import StringIO
from typing import Any

from starlette.datastructures import UploadFile

from app.features.history_ingest.domain.csv_column_mapping import (
    infer_csv_columns_from_headers,
)
from app.features.history_ingest.infrastructure.file_processing_service import (
    FileProcessingService,
)
from app.features.history_ingest.infrastructure.repositories.document_lancedb_repository import (
    DocumentLanceDbRepository,
)
from app.features.history_ingest.infrastructure.repositories.qa_lancedb_repository import (
    QaLanceDbRepository,
)
from app.features.history_ingest.infrastructure.services.csv_column_detection_service import (
    CsvColumnDetectionService,
)
from app.features.history_ingest.infrastructure.services.csv_qa_normalization_service import (
    CsvQaNormalizationService,
)
from app.features.history_ingest.infrastructure.services.document_chunking_service import (
    DocumentChunkingService,
)
from app.features.history_ingest.infrastructure.services.qa_embedding_service import (
    QaEmbeddingService,
)
from app.features.history_ingest.schemas.requests import HistoryIngestRequestOptions
from app.features.history_ingest.schemas.responses import (
    HistoryIngestResponse,
    ParsedFilePayload,
    ProcessedHistoryFileResult,
)


class IngestHistoryUseCase:
    """Coordinate parsing, column detection, normalization, embedding, and storage."""

    def __init__(
        self,
        file_processing_service: FileProcessingService | None = None,
        csv_column_detection_service: CsvColumnDetectionService | None = None,
        csv_qa_normalization_service: CsvQaNormalizationService | None = None,
        qa_embedding_service: QaEmbeddingService | None = None,
        qa_repository: QaLanceDbRepository | None = None,
        document_chunking_service: DocumentChunkingService | None = None,
        document_repository: DocumentLanceDbRepository | None = None,
    ) -> None:
        self._file_processing_service = file_processing_service or FileProcessingService()
        self._csv_column_detection_service = csv_column_detection_service
        self._csv_qa_normalization_service = csv_qa_normalization_service
        self._qa_embedding_service = qa_embedding_service
        self._qa_repository = qa_repository
        self._document_chunking_service = document_chunking_service
        self._document_repository = document_repository

    async def process_files(
        self,
        files: Sequence[UploadFile],
        request_options: HistoryIngestRequestOptions | None = None,
    ) -> HistoryIngestResponse:
        """Process each uploaded file and aggregate per-file ingest outcomes."""

        final_results: list[ProcessedHistoryFileResult] = []

        for upload_file in files:
            # Parse every file first so unsupported formats and decode failures are
            # reported using the same result shape as successful parses.
            parsed_result = await self._file_processing_service.process_upload(upload_file)
            if parsed_result.status == "failed" or parsed_result.payload is None:
                final_results.append(parsed_result)
                continue

            if parsed_result.payload.extension in {".csv", ".xlsx"}:
                final_results.append(await self._process_tabular_file(parsed_result.payload))
                continue

            if parsed_result.payload.extension in {".md", ".json", ".txt"}:
                final_results.append(await self._process_document_file(parsed_result.payload))
                continue

            final_results.append(
                ProcessedHistoryFileResult(
                    status="failed",
                    payload=parsed_result.payload,
                    error_code="unsupported_ingest_type",
                    error_message=(
                        "Only CSV, XLSX, MD, JSON, and TXT files are persisted in this phase."
                    ),
                )
            )

        processed_file_count = sum(result.status == "processed" for result in final_results)
        failed_file_count = sum(result.status == "failed" for result in final_results)

        return HistoryIngestResponse(
            total_file_count=len(files),
            processed_file_count=processed_file_count,
            failed_file_count=failed_file_count,
            request_options=request_options or HistoryIngestRequestOptions(),
            files=final_results,
        )

    async def _process_tabular_file(
        self,
        payload: ParsedFilePayload,
    ) -> ProcessedHistoryFileResult:
        """Persist CSV/XLSX files as normalized QA records."""

        headers = self._extract_csv_headers(payload.raw_text)
        deterministic_result = infer_csv_columns_from_headers(headers)
        detection_result = await self._get_csv_column_detection_service().detect_columns(
            headers=headers,
            sample_rows=payload.structured_data or [],
            deterministic_result=deterministic_result,
        )

        if detection_result.detected_columns is None:
            return ProcessedHistoryFileResult(
                status="failed",
                payload=payload,
                error_code=detection_result.error_code,
                error_message=detection_result.error_message,
                failed_row_count=payload.row_count or 0,
            )

        normalization_result = self._get_csv_qa_normalization_service().normalize_rows(
            file_name=payload.file_name,
            detected_columns=detection_result.detected_columns,
            rows=payload.structured_data or [],
        )

        if not normalization_result.records:
            return ProcessedHistoryFileResult(
                status="failed",
                payload=payload,
                error_code="row_normalization_failed",
                error_message="No valid QA rows were produced from the CSV file.",
                detected_columns=detection_result.detected_columns,
                failed_row_count=normalization_result.failed_row_count,
            )

        new_records = self._filter_new_records(normalization_result.records)

        if not new_records:
            return ProcessedHistoryFileResult(
                status="processed",
                payload=payload,
                detected_columns=detection_result.detected_columns,
                ingested_row_count=0,
                failed_row_count=normalization_result.failed_row_count,
                storage_target="qa_records",
            )

        vectors = await self._get_qa_embedding_service().embed_texts(
            [record.text for record in new_records]
        )
        repository_records = []
        for record, vector in zip(new_records, vectors, strict=True):
            repository_records.append(
                {
                    "id": record.id,
                    "domain": record.domain,
                    "question": record.question,
                    "answer": record.answer,
                    "text": record.text,
                    "vector": vector,
                    "client": record.client,
                    "source_doc": record.source_doc,
                    "tags": record.tags,
                    "risk_topics": record.risk_topics,
                    "created_at": record.created_at,
                    "updated_at": record.updated_at,
                }
            )

        self._get_qa_repository().upsert_records(repository_records)
        return ProcessedHistoryFileResult(
            status="processed",
            payload=payload,
            detected_columns=detection_result.detected_columns,
            ingested_row_count=len(repository_records),
            failed_row_count=normalization_result.failed_row_count,
            storage_target="qa_records",
        )

    async def _process_document_file(
        self,
        payload: ParsedFilePayload,
    ) -> ProcessedHistoryFileResult:
        """Persist MD/JSON/TXT files as document chunks."""

        chunk_records = self._get_document_chunking_service().build_chunks(payload)
        if not chunk_records:
            return ProcessedHistoryFileResult(
                status="failed",
                payload=payload,
                error_code="document_chunking_failed",
                error_message="No document chunks were produced from the uploaded file.",
            )

        new_chunk_records = self._filter_new_document_chunks(chunk_records)
        if not new_chunk_records:
            return ProcessedHistoryFileResult(
                status="processed",
                payload=payload,
                ingested_row_count=0,
                storage_target="document_records",
            )

        vectors = await self._get_qa_embedding_service().embed_texts(
            [record.text for record in new_chunk_records]
        )
        repository_records: list[dict[str, Any]] = []
        for record, vector in zip(new_chunk_records, vectors, strict=True):
            repository_records.append(
                {
                    "id": record.id,
                    "document_id": record.document_id,
                    "document_type": record.document_type,
                    "domain": record.domain,
                    "title": record.title,
                    "text": record.text,
                    "vector": vector,
                    "source_doc": record.source_doc,
                    "tags": record.tags,
                    "risk_topics": record.risk_topics,
                    "client": record.client,
                    "chunk_index": record.chunk_index,
                    "created_at": record.created_at,
                    "updated_at": record.updated_at,
                }
            )

        self._get_document_repository().upsert_records(repository_records)
        return ProcessedHistoryFileResult(
            status="processed",
            payload=payload,
            ingested_row_count=len(repository_records),
            storage_target="document_records",
        )

    def _extract_csv_headers(self, raw_text: str) -> list[str]:
        """Read the first CSV row as headers without reparsing the full file."""

        reader = csv.reader(StringIO(raw_text))
        return next(reader, [])

    def _get_csv_column_detection_service(self) -> CsvColumnDetectionService:
        """Lazily construct the column detection dependency."""

        if self._csv_column_detection_service is None:
            self._csv_column_detection_service = CsvColumnDetectionService()
        return self._csv_column_detection_service

    def _get_csv_qa_normalization_service(self) -> CsvQaNormalizationService:
        """Lazily construct the row-normalization dependency."""

        if self._csv_qa_normalization_service is None:
            self._csv_qa_normalization_service = CsvQaNormalizationService()
        return self._csv_qa_normalization_service

    def _get_qa_embedding_service(self) -> QaEmbeddingService:
        """Lazily construct the embeddings dependency."""

        if self._qa_embedding_service is None:
            self._qa_embedding_service = QaEmbeddingService()
        return self._qa_embedding_service

    def _get_qa_repository(self) -> QaLanceDbRepository:
        """Lazily construct the persistence dependency."""

        if self._qa_repository is None:
            self._qa_repository = QaLanceDbRepository()
        return self._qa_repository

    def _get_document_chunking_service(self) -> DocumentChunkingService:
        """Lazily construct the document chunking dependency."""

        if self._document_chunking_service is None:
            self._document_chunking_service = DocumentChunkingService()
        return self._document_chunking_service

    def _get_document_repository(self) -> DocumentLanceDbRepository:
        """Lazily construct the document persistence dependency."""

        if self._document_repository is None:
            self._document_repository = DocumentLanceDbRepository()
        return self._document_repository

    def _filter_new_records(self, records):
        """Deduplicate within the batch, then skip ids already stored in LanceDB."""

        unique_records_by_id: dict[str, Any] = {}
        for record in records:
            # setdefault preserves the first normalized instance for a stable id.
            unique_records_by_id.setdefault(record.id, record)

        unique_records = list(unique_records_by_id.values())
        existing_ids = self._get_qa_repository().get_existing_record_ids(
            [record.id for record in unique_records]
        )
        return [record for record in unique_records if record.id not in existing_ids]

    def _filter_new_document_chunks(self, records):
        """Deduplicate document chunks within the batch and against LanceDB."""

        unique_records_by_id: dict[str, Any] = {}
        for record in records:
            unique_records_by_id.setdefault(record.id, record)

        unique_records = list(unique_records_by_id.values())
        existing_ids = self._get_document_repository().get_existing_record_ids(
            [record.id for record in unique_records]
        )
        return [record for record in unique_records if record.id not in existing_ids]
