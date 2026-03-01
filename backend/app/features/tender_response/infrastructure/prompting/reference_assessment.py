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
            "reference_type": reference.reference_type,
            "alignment_score": reference.alignment_score,
            "source_doc": reference.source_doc,
            "excerpt": reference.excerpt,
            "chunk_index": reference.chunk_index,
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
                "- none: the references are unrelated, too weak to support any safe answer, "
                "or materially conflict with each other on the same capability/commitment so "
                "human review is required.\n"
                "- partial: the references support part of the answer, "
                "but material scope is missing.\n"
                "- grounded: the references are sufficient on their own for the full answer.\n"
                "If answerability is none, also decide whether none_reason_kind should be "
                "'insufficient_reference' or 'conflict'. Use 'conflict' only when the "
                "references make opposing statements about the same underlying capability, "
                "certification, or commitment.\n"
                "If answerability is partial or grounded, set none_reason_kind to "
                "'not_applicable'.\n"
                "Return supported_coverage_percent as an integer from 0 to 100 that "
                "estimates how much of the user's requested scope can be safely answered "
                "from the provided references.\n"
                "- Use 0 when answerability is none.\n"
                "- Use 100 only when the full requested scope is supported.\n"
                "- Use 1-99 when answerability is partial.\n"
                "- If the supported and unsupported scope are roughly equal, use 50.\n"
                "If any material sub-part, scope, timeframe, environment, commitment, "
                "certification, quantity, or condition is unsupported, choose partial rather "
                "than grounded.\n"
                "Do not mark grounded when the references support only a standard position but "
                "do not directly authorize the exact requested term, duration, environment, or "
                "commercial commitment.\n"
                "Only return reference ids that materially support the selected answerability.\n"
                "Use partial when a safe partial answer is possible."
            )
        ),
    ]


_SYSTEM_PROMPT = (
    "Decide whether the provided historical references are sufficient to answer "
    "the tender question without fabricating certifications or unsupported claims. "
    "Reserve 'none' for references that are not materially relevant, materially "
    "conflict with each other, or cannot support any safe answer at all. When "
    "references conflict on a material fact or commitment, require human review "
    "instead of synthesizing an answer. Be conservative about 'grounded': if a "
    "material part of the tender question remains unsupported, classify as 'partial', "
    "not 'grounded'."
)
