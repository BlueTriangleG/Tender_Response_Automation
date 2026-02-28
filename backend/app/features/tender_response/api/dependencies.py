"""Dependency providers scoped to the tender-response feature."""

from functools import lru_cache

from app.features.tender_response.application.process_tender_csv_use_case import (
    ProcessTenderCsvUseCase,
)


@lru_cache
def get_process_tender_csv_use_case() -> ProcessTenderCsvUseCase:
    """Cache the tender-response use case and its underlying workflow graph."""

    return ProcessTenderCsvUseCase()
