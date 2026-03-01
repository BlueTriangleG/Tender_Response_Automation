"""Shared parser input models for history-ingest infrastructure."""

from dataclasses import dataclass


@dataclass(slots=True)
class FileContent:
    """Raw file metadata and text content passed to parser implementations."""

    file_name: str
    extension: str
    content_type: str | None
    size_bytes: int
    raw_bytes: bytes
    raw_text: str | None
