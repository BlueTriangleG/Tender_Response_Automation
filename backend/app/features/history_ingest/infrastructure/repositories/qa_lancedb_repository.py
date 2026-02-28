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
