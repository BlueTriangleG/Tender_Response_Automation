"""Plain-text parser for history-ingest uploads."""

from app.features.history_ingest.infrastructure.parsers.models import FileContent
from app.features.history_ingest.schemas.responses import ParsedFilePayload


class TextParser:
    """Pass plain-text uploads through as unstructured evidence."""

    extension = ".txt"
    parsed_kind = "text"

    def parse(self, content: FileContent) -> ParsedFilePayload:
        """Return raw text without attempting structured extraction."""

        raw_text = content.raw_text or ""
        return ParsedFilePayload(
            file_name=content.file_name,
            extension=content.extension,
            content_type=content.content_type,
            size_bytes=content.size_bytes,
            parsed_kind=self.parsed_kind,
            raw_text=raw_text,
            structured_data=None,
            row_count=None,
            warnings=[],
        )
