import csv
from io import StringIO
from starlette.datastructures import UploadFile

from app.file_processing.csv_column_mapping import infer_csv_columns_from_headers
from app.file_processing.service import FileProcessingService
from app.schemas.history_ingest import (
    HistoryIngestRequestOptions,
    HistoryIngestResponse,
    ProcessedHistoryFileResult,
)
from app.services.csv_column_detection_service import CsvColumnDetectionService
from app.services.csv_qa_normalization_service import CsvQaNormalizationService
from app.services.qa_embedding_service import QaEmbeddingService
from app.repositories.qa_repository import QaRepository


class HistoryIngestService:
    def __init__(
        self,
        file_processing_service: FileProcessingService | None = None,
        csv_column_detection_service: CsvColumnDetectionService | None = None,
        csv_qa_normalization_service: CsvQaNormalizationService | None = None,
        qa_embedding_service: QaEmbeddingService | None = None,
        qa_repository: QaRepository | None = None,
    ) -> None:
        self._file_processing_service = file_processing_service or FileProcessingService()
        self._csv_column_detection_service = csv_column_detection_service
        self._csv_qa_normalization_service = csv_qa_normalization_service
        self._qa_embedding_service = qa_embedding_service
        self._qa_repository = qa_repository

    async def process_files(
        self,
        files: list[UploadFile],
        request_options: HistoryIngestRequestOptions | None = None,
    ) -> HistoryIngestResponse:
        final_results: list[ProcessedHistoryFileResult] = []

        for upload_file in files:
            parsed_result = await self._file_processing_service.process_upload(upload_file)
            if parsed_result.status == "failed" or parsed_result.payload is None:
                final_results.append(parsed_result)
                continue

            if parsed_result.payload.extension != ".csv":
                final_results.append(
                    ProcessedHistoryFileResult(
                        status="failed",
                        payload=parsed_result.payload,
                        error_code="unsupported_ingest_type",
                        error_message="Only CSV files are persisted in this phase.",
                    )
                )
                continue

            headers = self._extract_csv_headers(parsed_result.payload.raw_text)
            deterministic_result = infer_csv_columns_from_headers(headers)
            detection_result = await self._csv_column_detection_service.detect_columns(
                headers=headers,
                sample_rows=parsed_result.payload.structured_data or [],
                deterministic_result=deterministic_result,
            )

            if detection_result.detected_columns is None:
                final_results.append(
                    ProcessedHistoryFileResult(
                        status="failed",
                        payload=parsed_result.payload,
                        error_code=detection_result.error_code,
                        error_message=detection_result.error_message,
                        failed_row_count=parsed_result.payload.row_count or 0,
                    )
                )
                continue

            normalization_result = self._get_csv_qa_normalization_service().normalize_rows(
                file_name=parsed_result.payload.file_name,
                detected_columns=detection_result.detected_columns,
                rows=parsed_result.payload.structured_data or [],
            )

            if not normalization_result.records:
                final_results.append(
                    ProcessedHistoryFileResult(
                        status="failed",
                        payload=parsed_result.payload,
                        error_code="row_normalization_failed",
                        error_message="No valid QA rows were produced from the CSV file.",
                        detected_columns=detection_result.detected_columns,
                        failed_row_count=normalization_result.failed_row_count,
                    )
                )
                continue

            vectors = await self._get_qa_embedding_service().embed_texts(
                [record.text for record in normalization_result.records]
            )
            repository_records = []
            for record, vector in zip(normalization_result.records, vectors, strict=True):
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
            final_results.append(
                ProcessedHistoryFileResult(
                    status="processed",
                    payload=parsed_result.payload,
                    error_code=None,
                    error_message=None,
                    detected_columns=detection_result.detected_columns,
                    ingested_row_count=len(repository_records),
                    failed_row_count=normalization_result.failed_row_count,
                    storage_target="qa_records",
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

    async def persist_processed_files(self, _: list[ProcessedHistoryFileResult]) -> None:
        return None

    def _extract_csv_headers(self, raw_text: str) -> list[str]:
        reader = csv.reader(StringIO(raw_text))
        return next(reader, [])

    @property
    def _csv_column_detection_service(self) -> CsvColumnDetectionService:
        return self.__csv_column_detection_service or self._set_csv_column_detection_service()

    @_csv_column_detection_service.setter
    def _csv_column_detection_service(
        self,
        value: CsvColumnDetectionService | None,
    ) -> None:
        self.__csv_column_detection_service = value

    def _set_csv_column_detection_service(self) -> CsvColumnDetectionService:
        self.__csv_column_detection_service = CsvColumnDetectionService()
        return self.__csv_column_detection_service

    def _get_csv_qa_normalization_service(self) -> CsvQaNormalizationService:
        if self._csv_qa_normalization_service is None:
            self._csv_qa_normalization_service = CsvQaNormalizationService()
        return self._csv_qa_normalization_service

    def _get_qa_embedding_service(self) -> QaEmbeddingService:
        if self._qa_embedding_service is None:
            self._qa_embedding_service = QaEmbeddingService()
        return self._qa_embedding_service

    def _get_qa_repository(self) -> QaRepository:
        if self._qa_repository is None:
            self._qa_repository = QaRepository()
        return self._qa_repository
