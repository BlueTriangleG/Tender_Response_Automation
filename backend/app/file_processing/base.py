from typing import Protocol

from app.file_processing.models import FileContent
from app.schemas.history_ingest import ParsedFilePayload


class FileProcessor(Protocol):
    extension: str
    parsed_kind: str

    def parse(self, content: FileContent) -> ParsedFilePayload: ...
