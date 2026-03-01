"""Prompt construction for session-level tender answer conflict review."""

import json

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.features.tender_response.schemas.responses import TenderQuestionResponse


def build_conflict_review_messages(
    *,
    target_results: list[TenderQuestionResponse],
    reference_results: list[TenderQuestionResponse],
) -> list[BaseMessage]:
    """Build a strict structured-output prompt for answer conflict review."""

    target_payload = [_result_payload(item) for item in target_results]
    reference_payload = [_result_payload(item) for item in reference_results]

    return [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                "Review the target tender answers for contradictions against the full "
                "reference set from the same session.\n"
                f"Target answers: {json.dumps(target_payload, ensure_ascii=True)}\n"
                f"Reference answers: {json.dumps(reference_payload, ensure_ascii=True)}\n"
                "Return only material contradictions or mutually incompatible commitments. "
                "Do not return duplicates, formatting differences, or harmless wording variation."
            )
        ),
    ]


def _result_payload(result: TenderQuestionResponse) -> dict[str, str]:
    return {
        "question_id": result.question_id,
        "original_question": result.original_question,
        "generated_answer": result.generated_answer or "",
        "domain_tag": result.domain_tag or "",
        "status": result.status,
    }


_SYSTEM_PROMPT = (
    "You are reviewing completed tender answers for contradictions within the same session. "
    "Only report a conflict when two answers make incompatible factual, contractual, "
    "security, compliance, architecture, or pricing commitments. "
    "Treat an absolute answer such as 'fully disabled for all production traffic' as "
    "conflicting with any other answer that allows the same capability during "
    "migration windows, approved exceptions, or temporary transition scenarios. "
    "Ignore unanswered or failed items; they are not included in the payload. "
    "Each reported conflict must identify one target_question_id, one conflicting_question_id, "
    "a concise reason, and a severity of high, medium, or low."
)
