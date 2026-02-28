"""JSON parser used by the history-ingest upload flow."""

import json

from app.features.history_ingest.infrastructure.parsers.models import FileContent
from app.features.history_ingest.schemas.responses import ParsedFilePayload


class JsonParser:
    """Parse JSON uploads while preserving the original text payload."""

    extension = ".json"
    parsed_kind = "json"

    def parse(self, content: FileContent) -> ParsedFilePayload:
        """Return the decoded JSON object as structured data."""

        structured_data = json.loads(content.raw_text)
        return ParsedFilePayload(
            file_name=content.file_name,
            extension=content.extension,
            content_type=content.content_type,
            size_bytes=content.size_bytes,
            parsed_kind=self.parsed_kind,
            raw_text=content.raw_text,
            structured_data=structured_data,
            row_count=1,
            warnings=[],
        )
