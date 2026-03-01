"""CSV parser for tender-response question imports."""

import csv
from io import StringIO

from app.features.tender_response.domain.models import TenderCsvParseResult
from app.features.tender_response.infrastructure.parsers.tender_tabular_normalizer import (
    TenderTabularNormalizer,
)


class TenderCsvParser:
    """Extract question rows and normalize them into TenderQuestion objects."""

    def __init__(self, normalizer: TenderTabularNormalizer | None = None) -> None:
        self._normalizer = normalizer or TenderTabularNormalizer()

    def parse_bytes(self, raw_bytes: bytes, *, source_file_name: str) -> TenderCsvParseResult:
        """Decode UTF-8 CSV bytes and parse them into tender questions."""

        try:
            raw_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"Failed to decode CSV as UTF-8: {source_file_name}") from exc
        return self.parse_text(raw_text, source_file_name=source_file_name)

    def parse_text(self, raw_text: str, *, source_file_name: str) -> TenderCsvParseResult:
        """Read the tender CSV and keep only rows that contain a usable question."""

        reader = csv.DictReader(StringIO(raw_text))
        headers = reader.fieldnames or []
        rows = [{key: value or "" for key, value in row.items()} for row in reader]
        return self._normalizer.normalize_rows(
            headers=headers,
            rows=rows,
            source_file_name=source_file_name,
        )
