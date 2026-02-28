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

        response = await self._completion_client.create_json_completion(
            system_prompt=(
                "Generate a grounded tender response using only the provided historical "
                "references. Return strict JSON with keys generated_answer, "
                "confidence_level, confidence_reason, risk_level, risk_reason, "
                "inconsistent_response. confidence_level and risk_level must be "
                "high, medium, or low. Do not fabricate certifications, commitments, "
                "or unsupported claims."
            ),
            user_prompt=(
                f"Question: {question.original_question}\n"
                f"{'\n\n'.join(reference_lines)}\n\n"
                "Return a concise answer grounded only in the references, plus "
                "confidence and risk metadata."
            ),
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
