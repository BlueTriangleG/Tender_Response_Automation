from importlib import import_module


def test_history_ingest_feature_modules_are_importable() -> None:
    modules = [
        "app.features.history_ingest.api.routes",
        "app.features.history_ingest.api.dependencies",
        "app.features.history_ingest.application.ingest_history_use_case",
        "app.features.history_ingest.domain.csv_column_mapping",
        "app.features.history_ingest.domain.csv_qa_normalization",
        "app.features.history_ingest.infrastructure.file_processing_service",
        "app.features.history_ingest.infrastructure.repositories.qa_lancedb_repository",
        "app.features.history_ingest.infrastructure.services.csv_column_detection_service",
        "app.features.history_ingest.schemas.requests",
        "app.features.history_ingest.schemas.responses",
    ]

    for module_name in modules:
        imported = import_module(module_name)
        assert imported is not None
