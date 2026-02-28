"""LLM-backed assessment of whether retrieved references are sufficient."""

import json

from app.core.config import settings
from app.features.tender_response.domain.models import (
    HistoricalReference,
    ReferenceAssessmentResult,
    TenderQuestion,
)
from app.integrations.openai.chat_completions_client import OpenAIChatCompletionsClient


class ReferenceAssessmentService:
    """Gate answer generation unless the retrieved references can stand on their own."""

    def __init__(
        self,
        completion_client: OpenAIChatCompletionsClient | None = None,
    ) -> None:
        self._completion_client = completion_client or OpenAIChatCompletionsClient(
            model=settings.openai_tender_response_model
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

        prompt = self._build_prompt(question=question, references=references)
        try:
            response = await self._completion_client.create_json_completion(
                system_prompt=(
                    "Decide whether the provided historical references are sufficient to answer "
                    "the tender question without fabricating certifications or unsupported claims. "
                    "Return strict JSON with keys can_answer, usable_reference_ids, reason."
                ),
                user_prompt=prompt,
            )
            payload = json.loads(response)
            usable_reference_ids = payload.get("usable_reference_ids", [])
            if not isinstance(usable_reference_ids, list):
                raise ValueError("usable_reference_ids must be a list.")
            valid_reference_ids = {reference.record_id for reference in references}
            # Never trust the model to return only ids we supplied in the prompt.
            usable_reference_ids = [
                str(reference_id)
                for reference_id in usable_reference_ids
                if str(reference_id) in valid_reference_ids
            ]
            # "can_answer" is only honored when it is backed by at least one validated reference id.
            can_answer = bool(payload.get("can_answer")) and bool(usable_reference_ids)
            reason = str(payload.get("reason", "")).strip() or "Reference assessment completed."
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

    def _build_prompt(
        self,
        *,
        question: TenderQuestion,
        references: list[HistoricalReference],
    ) -> str:
        """Serialize the question and evidence set for strict JSON evaluation."""

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
            f"Candidate references: {json.dumps(reference_payload, ensure_ascii=True)}\n"
            "Only mark can_answer=true if the references are sufficient on their own."
        )
