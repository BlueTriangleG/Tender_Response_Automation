from starlette.datastructures import UploadFile

from app.file_processing.service import FileProcessingService
from app.schemas.history_ingest import (
    HistoryIngestRequestOptions,
    HistoryIngestResponse,
    ProcessedHistoryFileResult,
)


class HistoryIngestService:
    def __init__(self, file_processing_service: FileProcessingService | None = None) -> None:
        self._file_processing_service = file_processing_service or FileProcessingService()

    async def process_files(
        self,
        files: list[UploadFile],
        request_options: HistoryIngestRequestOptions | None = None,
    ) -> HistoryIngestResponse:
        results: list[ProcessedHistoryFileResult] = []

        for upload_file in files:
            results.append(await self._file_processing_service.process_upload(upload_file))

        processed_file_count = sum(result.status == "processed" for result in results)
        failed_file_count = sum(result.status == "failed" for result in results)

        return HistoryIngestResponse(
            total_file_count=len(files),
            processed_file_count=processed_file_count,
            failed_file_count=failed_file_count,
            request_options=request_options or HistoryIngestRequestOptions(),
            files=results,
        )

    async def persist_processed_files(self, _: list[ProcessedHistoryFileResult]) -> None:
        return None
