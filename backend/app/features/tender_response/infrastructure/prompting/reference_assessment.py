"""Prompt construction for reference sufficiency assessment."""

import json

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.features.tender_response.domain.models import HistoricalReference, TenderQuestion


def build_reference_assessment_messages(
    *,
    question: TenderQuestion,
    references: list[HistoricalReference],
) -> list[BaseMessage]:
    """Build the structured-output prompt for deciding whether references are sufficient."""

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
    return [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Question: {question.original_question}\n"
                f"Candidate references: {json.dumps(reference_payload, ensure_ascii=True)}\n"
                "Classify answerability as none, partial, or grounded.\n"
                "- none: the references are unrelated or too weak to support any safe answer.\n"
                "- partial: the references support part of the answer, but material scope is missing.\n"
                "- grounded: the references are sufficient on their own for the full answer.\n"
                "Only return reference ids that materially support the selected answerability.\n"
                "Use partial when a safe partial answer is possible."
            )
        ),
    ]


_SYSTEM_PROMPT = (
    "Decide whether the provided historical references are sufficient to answer "
    "the tender question without fabricating certifications or unsupported claims. "
    "Reserve 'none' for references that are not materially relevant or cannot support "
    "any safe answer at all."
)
