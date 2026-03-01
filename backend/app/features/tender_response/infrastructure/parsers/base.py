"""Shared parser contracts for tender-response uploads."""

from __future__ import annotations

from typing import Protocol

from app.features.tender_response.domain.models import TenderTabularParseResult


class TenderUploadParser(Protocol):
    """Contract for parsers that normalize uploaded tender files into questions."""

    def parse_bytes(
        self,
        raw_bytes: bytes,
        *,
        source_file_name: str,
    ) -> TenderTabularParseResult: ...
