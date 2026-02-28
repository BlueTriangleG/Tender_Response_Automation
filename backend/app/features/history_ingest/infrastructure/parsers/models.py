from dataclasses import dataclass


@dataclass(slots=True)
class FileContent:
    file_name: str
    extension: str
    content_type: str | None
    size_bytes: int
    raw_text: str
