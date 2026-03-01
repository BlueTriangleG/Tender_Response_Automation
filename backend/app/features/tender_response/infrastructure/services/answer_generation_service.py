"""Single-call grounded answer generation plus confidence/risk review."""

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.features.tender_response.domain.models import (
    GroundedAnswerResult,
    HistoricalReference,
    TenderQuestion,
)
from app.features.tender_response.infrastructure.prompting.answer_generation import (
    build_answer_generation_messages,
    build_answer_rewrite_messages,
)


class AnswerGenerationService:
    """Generate a grounded answer and review metadata in one LLM call."""

    def __init__(
        self,
        model: BaseChatModel | None = None,
    ) -> None:
        self._model = model or ChatOpenAI(
            model=settings.openai_tender_response_model,
            temperature=0,
        )

    async def generate_grounded_response(
        self,
        *,
        question: TenderQuestion,
        usable_references: list[HistoricalReference],
        attempt_number: int = 1,
        validation_error: str | None = None,
        last_invalid_answer: str | None = None,
        last_invalid_confidence_level: str | None = None,
        last_invalid_confidence_reason: str | None = None,
        assessment_reason: str | None = None,
    ) -> GroundedAnswerResult:
        """Render references into a prompt and ask for answer plus structured review."""

        result = await self._request_grounded_response(
            messages=build_answer_generation_messages(
                question=question,
                usable_references=usable_references,
                attempt_number=attempt_number,
                validation_error=validation_error,
                last_invalid_answer=last_invalid_answer,
                last_invalid_confidence_level=last_invalid_confidence_level,
                last_invalid_confidence_reason=last_invalid_confidence_reason,
                assessment_reason=assessment_reason,
            )
        )
        if self._is_displayable_answer(result.generated_answer):
            return result

        rewritten_result = await self._request_grounded_response(
            messages=build_answer_rewrite_messages(
                question=question,
                usable_references=usable_references,
                invalid_generated_answer=result.generated_answer,
            )
        )
        if self._is_displayable_answer(rewritten_result.generated_answer):
            return rewritten_result

        return GroundedAnswerResult(
            generated_answer="",
            confidence_level="low",
            confidence_reason="Generated answer failed output validation.",
            risk_level=rewritten_result.risk_level,
            risk_reason=rewritten_result.risk_reason,
            inconsistent_response=rewritten_result.inconsistent_response,
        )

    async def _request_grounded_response(
        self,
        *,
        messages,
    ) -> GroundedAnswerResult:
        """Request one structured grounded-response payload from the model."""

        structured_model = self._model.with_structured_output(
            _GroundedAnswerPayload,
            method="function_calling",
            strict=True,
        )
        payload = await structured_model.ainvoke(messages)
        return GroundedAnswerResult(
            generated_answer=payload.generated_answer.strip(),
            confidence_level=payload.confidence_level.lower(),
            confidence_reason=payload.confidence_reason.strip(),
            risk_level=payload.risk_level.lower(),
            risk_reason=payload.risk_reason.strip(),
            inconsistent_response=payload.inconsistent_response,
        )

    def _is_displayable_answer(self, answer: str) -> bool:
        """Reject machine-oriented payloads that should be rewritten before returning."""

        text = answer.strip()
        if not text:
            return False
        if self._looks_like_structured_payload(text):
            return False
        return True

    def _looks_like_structured_payload(self, text: str) -> bool:
        """Detect JSON-like or dict-like strings that are not suitable for UI display."""

        stripped = text.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (
            stripped.startswith("[") and stripped.endswith("]")
        ):
            return True

        # Common Python dict rendering that may not be valid JSON but still shouldn't
        # be shown as the final answer to end users.
        if stripped.startswith("{'") or '":' in stripped or "':" in stripped:
            return True

        return False


class _GroundedAnswerPayload(BaseModel):
    generated_answer: str
    confidence_level: str
    confidence_reason: str
    risk_level: str
    risk_reason: str
    inconsistent_response: bool
