"""LLM-backed session conflict review for completed tender answers."""

import asyncio
from time import perf_counter
from typing import Literal, Protocol

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.features.tender_response.domain.conflict_rules import (
    has_meaningful_topic_overlap,
    normalize_conflict_text,
)
from app.features.tender_response.infrastructure.prompting.conflict_review import (
    build_conflict_review_messages,
)
from app.features.tender_response.infrastructure.workflows.common.debug import (
    debug_log,
    print_llm_bug_report,
)
from app.features.tender_response.schemas.responses import TenderQuestionResponse


class ConflictReviewService:
    """Check completed tender answers for session-level contradictions."""

    def __init__(
        self,
        model: BaseChatModel | None = None,
    ) -> None:
        self._model = model or ChatOpenAI(
            model=settings.openai_tender_response_model,
            temperature=0,
        )

    async def review_conflicts(
        self,
        *,
        target_results: list[TenderQuestionResponse],
        reference_results: list[TenderQuestionResponse],
    ) -> list[dict[str, str]]:
        """Return validated conflict findings for the target results."""

        if not target_results or len(reference_results) < 2:
            return []

        debug_log(
            "conflict_review_service request "
            f"targets={len(target_results)} references={len(reference_results)}"
        )
        structured_model = self._model.with_structured_output(
            _ConflictReviewPayload,
            method="function_calling",
            strict=True,
        )
        timeout_seconds = min(
            settings.tender_llm_request_timeout_seconds,
            settings.tender_conflict_review_timeout_seconds,
        )
        started_at = perf_counter()
        debug_log(f"conflict_review_service llm_call start timeout_s={timeout_seconds:.2f}")
        messages = build_conflict_review_messages(
            target_results=target_results,
            reference_results=reference_results,
        )
        try:
            raw_payload = await asyncio.wait_for(
                structured_model.ainvoke(messages),
                timeout=timeout_seconds,
            )
            payload = _ConflictReviewPayload.model_validate(raw_payload)
        except TimeoutError:
            duration_ms = (perf_counter() - started_at) * 1000
            debug_log(f"conflict_review_service llm_call timeout duration_ms={duration_ms:.2f}")
            print_llm_bug_report(
                service="conflict_review_service",
                error=f"timed out after {timeout_seconds:.2f}s",
                messages=messages,
                metadata={
                    "target_count": len(target_results),
                    "reference_count": len(reference_results),
                    "timeout_seconds": f"{timeout_seconds:.2f}",
                },
            )
            raise
        except Exception as exc:
            duration_ms = (perf_counter() - started_at) * 1000
            debug_log(
                f"conflict_review_service llm_call failed duration_ms={duration_ms:.2f} error={exc}"
            )
            print_llm_bug_report(
                service="conflict_review_service",
                error=str(exc),
                messages=messages,
                metadata={
                    "target_count": len(target_results),
                    "reference_count": len(reference_results),
                },
            )
            raise
        duration_ms = (perf_counter() - started_at) * 1000
        debug_log(f"conflict_review_service llm_call end duration_ms={duration_ms:.2f}")
        target_ids = {item.question_id for item in target_results}
        reference_ids = {item.question_id for item in reference_results}
        results_by_id = {item.question_id: item for item in [*target_results, *reference_results]}
        deduped: dict[tuple[str, str], dict[str, str]] = {}

        for item in payload.conflicts:
            target_question_id = item.target_question_id.strip()
            conflicting_question_id = item.conflicting_question_id.strip()
            reason = item.reason.strip()
            severity = item.severity.lower()

            if (
                not target_question_id
                or not conflicting_question_id
                or not reason
                or target_question_id not in target_ids
                or conflicting_question_id not in reference_ids
                or target_question_id == conflicting_question_id
            ):
                continue

            target = results_by_id[target_question_id]
            reference = results_by_id[conflicting_question_id]
            if not has_meaningful_topic_overlap(
                left_question=target.original_question,
                left_answer=target.generated_answer or "",
                right_question=reference.original_question,
                right_answer=reference.generated_answer or "",
            ):
                continue

            deduped[(target_question_id, conflicting_question_id)] = {
                "target_question_id": target_question_id,
                "conflicting_question_id": conflicting_question_id,
                "reason": reason,
                "severity": severity,
            }

        for finding in self._detect_guardrail_conflicts(
            target_results=target_results,
            reference_results=reference_results,
        ):
            deduped[(finding["target_question_id"], finding["conflicting_question_id"])] = (
                finding
            )

        validated = list(deduped.values())
        debug_log(
            "conflict_review_service response "
            f"raw={len(payload.conflicts)} validated={len(validated)}"
        )
        return validated

    def _detect_guardrail_conflicts(
        self,
        *,
        target_results: list[TenderQuestionResponse],
        reference_results: list[TenderQuestionResponse],
    ) -> list[dict[str, str]]:
        findings: list[dict[str, str]] = []

        for target in target_results:
            for reference in reference_results:
                if reference.question_id == target.question_id:
                    continue
                if not _is_absolute_vs_exception_conflict_pair(
                    left_answer=target.generated_answer or "",
                    right_answer=reference.generated_answer or "",
                ):
                    continue

                findings.append(
                    {
                        "target_question_id": target.question_id,
                        "conflicting_question_id": reference.question_id,
                        "reason": _build_conflict_reason(
                            left_answer=target.generated_answer or "",
                            right_answer=reference.generated_answer or "",
                        ),
                        "severity": "high",
                    }
                )

        return findings


class NoopConflictReviewService:
    """Test-friendly conflict reviewer that never emits conflicts."""

    async def review_conflicts(
        self,
        *,
        target_results: list[TenderQuestionResponse],
        reference_results: list[TenderQuestionResponse],
    ) -> list[dict[str, str]]:
        return []


class ConflictReviewer(Protocol):
    async def review_conflicts(
        self,
        *,
        target_results: list[TenderQuestionResponse],
        reference_results: list[TenderQuestionResponse],
    ) -> list[dict[str, str]]: ...


class _ConflictFindingPayload(BaseModel):
    target_question_id: str
    conflicting_question_id: str
    reason: str
    severity: Literal["high", "medium", "low"]


class _ConflictReviewPayload(BaseModel):
    conflicts: list[_ConflictFindingPayload]


def _build_conflict_reason(*, left_answer: str, right_answer: str) -> str:
    if _is_absolute_vs_exception_conflict_pair(left_answer=left_answer, right_answer=right_answer):
        return (
            "One answer asserts a capability is fully disabled for production traffic, "
            "while another allows limited production-time exceptions during migration scenarios."
        )
    return "These answers make incompatible statements about the same capability or claim."


def _mentions_legacy_protocol(text: str) -> bool:
    return (
        "legacy ssl" in text
        or "legacy protocol" in text
        or "deprecated protocol" in text
    )


def _is_absolute_vs_exception_conflict_pair(*, left_answer: str, right_answer: str) -> bool:
    left_text = normalize_conflict_text(left_answer)
    right_text = normalize_conflict_text(right_answer)

    if not _mentions_legacy_protocol(left_text) or not _mentions_legacy_protocol(right_text):
        return False

    left_absolute = "fully disabled" in left_text and "production traffic" in left_text
    right_absolute = "fully disabled" in right_text and "production traffic" in right_text
    left_exception = "remain enabled" in left_text and (
        "migration" in left_text or "transition" in left_text
    )
    right_exception = "remain enabled" in right_text and (
        "migration" in right_text or "transition" in right_text
    )

    return (left_absolute and right_exception) or (right_absolute and left_exception)
