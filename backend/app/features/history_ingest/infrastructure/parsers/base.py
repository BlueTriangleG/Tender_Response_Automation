"""Parsing protocol shared by history-ingest file adapters."""

from typing import Protocol

from app.features.history_ingest.infrastructure.parsers.models import FileContent
from app.features.history_ingest.schemas.responses import ParsedFilePayload


class FileProcessor(Protocol):
    """Interface implemented by file-type specific parsers."""

    extension: str
    parsed_kind: str

    def parse(self, content: FileContent) -> ParsedFilePayload: ...
