"""Prompt construction for grounded tender-answer generation."""

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.features.tender_response.domain.models import HistoricalReference, TenderQuestion


def build_answer_generation_messages(
    *,
    question: TenderQuestion,
    usable_references: list[HistoricalReference],
) -> list[BaseMessage]:
    """Build the primary structured-output prompt for grounded answer generation."""

    return [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=_build_user_prompt(
                question=question,
                usable_references=usable_references,
            )
        ),
    ]


def build_answer_rewrite_messages(
    *,
    question: TenderQuestion,
    usable_references: list[HistoricalReference],
    invalid_generated_answer: str,
) -> list[BaseMessage]:
    """Build the rewrite prompt used after output validation fails."""

    return [
        SystemMessage(content=f"{_SYSTEM_PROMPT} Rewrite any invalid generated_answer output."),
        HumanMessage(
            content=(
                f"{_build_user_prompt(question=question, usable_references=usable_references)}\n\n"
                f"Previous invalid generated_answer: {invalid_generated_answer}\n"
                "Rewrite generated_answer as plain natural-language prose. Do not return "
                "JSON-like, dict-like, list-like, or key-value formatted content."
            )
        ),
    ]


_SYSTEM_PROMPT = (
    "Generate a grounded tender response using only the provided historical references. "
    "confidence_level and risk_level must be high, medium, or low. "
    "Do not fabricate certifications, commitments, or unsupported claims."
)


def _build_user_prompt(
    *,
    question: TenderQuestion,
    usable_references: list[HistoricalReference],
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

    return (
        f"Question: {question.original_question}\n"
        f"{'\n\n'.join(reference_lines)}\n\n"
        "Return a concise answer grounded only in the references, plus "
        "confidence and risk metadata. generated_answer must be plain natural "
        "language suitable for direct display to end users, not JSON, a Python "
        "dict, a list, or key-value shorthand.\n"
        "Use this confidence rubric:\n"
        "- confidence_level=high when the references directly and explicitly support "
        "all material claims in the answer.\n"
        "- confidence_level=medium when the references support the core answer but "
        "leave some scope, specificity, or phrasing uncertainty.\n"
        "- confidence_level=low when the answer is only weakly supported, partial, "
        "or close to the boundary of what the references justify."
    )
