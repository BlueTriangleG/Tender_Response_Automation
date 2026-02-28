"""Helpers for connecting to LanceDB and ensuring required tables exist."""

from pathlib import Path

import lancedb
import pyarrow as pa
from lancedb.db import DBConnection

from app.core.config import settings

VECTOR_DIMENSION = 1536


def build_qa_table_schema() -> pa.Schema:
    """Return the schema used for historical QA records."""

    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("domain", pa.string()),
            pa.field("question", pa.string()),
            pa.field("answer", pa.string()),
            pa.field("text", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), VECTOR_DIMENSION)),
            pa.field("client", pa.string()),
            pa.field("source_doc", pa.string()),
            pa.field("tags", pa.list_(pa.string())),
            pa.field("risk_topics", pa.list_(pa.string())),
            pa.field("created_at", pa.string()),
            pa.field("updated_at", pa.string()),
        ]
    )


def build_document_table_schema() -> pa.Schema:
    """Return the schema reserved for document chunk storage."""

    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("document_id", pa.string()),
            pa.field("document_type", pa.string()),
            pa.field("domain", pa.string()),
            pa.field("title", pa.string()),
            pa.field("text", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), VECTOR_DIMENSION)),
            pa.field("source_doc", pa.string()),
            pa.field("tags", pa.list_(pa.string())),
            pa.field("risk_topics", pa.list_(pa.string())),
            pa.field("client", pa.string()),
            pa.field("chunk_index", pa.int32()),
            pa.field("created_at", pa.string()),
            pa.field("updated_at", pa.string()),
        ]
    )


def get_lancedb_connection(uri: str | Path | None = None) -> DBConnection:
    """Open a LanceDB connection and create the data directory if needed."""

    db_uri = Path(uri or settings.lancedb_uri)
    db_uri.mkdir(parents=True, exist_ok=True)
    return lancedb.connect(db_uri)


def ensure_lancedb_ready(
    uri: str | Path | None = None,
    qa_table_name: str | None = None,
    document_table_name: str | None = None,
) -> DBConnection:
    """Create the configured tables on first boot and return the connection."""

    connection = get_lancedb_connection(uri=uri)
    existing_tables = set(connection.list_tables().tables)

    resolved_qa_table_name = qa_table_name or settings.lancedb_qa_table_name
    if resolved_qa_table_name not in existing_tables:
        connection.create_table(resolved_qa_table_name, schema=build_qa_table_schema())

    resolved_document_table_name = document_table_name or settings.lancedb_document_table_name
    if resolved_document_table_name not in existing_tables:
        connection.create_table(
            resolved_document_table_name,
            schema=build_document_table_schema(),
        )

    return connection
