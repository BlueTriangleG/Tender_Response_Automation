from app.features.history_ingest.application.ingest_history_use_case import (
    IngestHistoryUseCase,
)


def test_ingest_history_use_case_does_not_expose_unused_persistence_placeholder() -> None:
    assert not hasattr(IngestHistoryUseCase, "persist_processed_files")
