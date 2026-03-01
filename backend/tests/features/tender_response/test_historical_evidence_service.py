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


async def test_find_historical_evidence_keeps_near_threshold_ssl_conflict_reference() -> None:
    service = HistoricalEvidenceService(
        qa_alignment_repository=FakeQaAlignmentRepository(
            [
                HistoricalReference(
                    record_id="qa-disable",
                    reference_type="qa",
                    question="Is legacy SSL fully disabled for all production traffic?",
                    answer=(
                        "Yes. Legacy SSL is fully disabled for all public and private "
                        "production traffic, and only TLS 1.2 or higher is permitted "
                        "in production environments."
                    ),
                    domain="Security",
                    source_doc="history.csv",
                    alignment_score=0.6944,
                ),
                HistoricalReference(
                    record_id="qa-migration",
                    reference_type="qa",
                    question=(
                        "Do you support SSL and TLS, and what is enforced for production traffic?"
                    ),
                    answer=(
                        "Production traffic to external service endpoints is "
                        "restricted to TLS 1.2 or higher. Legacy SSL is not enabled "
                        "for public production access, though isolated transition "
                        "handling may be used in rare migration scenarios."
                    ),
                    domain="Security",
                    source_doc="history.csv",
                    alignment_score=0.5837,
                ),
            ]
        ),
        document_alignment_repository=FakeDocumentAlignmentRepository([]),
    )

    result = await service.find_historical_evidence(
        TenderQuestion(
            question_id="q-013",
            original_question=(
                "Please confirm that legacy SSL is fully disabled for all "
                "production traffic in the proposed environment."
            ),
            declared_domain="Security",
            source_file_name="tender.csv",
            source_row_index=12,
        ),
        threshold=0.6,
    )

    assert result.matched is True
    assert result.record_id == "qa-disable"
    assert [reference.record_id for reference in result.references] == [
        "qa-disable",
        "qa-migration",
    ]


async def test_find_historical_evidence_keeps_assessable_near_threshold_audit_controls() -> None:
    service = HistoricalEvidenceService(
        qa_alignment_repository=FakeQaAlignmentRepository(
            [
                HistoricalReference(
                    record_id="qa-retention",
                    reference_type="qa",
                    question="How long are audit logs retained?",
                    answer=(
                        "Application and administrative audit logs are retained for "
                        "at least 365 days in the standard regulated deployment profile."
                    ),
                    domain="Security",
                    source_doc="history.csv",
                    alignment_score=0.59,
                ),
                HistoricalReference(
                    record_id="qa-immutable",
                    reference_type="qa",
                    question="Do you support immutable audit logs by default?",
                    answer=(
                        "Audit logs are retained for at least 365 days. Immutable "
                        "storage is deployment-dependent and must not be assumed by default."
                    ),
                    domain="Security",
                    source_doc="history.csv",
                    alignment_score=0.57,
                ),
            ]
        ),
        document_alignment_repository=FakeDocumentAlignmentRepository([]),
    )

    result = await service.find_historical_evidence(
        TenderQuestion(
            question_id="q-007",
            original_question=(
                "Do you provide tamper-proof immutable WORM audit storage for all "
                "administrator actions?"
            ),
            declared_domain="Security",
            source_file_name="tender.csv",
            source_row_index=6,
        ),
        threshold=0.6,
    )

    assert result.matched is True
    assert result.record_id == "qa-retention"
    assert [reference.record_id for reference in result.references] == [
        "qa-retention",
        "qa-immutable",
    ]


async def test_keeps_assessable_near_threshold_isolated_deployment_controls() -> None:
    service = HistoricalEvidenceService(
        qa_alignment_repository=FakeQaAlignmentRepository(
            [
                HistoricalReference(
                    record_id="qa-single-tenant",
                    reference_type="qa",
                    question="Can the platform be deployed as single-tenant?",
                    answer=(
                        "A single-tenant virtual private cloud deployment is "
                        "available for customers with stronger isolation requirements."
                    ),
                    domain="Infrastructure",
                    source_doc="history.csv",
                    alignment_score=0.48,
                ),
                HistoricalReference(
                    record_id="qa-customer-managed",
                    reference_type="qa",
                    question="Can the platform be deployed as single-tenant or customer-managed?",
                    answer=(
                        "Managed SaaS is the preferred model. Single-tenant virtual "
                        "private cloud deployment is available, while customer-managed "
                        "deployment is limited and requires separate scoping through "
                        "professional services."
                    ),
                    domain="Infrastructure",
                    source_doc="history.csv",
                    alignment_score=0.47,
                ),
            ]
        ),
        document_alignment_repository=FakeDocumentAlignmentRepository([]),
    )

    result = await service.find_historical_evidence(
        TenderQuestion(
            question_id="q-101",
            original_question=(
                "Do you support a fully air-gapped on-premises deployment with zero "
                "cloud dependency?"
            ),
            declared_domain="Infrastructure",
            source_file_name="tender.csv",
            source_row_index=0,
        ),
        threshold=0.5,
    )

    assert result.matched is True
    assert result.record_id == "qa-single-tenant"
    assert [reference.record_id for reference in result.references] == [
        "qa-single-tenant",
        "qa-customer-managed",
    ]
