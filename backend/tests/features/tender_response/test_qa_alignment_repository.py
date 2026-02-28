from pathlib import Path

from app.db.lancedb_client import ensure_lancedb_ready
from app.features.tender_response.domain.models import TenderQuestion
from app.features.tender_response.infrastructure.repositories.qa_alignment_repository import (
    QaAlignmentRepository,
)


class FakeEmbeddingsClient:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[list[str]] = []

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return self.vectors


async def test_find_best_match_returns_alignment_when_score_is_above_threshold(
    tmp_path: Path,
) -> None:
    connection = ensure_lancedb_ready(uri=tmp_path / "lancedb")
    table = connection.open_table("qa_records")
    expected_text = (
        "Question: Do you support TLS 1.2 or higher?\n"
        "Answer: Yes. Production traffic is restricted to TLS 1.2 or higher.\n"
        "Domain: Security"
    )
    table.add(
        [
            {
                "id": "qa-1",
                "domain": "Security",
                "question": "Do you support TLS 1.2 or higher?",
                "answer": "Yes. Production traffic is restricted to TLS 1.2 or higher.",
                "text": expected_text,
                "vector": [1.0] + [0.0] * 1535,
                "client": None,
                "source_doc": "history.csv",
                "tags": [],
                "risk_topics": [],
                "created_at": "2026-02-28T00:00:00+00:00",
            }
        ]
    )
    repository = QaAlignmentRepository(
        connection=connection,
        embeddings_client=FakeEmbeddingsClient([[1.0] + [0.0] * 1535]),
    )

    result = await repository.find_best_match(
        TenderQuestion(
            question_id="q-001",
            original_question="Do you support TLS 1.2 or higher?",
            declared_domain="Security",
            source_file_name="tender.csv",
            source_row_index=0,
        ),
        threshold=0.8,
    )

    assert result.matched is True
    assert result.record_id == "qa-1"
    assert result.answer.startswith("Yes.")
    assert result.source_doc == "history.csv"
    assert result.alignment_score == 1.0


async def test_find_best_match_returns_no_match_when_score_is_below_threshold(
    tmp_path: Path,
) -> None:
    connection = ensure_lancedb_ready(uri=tmp_path / "lancedb")
    table = connection.open_table("qa_records")
    expected_text = (
        "Question: Do you support TLS 1.2 or higher?\n"
        "Answer: Yes.\n"
        "Domain: Security"
    )
    table.add(
        [
            {
                "id": "qa-1",
                "domain": "Security",
                "question": "Do you support TLS 1.2 or higher?",
                "answer": "Yes.",
                "text": expected_text,
                "vector": [1.0] + [0.0] * 1535,
                "client": None,
                "source_doc": "history.csv",
                "tags": [],
                "risk_topics": [],
                "created_at": "2026-02-28T00:00:00+00:00",
            }
        ]
    )
    repository = QaAlignmentRepository(
        connection=connection,
        embeddings_client=FakeEmbeddingsClient([[0.0, 1.0] + [0.0] * 1534]),
    )

    result = await repository.find_best_match(
        TenderQuestion(
            question_id="q-002",
            original_question="Do you support single sign-on?",
            declared_domain="Architecture",
            source_file_name="tender.csv",
            source_row_index=1,
        ),
        threshold=0.9,
    )

    assert result.matched is False
    assert result.record_id is None
    assert result.answer is None


async def test_find_best_match_returns_no_match_when_table_is_empty(tmp_path: Path) -> None:
    connection = ensure_lancedb_ready(uri=tmp_path / "lancedb")
    repository = QaAlignmentRepository(
        connection=connection,
        embeddings_client=FakeEmbeddingsClient([[1.0] + [0.0] * 1535]),
    )

    result = await repository.find_best_match(
        TenderQuestion(
            question_id="q-003",
            original_question="Are backups encrypted at rest?",
            declared_domain="Compliance",
            source_file_name="tender.csv",
            source_row_index=2,
        ),
        threshold=0.8,
    )

    assert result.matched is False
