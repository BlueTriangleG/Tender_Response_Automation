"""Merge QA and document-chunk retrieval into one historical evidence result."""

import re

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
            reference for reference in merged_references if reference.alignment_score >= threshold
        ]
        if qualified_references:
            selected_reference = qualified_references[0]
            returned_references = _merge_returned_references(
                qualified_references=qualified_references,
                all_references=merged_references,
                question=question,
                threshold=threshold,
            )
        else:
            returned_references = _select_assessable_near_threshold_references(
                question=question,
                all_references=merged_references,
                threshold=threshold,
            )
            if not returned_references:
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
            selected_reference = returned_references[0]
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


def _tokenize(text: str | None) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", _normalize(text))
        if len(token) >= 4 and token not in _STOPWORDS
    }


def _is_absolute_ssl_disable_question(text: str) -> bool:
    normalized = _normalize(text)
    return (
        "legacy ssl" in normalized and "production" in normalized and "fully disabled" in normalized
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


def _is_audit_immutability_question(text: str) -> bool:
    normalized = _normalize(text)
    return "audit" in normalized and (
        "immutable" in normalized or "worm" in normalized or "tamper-proof" in normalized
    )


def _is_audit_controls_reference(reference: HistoricalReference) -> bool:
    normalized = _normalize(
        " ".join((reference.question, reference.answer, reference.excerpt or ""))
    )
    return "audit" in normalized and (
        "immutable" in normalized
        or "retained" in normalized
        or "retention" in normalized
        or "administrator" in normalized
    )


def _has_immutability_anchor(reference: HistoricalReference) -> bool:
    normalized = _normalize(
        " ".join((reference.question, reference.answer, reference.excerpt or ""))
    )
    return (
        "immutable" in normalized
        or "worm" in normalized
        or "tamper-proof" in normalized
        or "tamper proof" in normalized
    )


def _is_air_gapped_deployment_question(text: str) -> bool:
    normalized = _normalize(text)
    return (
        "air-gapped" in normalized
        or "air gapped" in normalized
        or "zero cloud" in normalized
        or "on-prem" in normalized
        or "on premises" in normalized
    )


def _is_isolated_deployment_reference(reference: HistoricalReference) -> bool:
    normalized = _normalize(
        " ".join((reference.question, reference.answer, reference.excerpt or ""))
    )
    return (
        "single-tenant" in normalized
        or "customer-managed" in normalized
        or "customer managed" in normalized
        or "isolation" in normalized
        or "private cloud" in normalized
        or "vpc" in normalized
    )


def _is_assessable_near_threshold_reference(
    *,
    question: TenderQuestion,
    reference: HistoricalReference,
    threshold: float,
) -> bool:
    if reference.alignment_score < max(0.0, threshold - 0.05):
        return False

    if _is_audit_immutability_question(question.original_question):
        return _is_audit_controls_reference(reference)

    if _is_air_gapped_deployment_question(question.original_question):
        return _is_isolated_deployment_reference(reference)

    question_tokens = _tokenize(question.original_question)
    reference_tokens = _tokenize(
        " ".join((reference.question, reference.answer, reference.excerpt or ""))
    )
    return len(question_tokens & reference_tokens) >= 2


def _select_assessable_near_threshold_references(
    *,
    question: TenderQuestion,
    all_references: list[HistoricalReference],
    threshold: float,
) -> list[HistoricalReference]:
    candidates = [
        reference
        for reference in all_references
        if _is_assessable_near_threshold_reference(
            question=question,
            reference=reference,
            threshold=threshold,
        )
    ]

    if _is_audit_immutability_question(question.original_question):
        if not any(_has_immutability_anchor(reference) for reference in candidates):
            return []

    return candidates


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

    return [reference for reference in all_references if reference.record_id in references_by_id]


_STOPWORDS = {
    "about",
    "after",
    "before",
    "being",
    "between",
    "confirm",
    "could",
    "does",
    "during",
    "environment",
    "every",
    "higher",
    "into",
    "long",
    "once",
    "only",
    "please",
    "proposed",
    "provide",
    "question",
    "restricted",
    "should",
    "support",
    "that",
    "their",
    "this",
    "through",
    "what",
    "when",
    "whether",
    "with",
    "within",
}
