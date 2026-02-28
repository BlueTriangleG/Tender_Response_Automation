from pathlib import Path

from app.db.lancedb_client import (
    build_document_table_schema,
    build_qa_table_schema,
    ensure_lancedb_ready,
)


def test_build_table_schemas_include_expected_columns() -> None:
    qa_schema = build_qa_table_schema()
    document_schema = build_document_table_schema()

    assert qa_schema.names == [
        "id",
        "domain",
        "question",
        "answer",
        "text",
        "vector",
        "client",
        "source_doc",
        "tags",
        "risk_topics",
        "created_at",
        "updated_at",
    ]
    assert document_schema.names == [
        "id",
        "document_id",
        "document_type",
        "domain",
        "title",
        "text",
        "vector",
        "source_doc",
        "tags",
        "risk_topics",
        "client",
        "chunk_index",
        "created_at",
        "updated_at",
    ]


def test_ensure_lancedb_ready_creates_directory_and_both_tables(tmp_path: Path) -> None:
    db_uri = tmp_path / "lancedb"

    connection = ensure_lancedb_ready(
        uri=db_uri,
        qa_table_name="qa_records",
        document_table_name="document_records",
    )

    assert db_uri.exists()
    assert sorted(connection.list_tables().tables) == ["document_records", "qa_records"]

    qa_table = connection.open_table("qa_records")
    document_table = connection.open_table("document_records")

    assert qa_table.schema.names == build_qa_table_schema().names
    assert document_table.schema.names == build_document_table_schema().names


def test_ensure_lancedb_ready_is_idempotent_for_existing_database(tmp_path: Path) -> None:
    db_uri = tmp_path / "lancedb"

    ensure_lancedb_ready(
        uri=db_uri,
        qa_table_name="qa_records",
        document_table_name="document_records",
    )
    connection = ensure_lancedb_ready(
        uri=db_uri,
        qa_table_name="qa_records",
        document_table_name="document_records",
    )

    assert sorted(connection.list_tables().tables) == ["document_records", "qa_records"]
