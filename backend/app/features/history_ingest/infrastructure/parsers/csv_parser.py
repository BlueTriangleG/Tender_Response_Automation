"""CSV parser used by the history-ingest upload flow."""

import csv
from io import StringIO

from app.features.history_ingest.infrastructure.parsers.models import FileContent
from app.features.history_ingest.schemas.responses import ParsedFilePayload


class CsvParser:
    """Convert CSV text into row dictionaries while preserving raw input."""

    extension = ".csv"
    parsed_kind = "csv"

    def parse(self, content: FileContent) -> ParsedFilePayload:
        """Return parsed rows and row count for downstream QA ingestion."""

        rows = list(csv.DictReader(StringIO(content.raw_text)))
        return ParsedFilePayload(
            file_name=content.file_name,
            extension=content.extension,
            content_type=content.content_type,
            size_bytes=content.size_bytes,
            parsed_kind=self.parsed_kind,
            raw_text=content.raw_text,
            structured_data=rows,
            row_count=len(rows),
            warnings=[],
        )
