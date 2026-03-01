from app.features.tender_response.domain.models import HistoricalReference, TenderQuestion
from app.features.tender_response.infrastructure.services.historical_evidence_service import (
    HistoricalEvidenceService,
)


class FakeQaAlignmentRepository:
    def __init__(self, references: list[HistoricalReference]) -> None:
        self.references = references
        self.calls: list[tuple[str, float]] = []

    async def find_best_matches(
        self,
        question: TenderQuestion,
        *,
        threshold: float,
        limit: int = 3,
    ) -> list[HistoricalReference]:
        self.calls.append((question.question_id, threshold))
        return self.references[:limit]


class FakeDocumentAlignmentRepository:
    def __init__(self, references: list[HistoricalReference]) -> None:
        self.references = references
        self.calls: list[tuple[str, float]] = []

    async def find_best_matches(
        self,
        question: TenderQuestion,
        *,
        threshold: float,
        limit: int = 4,
    ) -> list[HistoricalReference]:
        self.calls.append((question.question_id, threshold))
        return self.references[:limit]


async def test_find_historical_evidence_merges_qa_and_document_references() -> None:
    service = HistoricalEvidenceService(
        qa_alignment_repository=FakeQaAlignmentRepository(
            [
                HistoricalReference(
                    record_id="qa-1",
                    reference_type="qa",
                    question="What are your recovery targets?",
                    answer="Production RPO is 15 minutes and RTO is 4 hours.",
                    domain="Operations",
                    source_doc="history.xlsx",
                    alignment_score=0.94,
                )
            ]
        ),
        document_alignment_repository=FakeDocumentAlignmentRepository(
            [
                HistoricalReference(
                    record_id="doc-1#0",
                    reference_type="document_chunk",
                    question="",
                    answer="",
                    excerpt="Quarterly recovery exercises are documented and reviewed.",
                    chunk_index=0,
                    domain="Operations",
                    source_doc="operations_playbook.txt",
                    alignment_score=0.89,
                )
            ]
        ),
    )

    result = await service.find_historical_evidence(
        TenderQuestion(
            question_id="q-001",
            original_question="Describe your recovery capabilities.",
            declared_domain="Operations",
            source_file_name="tender.csv",
            source_row_index=0,
        ),
        threshold=0.8,
    )

    assert result.matched is True
    assert result.record_id == "qa-1"
    assert [reference.reference_type for reference in result.references] == [
        "qa",
        "document_chunk",
    ]
    assert result.references[1].excerpt == (
        "Quarterly recovery exercises are documented and reviewed."
    )


async def test_find_historical_evidence_marks_document_only_match_without_fake_answer() -> None:
    service = HistoricalEvidenceService(
        qa_alignment_repository=FakeQaAlignmentRepository([]),
        document_alignment_repository=FakeDocumentAlignmentRepository(
            [
                HistoricalReference(
                    record_id="doc-2#1",
                    reference_type="document_chunk",
                    question="",
                    answer="",
                    excerpt="Customer data is encrypted at rest with managed keys.",
                    chunk_index=1,
                    domain="Security",
                    source_doc="security_notes.md",
                    alignment_score=0.91,
                )
            ]
        ),
    )

    result = await service.find_historical_evidence(
        TenderQuestion(
            question_id="q-002",
            original_question="How do you protect customer data at rest?",
            declared_domain="Security",
            source_file_name="tender.csv",
            source_row_index=1,
        ),
        threshold=0.8,
    )

    assert result.matched is True
    assert result.record_id == "doc-2#1"
    assert result.question is None
    assert result.answer is None
    assert result.source_doc == "security_notes.md"
    assert result.references[0].reference_type == "document_chunk"


async def test_find_historical_evidence_drops_below_threshold_near_misses() -> None:
    service = HistoricalEvidenceService(
        qa_alignment_repository=FakeQaAlignmentRepository(
            [
                HistoricalReference(
                    record_id="qa-weak",
                    reference_type="qa",
                    question="How long are audit logs retained?",
                    answer=(
                        "Application and administrative audit logs are retained for "
                        "at least 365 days in the standard regulated deployment profile."
                    ),
                    domain="Security",
                    source_doc="history.csv",
                    alignment_score=0.59,
                )
            ]
        ),
        document_alignment_repository=FakeDocumentAlignmentRepository(
            [
                HistoricalReference(
                    record_id="doc-weak#0",
                    reference_type="document_chunk",
                    question="",
                    answer="",
                    excerpt="Audit logs can be exported to customer SIEM platforms.",
                    chunk_index=0,
                    domain="Security",
                    source_doc="security_notes.md",
                    alignment_score=0.58,
                )
            ]
        ),
    )

    result = await service.find_historical_evidence(
        TenderQuestion(
            question_id="q-007",
            original_question=(
                "Do you provide immutable audit logs for administrator actions, and "
                "how long are they retained?"
            ),
            declared_domain="Security",
            source_file_name="tender.csv",
            source_row_index=6,
        ),
        threshold=0.6,
    )

    assert result.matched is False
    assert result.record_id is None
    assert result.references == []
    assert result.alignment_score == 0.59
