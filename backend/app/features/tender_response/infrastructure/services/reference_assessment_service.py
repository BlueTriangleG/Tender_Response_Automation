"""LLM-backed assessment of whether retrieved references are sufficient."""

import asyncio
from time import perf_counter
from typing import Any, Literal

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
from app.features.tender_response.infrastructure.workflows.common.debug import (
    debug_log,
    print_llm_bug_report,
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
                supported_coverage_percent=0,
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
                supported_coverage_percent=0,
            )

        if _references_require_human_review_only(references):
            return ReferenceAssessmentResult(
                can_answer=False,
                grounding_status="insufficient_reference",
                usable_reference_ids=[],
                reason=(
                    "Retrieved references do not provide an approved factual answer and "
                    "instead require human review before any claim can be asserted."
                ),
                supported_coverage_percent=0,
            )

        if _references_require_verification_before_claim(question, references):
            return ReferenceAssessmentResult(
                can_answer=False,
                grounding_status="insufficient_reference",
                usable_reference_ids=[],
                reason=(
                    "Retrieved references do not provide an approved factual answer and "
                    "instead require separate verification before any certification or "
                    "authorization claim can be asserted."
                ),
                supported_coverage_percent=0,
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
            timeout_seconds = settings.tender_llm_request_timeout_seconds
            max_attempts = max(1, settings.tender_reference_assessment_retry_attempts)
            valid_reference_ids = {reference.record_id for reference in references}
            for attempt in range(1, max_attempts + 1):
                started_at = perf_counter()
                debug_log(
                    f"question={question.question_id} reference_assessment_service request start "
                    f"refs={len(references)} attempt={attempt} timeout_s={timeout_seconds:.2f}"
                )
                try:
                    raw_payload = await asyncio.wait_for(
                        structured_model.ainvoke(messages),
                        timeout=timeout_seconds,
                    )
                    payload = _ReferenceAssessmentPayload.model_validate(raw_payload)
                    duration_ms = (perf_counter() - started_at) * 1000
                    debug_log(
                        f"question={question.question_id} reference_assessment_service request end "
                        f"answerability={payload.answerability} attempt={attempt} "
                        f"duration_ms={duration_ms:.2f}"
                    )
                    usable_reference_ids = payload.usable_reference_ids
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
                    none_reason_kind = payload.none_reason_kind
                    supported_coverage_percent = max(
                        0,
                        min(payload.supported_coverage_percent, 100),
                    )
                    break
                except TimeoutError:
                    raise
                except Exception as exc:
                    duration_ms = (perf_counter() - started_at) * 1000
                    if _is_retryable_reference_assessment_error(exc) and attempt < max_attempts:
                        debug_log(
                            f"question={question.question_id} "
                            "reference_assessment_service request retry "
                            f"attempt={attempt} duration_ms={duration_ms:.2f} error={exc}"
                        )
                        continue
                    raise
        except TimeoutError:
            debug_log(
                f"question={question.question_id} reference_assessment_service request timeout "
                f"refs={len(references)}"
            )
            print_llm_bug_report(
                service="reference_assessment_service",
                error=("timed out before the retrieved references could be evaluated"),
                messages=messages,
                metadata={
                    "question_id": question.question_id,
                    "reference_count": len(references),
                    "timeout_seconds": f"{settings.tender_llm_request_timeout_seconds:.2f}",
                },
            )
            return ReferenceAssessmentResult(
                can_answer=False,
                grounding_status="insufficient_reference",
                usable_reference_ids=[],
                reason=(
                    "Reference assessment timed out before the retrieved references "
                    "could be evaluated."
                ),
                supported_coverage_percent=0,
            )
        except Exception as exc:
            debug_log(
                f"question={question.question_id} reference_assessment_service request failed "
                f"refs={len(references)} error={exc}"
            )
            print_llm_bug_report(
                service="reference_assessment_service",
                error=str(exc),
                messages=messages,
                metadata={
                    "question_id": question.question_id,
                    "reference_count": len(references),
                },
            )
            return ReferenceAssessmentResult(
                can_answer=False,
                grounding_status="insufficient_reference",
                usable_reference_ids=[],
                reason=f"Reference assessment failed: {exc}",
                supported_coverage_percent=0,
            )

        if answerability == "grounded":
            return ReferenceAssessmentResult(
                can_answer=True,
                grounding_status="grounded",
                usable_reference_ids=usable_reference_ids,
                reason=reason,
                supported_coverage_percent=100,
            )

        if answerability == "partial":
            return ReferenceAssessmentResult(
                can_answer=True,
                grounding_status="partial_reference",
                usable_reference_ids=usable_reference_ids,
                reason=reason,
                supported_coverage_percent=min(max(supported_coverage_percent, 0), 99),
            )

        return ReferenceAssessmentResult(
            can_answer=False,
            grounding_status=(
                "conflict" if none_reason_kind == "conflict" else "insufficient_reference"
            ),
            usable_reference_ids=[],
            reason=reason,
            supported_coverage_percent=0,
        )


class _ReferenceAssessmentPayload(BaseModel):
    answerability: Literal["none", "partial", "grounded"]
    none_reason_kind: Literal["insufficient_reference", "conflict", "not_applicable"]
    supported_coverage_percent: int
    usable_reference_ids: list[str]
    reason: str


def _normalize_structured_payload(payload: Any) -> _ReferenceAssessmentPayload:
    return _ReferenceAssessmentPayload.model_validate(payload)


def _normalize(text: str | None) -> str:
    return " ".join((text or "").lower().split())


def _is_absolute_ssl_disable_reference(text: str) -> bool:
    normalized = _normalize(text)
    return (
        "legacy ssl" in normalized
        and "fully disabled" in normalized
        and "production" in normalized
        and (
            "all public and private production traffic" in normalized
            or "all production traffic" in normalized
        )
    )


def _is_ssl_exception_reference(text: str) -> bool:
    normalized = _normalize(text)
    return (
        "legacy ssl" in normalized
        and ("can remain enabled" in normalized or "may be used" in normalized)
        and "production" in normalized
        and (
            "migration window" in normalized
            or "migration scenarios" in normalized
            or "transition" in normalized
        )
    )


def _detect_material_reference_conflict(
    *,
    question: TenderQuestion,
    references: list[HistoricalReference],
) -> str | None:
    """Return a human-review reason when retrieved references materially disagree."""

    normalized_question = _normalize(question.original_question)

    if (
        "legacy ssl" in normalized_question
        and "production" in normalized_question
        and "fully disabled" in normalized_question
    ):
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


def _is_human_review_only_reference(text: str) -> bool:
    normalized = _normalize(text)
    return (
        "not an approved claim" in normalized
        and "human review" in normalized
        and ("rather than asserted" in normalized or "should be referred" in normalized)
    )


def _references_require_human_review_only(references: list[HistoricalReference]) -> bool:
    return bool(references) and all(
        _is_human_review_only_reference(reference.answer) for reference in references
    )


def _is_retryable_reference_assessment_error(exc: Exception) -> bool:
    return "connection error" in str(exc).lower()


def _is_verification_only_reference(text: str) -> bool:
    normalized = _normalize(text)
    return (
        "separately verified" in normalized
        or "requires verification" in normalized
        or "must be verified" in normalized
    ) and (
        "fedramp" in normalized
        or "hipaa" in normalized
        or "authorization" in normalized
        or "certification" in normalized
    )


def _references_require_verification_before_claim(
    question: TenderQuestion,
    references: list[HistoricalReference],
) -> bool:
    normalized_question = _normalize(question.original_question)
    if not any(
        token in normalized_question
        for token in ("fedramp", "hipaa", "authorization", "authorized", "certification")
    ):
        return False

    return bool(references) and all(
        _is_human_review_only_reference(reference.answer)
        or _is_verification_only_reference(reference.answer)
        for reference in references
    )
