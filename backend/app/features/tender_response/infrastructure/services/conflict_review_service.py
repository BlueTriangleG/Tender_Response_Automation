"""LLM-backed session conflict review for completed tender answers."""

from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.features.tender_response.domain.conflict_rules import (
    detect_statement_conflict,
    normalize_conflict_text,
)
from app.features.tender_response.infrastructure.prompting.conflict_review import (
    build_conflict_review_messages,
)
from app.features.tender_response.infrastructure.workflows.common.debug import debug_log
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
        payload = await structured_model.ainvoke(
            build_conflict_review_messages(
                target_results=target_results,
                reference_results=reference_results,
            )
        )
        target_ids = {item.question_id for item in target_results}
        reference_ids = {item.question_id for item in reference_results}
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

            deduped[(target_question_id, conflicting_question_id)] = {
                "target_question_id": target_question_id,
                "conflicting_question_id": conflicting_question_id,
                "reason": reason,
                "severity": severity,
            }

        for item in self._detect_absolute_claim_conflicts(
            target_results=target_results,
            reference_results=reference_results,
        ):
            deduped[(item["target_question_id"], item["conflicting_question_id"])] = item

        validated = list(deduped.values())
        debug_log(
            "conflict_review_service response "
            f"raw={len(payload.conflicts)} validated={len(validated)}"
        )
        return validated

    def _detect_absolute_claim_conflicts(
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

                if not detect_statement_conflict(
                    left_question=target.original_question,
                    left_answer=target.generated_answer or "",
                    right_question=reference.original_question,
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


class _ConflictFindingPayload(BaseModel):
    target_question_id: str
    conflicting_question_id: str
    reason: str
    severity: Literal["high", "medium", "low"]


class _ConflictReviewPayload(BaseModel):
    conflicts: list[_ConflictFindingPayload]


def _build_conflict_reason(*, left_answer: str, right_answer: str) -> str:
    left_text = normalize_conflict_text(left_answer)
    right_text = normalize_conflict_text(right_answer)
    if "legacy ssl" in left_text and "legacy ssl" in right_text:
        return (
            "One answer says legacy SSL is fully disabled for production traffic, "
            "while another says legacy SSL can remain enabled in a production "
            "migration scenario."
        )
    if "fedramp" in left_text and "fedramp" in right_text:
        return (
            "The answers make opposing statements about FedRAMP status and cannot "
            "both be true."
        )
    if "saml" in left_text and "saml" in right_text:
        return (
            "The answers make opposing statements about whether SAML or OpenID "
            "Connect is supported."
        )
    return "These answers make incompatible statements about the same capability or claim."
