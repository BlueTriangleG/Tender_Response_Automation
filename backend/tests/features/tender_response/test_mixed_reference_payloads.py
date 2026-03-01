from app.features.tender_response.domain.models import HistoricalReference
from app.features.tender_response.infrastructure.workflows.common.builders import (
    build_reference_payload,
)
from app.features.tender_response.schemas.responses import QuestionReference


def test_build_reference_payload_marks_qa_and_document_chunk_reference_types() -> None:
    payload = build_reference_payload(
        [
            HistoricalReference(
                record_id="qa-1",
                reference_type="qa",
                question="Do you support TLS 1.2 or higher?",
                answer="Yes. Production traffic is restricted to TLS 1.2 or higher.",
                domain="Security",
                source_doc="history.xlsx",
                alignment_score=0.95,
            ),
            HistoricalReference(
                record_id="doc-1#0",
                reference_type="document_chunk",
                question="",
                answer="",
                excerpt="Primary production backups run every four hours.",
                chunk_index=0,
                domain="Operations",
                source_doc="operations_playbook.txt",
                alignment_score=0.82,
            ),
        ],
        used_reference_ids={"doc-1#0"},
    )

    assert payload[0].reference_type == "qa"
    assert payload[0].matched_question == "Do you support TLS 1.2 or higher?"
    assert payload[1].reference_type == "document_chunk"
    assert payload[1].excerpt == "Primary production backups run every four hours."
    assert payload[1].chunk_index == 0
    assert payload[1].matched_question == ""
    assert payload[1].matched_answer == ""
    assert payload[1].used_for_answer is True


def test_question_reference_accepts_document_chunk_payload() -> None:
    payload = QuestionReference(
        alignment_record_id="doc-1#0",
        reference_type="document_chunk",
        alignment_score=0.82,
        source_doc="operations_playbook.txt",
        matched_question="",
        matched_answer="",
        excerpt="Primary production backups run every four hours.",
        chunk_index=0,
        used_for_answer=True,
    )

    assert payload.reference_type == "document_chunk"
    assert payload.excerpt == "Primary production backups run every four hours."
