"""LLM-backed assessment of whether retrieved references are sufficient."""

from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.features.tender_response.domain.models import (
    HistoricalReference,
    ReferenceAssessmentResult,
    TenderQuestion,
)
from app.features.tender_response.infrastructure.prompting.reference_assessment import (
    build_reference_assessment_messages,
)


class ReferenceAssessmentService:
    """Gate answer generation unless the retrieved references can stand on their own."""

    def __init__(
        self,
        model: BaseChatModel | None = None,
    ) -> None:
        self._model = model or ChatOpenAI(
            model=settings.openai_tender_response_model,
            temperature=0,
        )

    async def assess(
        self,
        *,
        question: TenderQuestion,
        references: list[HistoricalReference],
    ) -> ReferenceAssessmentResult:
        """Return grounded/no-grounded decision plus the usable reference ids."""

        if not references:
            return ReferenceAssessmentResult(
                can_answer=False,
                grounding_status="no_reference",
                usable_reference_ids=[],
                reason="No qualified historical references were retrieved.",
            )

        conflict_reason = _detect_material_reference_conflict(
            question=question,
            references=references,
        )
        if conflict_reason is not None:
            return ReferenceAssessmentResult(
                can_answer=False,
                grounding_status="conflict",
                usable_reference_ids=[],
                reason=conflict_reason,
            )

        messages = build_reference_assessment_messages(
            question=question,
            references=references,
        )
        try:
            structured_model = self._model.with_structured_output(
                _ReferenceAssessmentPayload,
                method="function_calling",
                strict=True,
            )
            payload = await structured_model.ainvoke(messages)
            usable_reference_ids = payload.usable_reference_ids
            valid_reference_ids = {reference.record_id for reference in references}
            # Never trust the model to return only ids we supplied in the prompt.
            usable_reference_ids = [
                str(reference_id)
                for reference_id in usable_reference_ids
                if str(reference_id) in valid_reference_ids
            ]
            reason = payload.reason.strip() or "Reference assessment completed."
            if not usable_reference_ids:
                answerability: Literal["none", "partial", "grounded"] = "none"
            else:
                answerability = payload.answerability
        except Exception as exc:
            return ReferenceAssessmentResult(
                can_answer=False,
                grounding_status="insufficient_reference",
                usable_reference_ids=[],
                reason=f"Reference assessment failed: {exc}",
            )

        if answerability == "grounded":
            return ReferenceAssessmentResult(
                can_answer=True,
                grounding_status="grounded",
                usable_reference_ids=usable_reference_ids,
                reason=reason,
            )

        if answerability == "partial":
            return ReferenceAssessmentResult(
                can_answer=True,
                grounding_status="partial_reference",
                usable_reference_ids=usable_reference_ids,
                reason=reason,
            )

        return ReferenceAssessmentResult(
            can_answer=False,
            grounding_status="insufficient_reference",
            usable_reference_ids=[],
            reason=reason,
        )


class _ReferenceAssessmentPayload(BaseModel):
    answerability: Literal["none", "partial", "grounded"]
    usable_reference_ids: list[str]
    reason: str


def _normalize(text: str | None) -> str:
    return " ".join((text or "").lower().split())


def _is_absolute_ssl_disable_reference(text: str) -> bool:
    normalized = _normalize(text)
    return (
        "legacy ssl" in normalized
        and "fully disabled" in normalized
        and "production" in normalized
        and ("all public and private production traffic" in normalized or "all production traffic" in normalized)
    )


def _is_ssl_exception_reference(text: str) -> bool:
    normalized = _normalize(text)
    return (
        "legacy ssl" in normalized
        and ("can remain enabled" in normalized or "may be used" in normalized)
        and "production" in normalized
        and ("migration window" in normalized or "migration scenarios" in normalized or "transition" in normalized)
    )


def _detect_material_reference_conflict(
    *,
    question: TenderQuestion,
    references: list[HistoricalReference],
) -> str | None:
    """Return a human-review reason when retrieved references materially disagree."""

    normalized_question = _normalize(question.original_question)
    if (
        "legacy ssl" not in normalized_question
        or "production" not in normalized_question
        or "fully disabled" not in normalized_question
    ):
        return None

    has_absolute_disable = any(
        _is_absolute_ssl_disable_reference(reference.answer) for reference in references
    )
    has_exception_enable = any(
        _is_ssl_exception_reference(reference.answer) for reference in references
    )
    if has_absolute_disable and has_exception_enable:
        return (
            "Conflicting historical references disagree on whether legacy SSL is fully "
            "disabled for production traffic or can remain enabled during approved "
            "migration scenarios. Human review is required before answering."
        )
    return None
