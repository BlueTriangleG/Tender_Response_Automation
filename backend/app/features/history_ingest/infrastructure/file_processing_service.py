from pathlib import Path

from starlette.datastructures import UploadFile

from app.features.history_ingest.infrastructure.parsers.base import FileProcessor
from app.features.history_ingest.infrastructure.parsers.csv_parser import CsvParser
from app.features.history_ingest.infrastructure.parsers.json_parser import JsonParser
from app.features.history_ingest.infrastructure.parsers.markdown_parser import MarkdownParser
from app.features.history_ingest.infrastructure.parsers.models import FileContent
from app.features.history_ingest.schemas.responses import ProcessedHistoryFileResult


class FileProcessingService:
    def __init__(self, processors: list[FileProcessor] | None = None) -> None:
        resolved_processors = processors or [
            JsonParser(),
            MarkdownParser(),
            CsvParser(),
        ]
        self._processors = {processor.extension: processor for processor in resolved_processors}

    async def process_upload(self, upload_file: UploadFile) -> ProcessedHistoryFileResult:
        filename = upload_file.filename or "unknown"
        extension = Path(filename).suffix.lower()
        processor = self._processors.get(extension)

        if processor is None:
            return ProcessedHistoryFileResult(
                status="failed",
                payload=None,
                error_code="unsupported_extension",
                error_message=f"Unsupported file type: {extension or '[none]'}",
            )

        try:
            raw_bytes = await upload_file.read()
            raw_text = raw_bytes.decode("utf-8")
            payload = processor.parse(
                FileContent(
                    file_name=filename,
                    extension=extension,
                    content_type=upload_file.content_type,
                    size_bytes=len(raw_bytes),
                    raw_text=raw_text,
                )
            )
        except UnicodeDecodeError:
            return ProcessedHistoryFileResult(
                status="failed",
                payload=None,
                error_code="decode_error",
                error_message=f"Failed to decode file as UTF-8: {filename}",
            )
        except Exception as exc:
            return ProcessedHistoryFileResult(
                status="failed",
                payload=None,
                error_code="parse_error",
                error_message=str(exc),
            )

        return ProcessedHistoryFileResult(status="processed", payload=payload)
