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
                "Only mark can_answer=true if the references are sufficient on their own."
            )
        ),
    ]


_SYSTEM_PROMPT = (
    "Decide whether the provided historical references are sufficient to answer "
    "the tender question without fabricating certifications or unsupported claims."
)

