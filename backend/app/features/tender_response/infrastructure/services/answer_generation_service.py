from app.core.config import settings
from app.features.tender_response.domain.models import (
    HistoricalAlignmentResult,
    TenderQuestion,
)
from app.integrations.openai.chat_completions_client import OpenAIChatCompletionsClient


class AnswerGenerationService:
    def __init__(
        self,
        completion_client: OpenAIChatCompletionsClient | None = None,
    ) -> None:
        self._completion_client = completion_client or OpenAIChatCompletionsClient(
            model=settings.openai_tender_response_model
        )

    async def generate_with_alignment(
        self,
        *,
        question: TenderQuestion,
        alignment: HistoricalAlignmentResult,
    ) -> str:
        return await self._completion_client.create_completion(
            system_prompt=(
                "Generate a concise tender response using the historical alignment context. "
                "Do not fabricate certifications or unsupported claims."
            ),
            user_prompt=(
                f"Question: {question.original_question}\n"
                f"Historical question: {alignment.question}\n"
                f"Historical answer: {alignment.answer}\n"
                "Return only the final tender answer."
            ),
        )

    async def generate_without_alignment(self, question: TenderQuestion) -> str:
        return await self._completion_client.create_completion(
            system_prompt=(
                "Generate a conservative tender response. "
                "Do not fabricate certifications, contractual commitments, or unsupported claims. "
                "If evidence is unavailable, state that the answer cannot be fully confirmed."
            ),
            user_prompt=(
                f"Question: {question.original_question}\n"
                "Return only the final tender answer."
            ),
        )
