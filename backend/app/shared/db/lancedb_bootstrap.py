"""Application-level LanceDB bootstrap entrypoint."""

from pathlib import Path

from lancedb.db import DBConnection

from app.core.config import settings
from app.db.lancedb_client import ensure_lancedb_ready


def bootstrap_lancedb(
    uri: str | Path | None = None,
    qa_table_name: str | None = None,
    document_table_name: str | None = None,
) -> DBConnection:
    """Resolve settings defaults and initialize LanceDB for app startup."""

    return ensure_lancedb_ready(
        uri=uri or settings.lancedb_uri,
        qa_table_name=qa_table_name or settings.lancedb_qa_table_name,
        document_table_name=document_table_name or settings.lancedb_document_table_name,
    )
