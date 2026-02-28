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
    assert [reference.record_id for reference in result.references] == ["qa-1"]
    assert result.references[0].source_doc == "history.csv"


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


async def test_find_best_match_returns_up_to_top_three_qualified_references(
    tmp_path: Path,
) -> None:
    connection = ensure_lancedb_ready(uri=tmp_path / "lancedb")
    table = connection.open_table("qa_records")
    rows = [
        {
            "id": "qa-1",
            "domain": "Security",
            "question": "TLS question one",
            "answer": "TLS answer one",
            "text": "Question: TLS question one\nAnswer: TLS answer one\nDomain: Security",
            "vector": [1.0] + [0.0] * 1535,
            "client": None,
            "source_doc": "history-1.csv",
            "tags": [],
            "risk_topics": [],
            "created_at": "2026-02-28T00:00:00+00:00",
        },
        {
            "id": "qa-2",
            "domain": "Security",
            "question": "TLS question two",
            "answer": "TLS answer two",
            "text": "Question: TLS question two\nAnswer: TLS answer two\nDomain: Security",
            "vector": [0.95] + [0.0] * 1535,
            "client": None,
            "source_doc": "history-2.csv",
            "tags": [],
            "risk_topics": [],
            "created_at": "2026-02-28T00:00:00+00:00",
        },
        {
            "id": "qa-3",
            "domain": "Security",
            "question": "TLS question three",
            "answer": "TLS answer three",
            "text": "Question: TLS question three\nAnswer: TLS answer three\nDomain: Security",
            "vector": [0.9] + [0.0] * 1535,
            "client": None,
            "source_doc": "history-3.csv",
            "tags": [],
            "risk_topics": [],
            "created_at": "2026-02-28T00:00:00+00:00",
        },
        {
            "id": "qa-4",
            "domain": "Security",
            "question": "TLS question four",
            "answer": "TLS answer four",
            "text": "Question: TLS question four\nAnswer: TLS answer four\nDomain: Security",
            "vector": [0.85] + [0.0] * 1535,
            "client": None,
            "source_doc": "history-4.csv",
            "tags": [],
            "risk_topics": [],
            "created_at": "2026-02-28T00:00:00+00:00",
        },
    ]
    table.add(rows)
    repository = QaAlignmentRepository(
        connection=connection,
        embeddings_client=FakeEmbeddingsClient([[1.0] + [0.0] * 1535]),
    )

    result = await repository.find_best_match(
        TenderQuestion(
            question_id="q-004",
            original_question="Do you support TLS?",
            declared_domain="Security",
            source_file_name="tender.csv",
            source_row_index=3,
        ),
        threshold=0.8,
    )

    assert result.matched is True
    assert [reference.record_id for reference in result.references] == ["qa-1", "qa-2", "qa-3"]
