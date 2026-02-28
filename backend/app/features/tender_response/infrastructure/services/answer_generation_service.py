"""LLM-backed answer generation for grounded tender responses."""

from app.core.config import settings
from app.features.tender_response.domain.models import HistoricalReference, TenderQuestion
from app.integrations.openai.chat_completions_client import OpenAIChatCompletionsClient


class AnswerGenerationService:
    """Generate an answer using only the subset of references deemed usable."""

    def __init__(
        self,
        completion_client: OpenAIChatCompletionsClient | None = None,
    ) -> None:
        self._completion_client = completion_client or OpenAIChatCompletionsClient(
            model=settings.openai_tender_response_model
        )

    async def generate_answer(
        self,
        *,
        question: TenderQuestion,
        usable_references: list[HistoricalReference],
    ) -> str:
        """Render references into a prompt and ask the model for a grounded answer."""

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

        return await self._completion_client.create_completion(
            system_prompt=(
                "Generate a concise tender response using only the provided historical "
                "references. Do not fabricate certifications, commitments, or unsupported "
                "claims. If the references are insufficient, return an empty string."
            ),
            user_prompt=(
                f"Question: {question.original_question}\n"
                f"{'\n\n'.join(reference_lines)}\n\n"
                "Return only the final tender answer grounded in the references."
            ),
        )
