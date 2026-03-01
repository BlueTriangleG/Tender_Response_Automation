"""Dependency providers scoped to the tender-response feature."""

from functools import lru_cache

from app.features.tender_response.application.tender_response_runner import (
    TenderResponseRunner,
)


@lru_cache
def get_tender_response_runner() -> TenderResponseRunner:
    """Cache the tender-response runner and its workflow registry."""

    return TenderResponseRunner()
