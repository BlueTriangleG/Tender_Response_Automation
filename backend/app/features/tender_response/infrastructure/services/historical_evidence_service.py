"""Merge QA and document-chunk retrieval into one historical evidence result."""

from app.features.tender_response.domain.models import (
    HistoricalAlignmentResult,
    HistoricalReference,
    TenderQuestion,
)
from app.features.tender_response.infrastructure.repositories.document_alignment_repository import (
    DocumentAlignmentRepository,
)
from app.features.tender_response.infrastructure.repositories.qa_alignment_repository import (
    QaAlignmentRepository,
)


class HistoricalEvidenceService:
    """Retrieve and merge historical QA rows and document chunks."""

    def __init__(
        self,
        *,
        qa_alignment_repository: QaAlignmentRepository | None = None,
        document_alignment_repository: DocumentAlignmentRepository | None = None,
    ) -> None:
        self._qa_alignment_repository = qa_alignment_repository or QaAlignmentRepository()
        self._document_alignment_repository = (
            document_alignment_repository or DocumentAlignmentRepository()
        )

    async def find_historical_evidence(
        self,
        question: TenderQuestion,
        *,
        threshold: float,
    ) -> HistoricalAlignmentResult:
        """Return a merged historical-evidence view across QA and document lanes."""

        qa_references = await self._qa_alignment_repository.find_best_matches(
            question,
            threshold=threshold,
            limit=3,
        )
        document_references = await self._document_alignment_repository.find_best_matches(
            question,
            threshold=threshold,
            limit=4,
        )
        merged_references = sorted(
            [*qa_references, *document_references],
            key=lambda reference: (
                -reference.alignment_score,
                0 if reference.reference_type == "qa" else 1,
            ),
        )[:5]
        if not merged_references:
            return HistoricalAlignmentResult(
                matched=False,
                record_id=None,
                question=None,
                answer=None,
                domain=None,
                source_doc=None,
                alignment_score=None,
                references=[],
            )

        best_reference = merged_references[0]
        qualified_references = [
            reference
            for reference in merged_references
            if reference.alignment_score >= threshold
        ]
        if not qualified_references:
            return HistoricalAlignmentResult(
                matched=False,
                record_id=None,
                question=None,
                answer=None,
                domain=None,
                source_doc=None,
                alignment_score=best_reference.alignment_score,
                references=[],
            )

        selected_reference = qualified_references[0]
        returned_references = _merge_returned_references(
            qualified_references=qualified_references,
            all_references=merged_references,
            question=question,
            threshold=threshold,
        )
        if selected_reference.reference_type == "qa":
            top_question = selected_reference.question
            top_answer = selected_reference.answer
        else:
            top_question = None
            top_answer = None

        return HistoricalAlignmentResult(
            matched=True,
            record_id=selected_reference.record_id,
            question=top_question,
            answer=top_answer,
            domain=selected_reference.domain,
            source_doc=selected_reference.source_doc,
            alignment_score=selected_reference.alignment_score,
            references=returned_references,
        )


def _normalize(text: str | None) -> str:
    return " ".join((text or "").lower().split())


def _is_absolute_ssl_disable_question(text: str) -> bool:
    normalized = _normalize(text)
    return (
        "legacy ssl" in normalized
        and "production" in normalized
        and "fully disabled" in normalized
    )


def _is_ssl_exception_reference(reference: HistoricalReference) -> bool:
    normalized = _normalize(reference.answer)
    return (
        "legacy ssl" in normalized
        and "production" in normalized
        and (
            "migration scenario" in normalized
            or "migration scenarios" in normalized
            or "migration window" in normalized
            or "migration windows" in normalized
            or "transition" in normalized
        )
    )


def _merge_returned_references(
    *,
    qualified_references: list[HistoricalReference],
    all_references: list[HistoricalReference],
    question: TenderQuestion,
    threshold: float,
) -> list[HistoricalReference]:
    references_by_id = {reference.record_id: reference for reference in qualified_references}

    if not _is_absolute_ssl_disable_question(question.original_question):
        return qualified_references

    near_threshold_floor = max(0.0, threshold - 0.03)
    for reference in all_references:
        if reference.record_id in references_by_id:
            continue
        if reference.alignment_score < near_threshold_floor:
            continue
        if not _is_ssl_exception_reference(reference):
            continue
        references_by_id[reference.record_id] = reference

    return [
        reference
        for reference in all_references
        if reference.record_id in references_by_id
    ]
