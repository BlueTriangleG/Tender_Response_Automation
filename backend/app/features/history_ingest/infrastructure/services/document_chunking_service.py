"""Deterministic chunking for non-tabular historical evidence files."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from app.features.history_ingest.domain.document_chunk import DocumentChunkRecord
from app.features.history_ingest.schemas.responses import ParsedFilePayload


class DocumentChunkingService:
    """Normalize source text and split it into stable chunks for LanceDB."""

    def __init__(self, chunk_size: int = 1000, overlap: int = 150) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap

    def build_chunks(self, payload: ParsedFilePayload) -> list[DocumentChunkRecord]:
        """Convert one parsed history file into deterministic document chunks."""

        normalized_text = self._normalize_text(payload)
        if not normalized_text:
            return []

        document_id = hashlib.sha256(f"{payload.file_name}\n{normalized_text}".encode()).hexdigest()
        timestamp = datetime.now(UTC).isoformat()

        chunks: list[DocumentChunkRecord] = []
        for chunk_index, chunk_text in enumerate(self._split_text(normalized_text)):
            chunk_id = hashlib.sha256(f"{document_id}:{chunk_index}".encode()).hexdigest()
            chunks.append(
                DocumentChunkRecord(
                    id=chunk_id,
                    document_id=document_id,
                    document_type=payload.parsed_kind,
                    title=payload.file_name,
                    text=chunk_text,
                    source_doc=payload.file_name,
                    chunk_index=chunk_index,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
        return chunks

    def _normalize_text(self, payload: ParsedFilePayload) -> str:
        raw_text = payload.raw_text or ""
        if payload.extension == ".json" and payload.structured_data is not None:
            raw_text = json.dumps(
                payload.structured_data,
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )

        normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n").strip()
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized

    def _split_text(self, text: str) -> list[str]:
        if len(text) <= self._chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0
        text_length = len(text)
        while start < text_length:
            end = min(text_length, start + self._chunk_size)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= text_length:
                break
            start = max(end - self._overlap, start + 1)
        return chunks
