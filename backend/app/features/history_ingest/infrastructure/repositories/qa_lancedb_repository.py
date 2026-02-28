from typing import Any

from lancedb.db import DBConnection

from app.core.config import settings
from app.db.lancedb_client import ensure_lancedb_ready


class QaLanceDbRepository:
    def __init__(self, connection: DBConnection | None = None) -> None:
        self._connection = connection or ensure_lancedb_ready()
        self._table_name = settings.lancedb_qa_table_name

    def upsert_records(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return

        table = self._connection.open_table(self._table_name)
        (
            table.merge_insert("id")
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute(records)
        )

    def get_existing_record_ids(self, record_ids: list[str]) -> set[str]:
        if not record_ids:
            return set()

        table = self._connection.open_table(self._table_name)
        wanted_ids = set(record_ids)
        existing_ids = {
            row["id"]
            for row in table.to_arrow().to_pylist()
            if row.get("id") in wanted_ids
        }
        return existing_ids
