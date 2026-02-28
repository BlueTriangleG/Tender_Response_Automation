"""Compatibility re-export for the CSV QA normalization domain service."""

from app.features.history_ingest.domain.csv_qa_normalization import (
    CsvQaNormalizationResult,
    CsvQaNormalizationService,
    NormalizedQaRecord,
)

__all__ = [
    "CsvQaNormalizationResult",
    "CsvQaNormalizationService",
    "NormalizedQaRecord",
]
