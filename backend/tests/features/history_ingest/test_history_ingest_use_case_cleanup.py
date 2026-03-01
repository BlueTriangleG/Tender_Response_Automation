from app.features.history_ingest.api.dependencies import get_history_ingest_use_case
from app.features.history_ingest.application.ingest_history_use_case import (
    IngestHistoryUseCase,
)


def test_ingest_history_use_case_does_not_expose_unused_persistence_placeholder() -> None:
    assert not hasattr(IngestHistoryUseCase, "persist_processed_files")


def test_ingest_history_use_case_has_no_lazy_getter_methods() -> None:
    lazy_getters = [
        "_get_csv_column_detection_service",
        "_get_csv_qa_normalization_service",
        "_get_qa_embedding_service",
        "_get_qa_repository",
        "_get_document_chunking_service",
        "_get_document_repository",
    ]
    for method in lazy_getters:
        assert not hasattr(IngestHistoryUseCase, method), f"Lazy getter still present: {method}"


def test_get_history_ingest_use_case_returns_fully_wired_instance() -> None:
    use_case = get_history_ingest_use_case()

    assert use_case._file_processing_service is not None
    assert use_case._csv_column_detection_service is not None
    assert use_case._csv_qa_normalization_service is not None
    assert use_case._qa_embedding_service is not None
    assert use_case._qa_repository is not None
    assert use_case._document_chunking_service is not None
    assert use_case._document_repository is not None
