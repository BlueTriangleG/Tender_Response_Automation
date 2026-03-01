"""LLM-backed assessment of whether retrieved references are sufficient."""

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
            # "can_answer" is only honored when it is backed by at least one validated reference id.
            can_answer = payload.can_answer and bool(usable_reference_ids)
            reason = payload.reason.strip() or "Reference assessment completed."
        except Exception as exc:
            return ReferenceAssessmentResult(
                can_answer=False,
                grounding_status="insufficient_reference",
                usable_reference_ids=[],
                reason=f"Reference assessment failed: {exc}",
            )

        if can_answer:
            return ReferenceAssessmentResult(
                can_answer=True,
                grounding_status="grounded",
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
    can_answer: bool
    usable_reference_ids: list[str]
    reason: str
