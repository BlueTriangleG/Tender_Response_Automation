"""LLM-backed review pass for generated tender answers."""

import json

from app.core.config import settings
from app.features.tender_response.domain.models import (
    HistoricalReference,
    ResponseReviewResult,
    TenderQuestion,
)
from app.integrations.openai.chat_completions_client import OpenAIChatCompletionsClient


class ResponseReviewService:
    """Assess confidence and risk after an answer has been generated."""

    def __init__(
        self,
        completion_client: OpenAIChatCompletionsClient | None = None,
    ) -> None:
        self._completion_client = completion_client or OpenAIChatCompletionsClient(
            model=settings.openai_tender_response_model
        )

    async def review_response(
        self,
        *,
        question: TenderQuestion,
        generated_answer: str | None,
        grounding_status: str,
        references: list[HistoricalReference],
    ) -> ResponseReviewResult:
        """Review confidence and risk with the LLM, then apply hard safety caps."""

        prompt = self._build_prompt(
            question=question,
            generated_answer=generated_answer,
            grounding_status=grounding_status,
            references=references,
        )
        try:
            response = await self._completion_client.create_json_completion(
                system_prompt=(
                    "Review the generated tender answer against the references. "
                    "Return strict JSON with keys confidence_level, confidence_reason, "
                    "risk_level, risk_reason, inconsistent_response. "
                    "confidence_level and risk_level must be high, medium, or low. "
                    "If grounding_status is not grounded, confidence_reason should explain "
                    "why the available evidence was not enough, and confidence_level should "
                    "still reflect the available evidence quality even though the "
                    "system may cap it."
                ),
                user_prompt=prompt,
            )
            payload = json.loads(response)
            result = ResponseReviewResult(
                confidence_level=str(payload["confidence_level"]).lower(),
                confidence_reason=str(payload["confidence_reason"]).strip(),
                risk_level=str(payload["risk_level"]).lower(),
                risk_reason=str(payload["risk_reason"]).strip(),
                inconsistent_response=bool(payload.get("inconsistent_response", False)),
            )
        except Exception as exc:
            return ResponseReviewResult(
                confidence_level="low",
                confidence_reason=f"Response review failed: {exc}",
                risk_level="medium",
                risk_reason="Risk could not be confidently assessed because review failed.",
                inconsistent_response=False,
            )

        if result.confidence_level not in {"high", "medium", "low"}:
            result.confidence_level = "low"
        if result.risk_level not in {"high", "medium", "low"}:
            result.risk_level = "medium"
        if grounding_status != "grounded":
            result.confidence_level = "low"
        if not result.confidence_reason:
            result.confidence_reason = "LLM review completed without a detailed reason."
        if not result.risk_reason:
            result.risk_reason = "LLM review completed without a detailed risk reason."
        return result

    def _build_prompt(
        self,
        *,
        question: TenderQuestion,
        generated_answer: str | None,
        grounding_status: str,
        references: list[HistoricalReference],
    ) -> str:
        """Serialize the generated answer and evidence for model-based review."""

        reference_payload = [
            {
                "alignment_record_id": reference.record_id,
                "alignment_score": reference.alignment_score,
                "source_doc": reference.source_doc,
                "matched_question": reference.question,
                "matched_answer": reference.answer,
            }
            for reference in references
        ]
        return (
            f"Question: {question.original_question}\n"
            f"Generated answer: {generated_answer or ''}\n"
            f"Grounding status: {grounding_status}\n"
            f"References: {json.dumps(reference_payload, ensure_ascii=True)}\n"
            "Assess answer confidence from the actual supporting information. "
            "Assess risk independently from confidence."
        )
