"""Dependency providers scoped to the history-ingest feature."""

from app.features.history_ingest.application.ingest_history_use_case import IngestHistoryUseCase


def get_history_ingest_use_case() -> IngestHistoryUseCase:
    """Build a history-ingest use case for request handlers."""

    return IngestHistoryUseCase()
