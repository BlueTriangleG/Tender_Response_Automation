"""Single-call grounded answer generation plus confidence/risk review."""

import json

from app.core.config import settings
from app.features.tender_response.domain.models import (
    GroundedAnswerResult,
    HistoricalReference,
    TenderQuestion,
)
from app.integrations.openai.chat_completions_client import OpenAIChatCompletionsClient


class AnswerGenerationService:
    """Generate a grounded answer and review metadata in one LLM call."""

    def __init__(
        self,
        completion_client: OpenAIChatCompletionsClient | None = None,
    ) -> None:
        self._completion_client = completion_client or OpenAIChatCompletionsClient(
            model=settings.openai_tender_response_model
        )

    async def generate_grounded_response(
        self,
        *,
        question: TenderQuestion,
        usable_references: list[HistoricalReference],
    ) -> GroundedAnswerResult:
        """Render references into a prompt and ask for answer plus structured review."""

        reference_lines: list[str] = []
        for index, reference in enumerate(usable_references, start=1):
            reference_lines.append(
                "\n".join(
                    [
                        f"Reference {index} id: {reference.record_id}",
                        f"Reference {index} question: {reference.question}",
                        f"Reference {index} answer: {reference.answer}",
                        f"Reference {index} source_doc: {reference.source_doc or ''}",
                    ]
                )
            )

        system_prompt = (
            "Generate a grounded tender response using only the provided historical "
            "references. Return strict JSON with keys generated_answer, "
            "confidence_level, confidence_reason, risk_level, risk_reason, "
            "inconsistent_response. confidence_level and risk_level must be "
            "high, medium, or low. Do not fabricate certifications, commitments, "
            "or unsupported claims."
        )
        user_prompt = (
            f"Question: {question.original_question}\n"
            f"{'\n\n'.join(reference_lines)}\n\n"
            "Return a concise answer grounded only in the references, plus "
            "confidence and risk metadata. generated_answer must be plain natural "
            "language suitable for direct display to end users, not JSON, a Python "
            "dict, a list, or key-value shorthand.\n"
            "Use this confidence rubric:\n"
            "- confidence_level=high when the references directly and explicitly support "
            "all material claims in the answer.\n"
            "- confidence_level=medium when the references support the core answer but "
            "leave some scope, specificity, or phrasing uncertainty.\n"
            "- confidence_level=low when the answer is only weakly supported, partial, "
            "or close to the boundary of what the references justify."
        )
        result = await self._request_grounded_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        if self._is_displayable_answer(result.generated_answer):
            return result

        rewrite_prompt = (
            f"{user_prompt}\n\n"
            f"Previous invalid generated_answer: {result.generated_answer}\n"
            "Rewrite generated_answer as plain natural-language prose. Do not return "
            "JSON-like, dict-like, list-like, or key-value formatted content."
        )
        rewritten_result = await self._request_grounded_response(
            system_prompt=f"{system_prompt} Rewrite any invalid generated_answer output.",
            user_prompt=rewrite_prompt,
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
        system_prompt: str,
        user_prompt: str,
    ) -> GroundedAnswerResult:
        """Request one structured grounded-response payload from the model."""

        response = await self._completion_client.create_json_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        payload = json.loads(response)
        return GroundedAnswerResult(
            generated_answer=str(payload["generated_answer"]).strip(),
            confidence_level=str(payload["confidence_level"]).lower(),
            confidence_reason=str(payload["confidence_reason"]).strip(),
            risk_level=str(payload["risk_level"]).lower(),
            risk_reason=str(payload["risk_reason"]).strip(),
            inconsistent_response=bool(payload.get("inconsistent_response", False)),
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
