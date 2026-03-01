from pathlib import Path

from app.db.lancedb_client import ensure_lancedb_ready
from app.features.tender_response.domain.models import TenderQuestion
from app.features.tender_response.infrastructure.repositories.document_alignment_repository import (
    DocumentAlignmentRepository,
)


class FakeEmbeddingsClient:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[list[str]] = []

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return self.vectors


async def test_find_best_matches_returns_no_match_when_document_table_is_empty(
    tmp_path: Path,
) -> None:
    connection = ensure_lancedb_ready(uri=tmp_path / "lancedb")
    repository = DocumentAlignmentRepository(
        connection=connection,
        embeddings_client=FakeEmbeddingsClient([[1.0] + [0.0] * 1535]),
    )

    matches = await repository.find_best_matches(
        TenderQuestion(
            question_id="q-001",
            original_question="Describe your disaster recovery controls.",
            declared_domain="Operations",
            source_file_name="tender.csv",
            source_row_index=0,
        ),
        threshold=0.8,
    )

    assert matches == []


async def test_find_best_matches_maps_document_chunk_fields_and_caps_results(
    tmp_path: Path,
) -> None:
    connection = ensure_lancedb_ready(uri=tmp_path / "lancedb")
    table = connection.open_table("document_records")
    table.add(
        [
            {
                "id": "doc-1#0",
                "document_id": "doc-1",
                "document_type": "text/plain",
                "domain": "Operations",
                "title": "Operations Playbook",
                "text": "Primary production backups run every four hours.",
                "vector": [1.0] + [0.0] * 1535,
                "source_doc": "operations_playbook.txt",
                "tags": [],
                "risk_topics": [],
                "client": None,
                "chunk_index": 0,
                "created_at": "2026-02-28T00:00:00+00:00",
                "updated_at": None,
            },
            {
                "id": "doc-1#1",
                "document_id": "doc-1",
                "document_type": "text/plain",
                "domain": "Operations",
                "title": "Operations Playbook",
                "text": "Recovery exercises are run quarterly with tracked actions.",
                "vector": [0.95] + [0.0] * 1535,
                "source_doc": "operations_playbook.txt",
                "tags": [],
                "risk_topics": [],
                "client": None,
                "chunk_index": 1,
                "created_at": "2026-02-28T00:00:00+00:00",
                "updated_at": None,
            },
            {
                "id": "doc-1#2",
                "document_id": "doc-1",
                "document_type": "text/plain",
                "domain": "Operations",
                "title": "Operations Playbook",
                "text": "Incident response plans are reviewed after major incidents.",
                "vector": [0.9] + [0.0] * 1535,
                "source_doc": "operations_playbook.txt",
                "tags": [],
                "risk_topics": [],
                "client": None,
                "chunk_index": 2,
                "created_at": "2026-02-28T00:00:00+00:00",
                "updated_at": None,
            },
        ]
    )
    repository = DocumentAlignmentRepository(
        connection=connection,
        embeddings_client=FakeEmbeddingsClient([[1.0] + [0.0] * 1535]),
    )

    matches = await repository.find_best_matches(
        TenderQuestion(
            question_id="q-002",
            original_question="Describe your backup and recovery process.",
            declared_domain="Operations",
            source_file_name="tender.csv",
            source_row_index=1,
        ),
        threshold=0.5,
        limit=2,
    )

    assert [match.record_id for match in matches] == ["doc-1#0", "doc-1#1"]
    assert all(match.reference_type == "document_chunk" for match in matches)
    assert matches[0].source_doc == "operations_playbook.txt"
    assert matches[0].excerpt == "Primary production backups run every four hours."
    assert matches[0].chunk_index == 0
    assert matches[0].question == ""
    assert matches[0].answer == ""
    assert 0.0 < matches[0].alignment_score <= 1.0
