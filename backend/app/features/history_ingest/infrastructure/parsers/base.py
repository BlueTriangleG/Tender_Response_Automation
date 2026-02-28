from typing import Protocol

from app.features.history_ingest.infrastructure.parsers.models import FileContent
from app.features.history_ingest.schemas.responses import ParsedFilePayload


class FileProcessor(Protocol):
    extension: str
    parsed_kind: str

    def parse(self, content: FileContent) -> ParsedFilePayload: ...
