from app.features.history_ingest.infrastructure.parsers.models import FileContent
from app.features.history_ingest.schemas.responses import ParsedFilePayload


class MarkdownParser:
    extension = ".md"
    parsed_kind = "markdown"

    def parse(self, content: FileContent) -> ParsedFilePayload:
        return ParsedFilePayload(
            file_name=content.file_name,
            extension=content.extension,
            content_type=content.content_type,
            size_bytes=content.size_bytes,
            parsed_kind=self.parsed_kind,
            raw_text=content.raw_text,
            structured_data=None,
            row_count=None,
            warnings=[],
        )
