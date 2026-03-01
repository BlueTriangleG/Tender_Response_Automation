"""Domain model for chunked historical document evidence."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class DocumentChunkRecord:
    """One chunk of non-tabular historical content prepared for LanceDB."""

    id: str
    document_id: str
    document_type: str
    title: str
    text: str
    source_doc: str
    chunk_index: int
    domain: str | None = None
    tags: list[str] = field(default_factory=list)
    risk_topics: list[str] = field(default_factory=list)
    client: str | None = None
    created_at: str = ""
    updated_at: str = ""
