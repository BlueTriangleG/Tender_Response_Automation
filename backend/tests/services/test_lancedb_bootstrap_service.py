from pathlib import Path

from app.services.lancedb_bootstrap_service import bootstrap_lancedb


def test_bootstrap_lancedb_calls_readiness_function(monkeypatch) -> None:
    captured: dict[str, Path | str] = {}

    def fake_ensure_lancedb_ready(
        uri: str | Path | None = None,
        qa_table_name: str | None = None,
        document_table_name: str | None = None,
    ) -> object:
        captured["uri"] = Path(uri) if uri is not None else Path()
        captured["qa_table_name"] = qa_table_name or ""
        captured["document_table_name"] = document_table_name or ""
        return object()

    monkeypatch.setattr(
        "app.services.lancedb_bootstrap_service.ensure_lancedb_ready",
        fake_ensure_lancedb_ready,
    )

    bootstrap_lancedb(
        uri=Path("/tmp/test-lancedb"),
        qa_table_name="qa_records",
        document_table_name="document_records",
    )

    assert captured == {
        "uri": Path("/tmp/test-lancedb"),
        "qa_table_name": "qa_records",
        "document_table_name": "document_records",
    }
