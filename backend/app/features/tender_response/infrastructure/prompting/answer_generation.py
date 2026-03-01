"""Prompt construction for grounded tender-answer generation."""

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.features.tender_response.domain.models import HistoricalReference, TenderQuestion


def build_answer_generation_messages(
    *,
    question: TenderQuestion,
    usable_references: list[HistoricalReference],
    attempt_number: int = 1,
    validation_error: str | None = None,
    last_invalid_answer: str | None = None,
    last_invalid_confidence_level: str | None = None,
    last_invalid_confidence_reason: str | None = None,
    assessment_reason: str | None = None,
) -> list[BaseMessage]:
    """Build the primary structured-output prompt for grounded answer generation."""

    return [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=_build_user_prompt(
                question=question,
                usable_references=usable_references,
                attempt_number=attempt_number,
                validation_error=validation_error,
                last_invalid_answer=last_invalid_answer,
                last_invalid_confidence_level=last_invalid_confidence_level,
                last_invalid_confidence_reason=last_invalid_confidence_reason,
                assessment_reason=assessment_reason,
            )
        ),
    ]


def build_answer_rewrite_messages(
    *,
    question: TenderQuestion,
    usable_references: list[HistoricalReference],
    invalid_generated_answer: str,
    attempt_number: int = 2,
    validation_error: str = "generated_answer must be plain natural-language prose.",
) -> list[BaseMessage]:
    """Build the rewrite prompt used after output validation fails."""

    return [
        SystemMessage(content=f"{_SYSTEM_PROMPT} Rewrite any invalid generated_answer output."),
        HumanMessage(
            content=(
                f"{_build_user_prompt(question=question, usable_references=usable_references)}\n\n"
                f"Correction attempt {attempt_number}.\n"
                f"Validation error: {validation_error}\n"
                f"Previous invalid generated_answer: {invalid_generated_answer}\n"
                "Rewrite generated_answer as plain natural-language prose. Do not return "
                "JSON-like, dict-like, list-like, or key-value formatted content."
            )
        ),
    ]


_SYSTEM_PROMPT = (
    "Generate a grounded tender response using only the provided historical references. "
    "confidence_level and risk_level must be high, medium, or low. "
    "Do not fabricate certifications, commitments, or unsupported claims. "
    "If only a partial answer is supported, generated_answer must still answer the "
    "supported portion and must explicitly identify the missing or unsupported scope "
    "in parentheses."
)


def _build_user_prompt(
    *,
    question: TenderQuestion,
    usable_references: list[HistoricalReference],
    attempt_number: int = 1,
    validation_error: str | None = None,
    last_invalid_answer: str | None = None,
    last_invalid_confidence_level: str | None = None,
    last_invalid_confidence_reason: str | None = None,
    assessment_reason: str | None = None,
) -> str:
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

    retry_block = ""
    if attempt_number > 1:
        retry_lines = [f"Correction attempt {attempt_number}."]
        if validation_error:
            retry_lines.append(
                f"Your previous answer failed validation for this exact reason: {validation_error}"
            )
            retry_lines.append(
                "You must fix this exact validation error in the next answer."
            )
        if last_invalid_answer:
            retry_lines.append(f"Previous invalid generated_answer: {last_invalid_answer}")
        if last_invalid_confidence_level:
            retry_lines.append(
                f"Previous invalid confidence_level: {last_invalid_confidence_level}"
            )
        if last_invalid_confidence_reason:
            retry_lines.append(
                f"Previous invalid confidence_reason: {last_invalid_confidence_reason}"
            )
        if assessment_reason:
            retry_lines.append(
                "Reference assessment identified this exact unsupported or missing scope: "
                f"{assessment_reason}"
            )
            retry_lines.append(
                "Use that missing or unsupported scope directly in the parentheses within "
                "generated_answer and explain the same gap explicitly in confidence_reason."
            )
        retry_lines.append("Correct the output. Do not repeat the same mistake.")
        retry_block = "\n" + "\n".join(retry_lines) + "\n"

    assessment_block = ""
    if assessment_reason:
        assessment_block = (
            f"Reference assessment reason: {assessment_reason}\n"
            "If the answer is partial, the parenthetical note and confidence_reason "
            "must explicitly reflect this gap.\n"
        )

    return (
        f"Question: {question.original_question}\n"
        f"{'\n\n'.join(reference_lines)}\n\n"
        "Return a concise answer grounded only in the references, plus "
        "confidence and risk metadata. generated_answer must be plain natural "
        "language suitable for direct display to end users, not JSON, a Python "
        "dict, a list, or key-value shorthand.\n"
        "If the references support only part of the question, do not return unanswered. "
        "Answer the supported portion and explicitly note the missing or unsupported "
        "scope in parentheses within generated_answer.\n"
        "For partial answers, confidence_reason must explicitly explain why confidence "
        "is reduced and identify the missing evidence, scope, timeframe, certification, "
        "number, or commitment.\n"
        f"{assessment_block}"
        f"{retry_block}"
        "Use this confidence rubric:\n"
        "- confidence_level=high when the references directly and explicitly support "
        "all material claims in the answer.\n"
        "- confidence_level=medium when the references support the core answer but "
        "leave some scope, specificity, or phrasing uncertainty.\n"
        "- confidence_level=low when the answer is only weakly supported, partial, "
        "or close to the boundary of what the references justify. Partial answers "
        "should normally be medium or low, not high."
    )
