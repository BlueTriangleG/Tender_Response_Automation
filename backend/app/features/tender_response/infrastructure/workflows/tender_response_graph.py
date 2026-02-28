"""LangGraph workflow that grounds tender answers in historical QA records."""

import operator
from typing import Annotated

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send
from typing_extensions import TypedDict

from app.features.tender_response.domain.models import (
    GroundedAnswerResult,
    HistoricalAlignmentResult,
    HistoricalReference,
    ReferenceAssessmentResult,
    ResponseReviewResult,
    TenderQuestion,
)
from app.features.tender_response.domain.risk_rules import (
    detect_high_risk_response,
    detect_inconsistent_response,
)
from app.features.tender_response.infrastructure.repositories.qa_alignment_repository import (
    QaAlignmentRepository,
)
from app.features.tender_response.infrastructure.services.answer_generation_service import (
    AnswerGenerationService,
)
from app.features.tender_response.infrastructure.services.domain_tagging_service import (
    DomainTaggingService,
)
from app.features.tender_response.infrastructure.services.reference_assessment_service import (
    ReferenceAssessmentService,
)
from app.features.tender_response.schemas.responses import (
    QuestionFlags,
    QuestionMetadata,
    QuestionReference,
    QuestionRisk,
    TenderQuestionResponse,
    TenderResponseSummary,
)


def replace_reducer(_old, new):
    """LangGraph reducer that always keeps the most recent state value."""

    return new


class BatchTenderResponseState(TypedDict):
    """State carried across the batch graph that fans out per question."""

    request_id: Annotated[str, replace_reducer]
    session_id: Annotated[str, replace_reducer]
    source_file_name: Annotated[str, replace_reducer]
    alignment_threshold: Annotated[float, replace_reducer]
    questions: Annotated[list[TenderQuestion], replace_reducer]
    question_results: Annotated[list[TenderQuestionResponse], operator.add]
    run_errors: Annotated[list[str], operator.add]
    summary: Annotated[TenderResponseSummary | None, replace_reducer]
    current_question: Annotated[TenderQuestion | None, replace_reducer]
    current_alignment: Annotated[HistoricalAlignmentResult | None, replace_reducer]
    current_assessment: Annotated[ReferenceAssessmentResult | None, replace_reducer]
    current_review: Annotated[ResponseReviewResult | None, replace_reducer]
    current_grounded_result: Annotated[GroundedAnswerResult | None, replace_reducer]
    current_answer: Annotated[str | None, replace_reducer]
    current_result: Annotated[TenderQuestionResponse | None, replace_reducer]


class QuestionProcessingState(TypedDict):
    """State for the per-question subgraph that does retrieval and review."""

    current_question: Annotated[TenderQuestion, replace_reducer]
    alignment_threshold: Annotated[float, replace_reducer]
    current_alignment: Annotated[HistoricalAlignmentResult | None, replace_reducer]
    current_assessment: Annotated[ReferenceAssessmentResult | None, replace_reducer]
    current_review: Annotated[ResponseReviewResult | None, replace_reducer]
    current_grounded_result: Annotated[GroundedAnswerResult | None, replace_reducer]
    current_answer: Annotated[str | None, replace_reducer]
    current_result: Annotated[TenderQuestionResponse | None, replace_reducer]


def _build_reference_payload(
    references: list[HistoricalReference],
    *,
    used_reference_ids: set[str] | None = None,
) -> list[QuestionReference]:
    """Convert domain references into API response models with usage markers."""

    used_ids = used_reference_ids or set()
    return [
        QuestionReference(
            alignment_record_id=reference.record_id,
            alignment_score=reference.alignment_score,
            source_doc=reference.source_doc,
            matched_question=reference.question,
            matched_answer=reference.answer,
            used_for_answer=reference.record_id in used_ids,
        )
        for reference in references
    ]


UNANSWERED_CONFIDENCE_REASON = "Insufficient supporting evidence to answer safely."


def _primary_domain_tag(
    *,
    question: TenderQuestion,
    alignment: HistoricalAlignmentResult,
    domain_tagging_service: DomainTaggingService,
) -> str:
    """Resolve the domain tag even when no answer text was generated."""

    return domain_tagging_service.tag(
        question=question,
        generated_answer="",
        alignment=alignment,
    )


def _unanswered_confidence_reason(
    *,
    assessment: ReferenceAssessmentResult,
    alignment: HistoricalAlignmentResult,
) -> str:
    """Return a fixed message for no-reference cases and a specific reason otherwise."""

    if assessment.grounding_status == "no_reference" or not alignment.references:
        return UNANSWERED_CONFIDENCE_REASON

    return assessment.reason.strip() or UNANSWERED_CONFIDENCE_REASON


def _failed_question_result(question: TenderQuestion, error_message: str) -> TenderQuestionResponse:
    """Build a consistent failure payload when question processing aborts."""

    return TenderQuestionResponse(
        question_id=question.question_id,
        original_question=question.original_question,
        generated_answer=None,
        domain_tag=question.declared_domain.lower() if question.declared_domain else None,
        confidence_level=None,
        historical_alignment_indicator=False,
        status="failed",
        grounding_status="failed",
        flags=QuestionFlags(high_risk=False, inconsistent_response=False),
        risk=QuestionRisk(level="low", reason="No risk assessment for failed processing."),
        metadata=QuestionMetadata(
            source_row_index=question.source_row_index,
            alignment_record_id=None,
            alignment_score=None,
        ),
        references=[],
        error_message=error_message,
        extensions={},
    )


def _create_question_processing_graph(
    *,
    alignment_repository: QaAlignmentRepository,
    answer_generation_service: AnswerGenerationService,
    reference_assessment_service: ReferenceAssessmentService,
    domain_tagging_service: DomainTaggingService,
) -> CompiledStateGraph:
    """Create the per-question graph that retrieves, grounds, and reviews answers."""

    async def retrieve_alignment(
        state: QuestionProcessingState,
    ) -> dict[str, HistoricalAlignmentResult]:
        """Retrieve the closest historical QA records for the current question."""

        # Vector retrieval is the first gate: everything downstream depends on whether
        # we found grounded historical material for this single tender question.
        alignment = await alignment_repository.find_best_match(
            state["current_question"],
            threshold=state["alignment_threshold"],
        )
        return {"current_alignment": alignment}

    async def assess_references(
        state: QuestionProcessingState,
    ) -> dict[str, ReferenceAssessmentResult]:
        """Decide whether the retrieved references are strong enough to answer."""

        # Retrieval and answerability are separate concerns. A close match can still
        # be unusable if it would force the model to invent commitments or evidence.
        assessment = await reference_assessment_service.assess(
            question=state["current_question"],
            references=state["current_alignment"].references,
        )
        return {"current_assessment": assessment}

    def route_after_assessment(state: QuestionProcessingState) -> str:
        """Skip generation when references cannot safely ground an answer."""

        assessment = state["current_assessment"]
        alignment = state["current_alignment"]
        # Only branch into generation when we both have references and the assessment
        # service explicitly approved them as sufficient support.
        if assessment.can_answer and alignment.references:
            return "generate_answer"
        return "finalize_unanswered"

    async def generate_answer(
        state: QuestionProcessingState,
    ) -> dict[str, GroundedAnswerResult | str | ResponseReviewResult]:
        """Generate a grounded answer and review metadata in one call."""

        alignment = state["current_alignment"]
        assessment = state["current_assessment"]
        usable_reference_ids = set(assessment.usable_reference_ids)
        # Keep the generation prompt constrained to references the assessment step
        # marked as safe and relevant, instead of passing every retrieved candidate.
        usable_references = [
            reference
            for reference in alignment.references
            if reference.record_id in usable_reference_ids
        ]
        grounded_result = await answer_generation_service.generate_grounded_response(
            question=state["current_question"],
            usable_references=usable_references,
        )
        return {
            "current_grounded_result": grounded_result,
            "current_answer": grounded_result.generated_answer,
            "current_review": ResponseReviewResult(
                confidence_level=grounded_result.confidence_level,
                confidence_reason=grounded_result.confidence_reason,
                risk_level=grounded_result.risk_level,
                risk_reason=grounded_result.risk_reason,
                inconsistent_response=grounded_result.inconsistent_response,
            ),
        }

    def finalize_unanswered(
        state: QuestionProcessingState,
    ) -> dict[str, TenderQuestionResponse]:
        """Return an unanswered result for questions that could not be safely answered."""

        question = state["current_question"]
        alignment = state["current_alignment"]
        assessment = state["current_assessment"]
        domain_tag = _primary_domain_tag(
            question=question,
            alignment=alignment,
            domain_tagging_service=domain_tagging_service,
        )

        result = TenderQuestionResponse(
            question_id=question.question_id,
            original_question=question.original_question,
            generated_answer=None,
            domain_tag=domain_tag,
            confidence_level="low",
            confidence_reason=_unanswered_confidence_reason(
                assessment=assessment,
                alignment=alignment,
            ),
            historical_alignment_indicator=alignment.matched,
            status="unanswered",
            grounding_status=assessment.grounding_status,
            flags=QuestionFlags(high_risk=False, inconsistent_response=False),
            risk=QuestionRisk(level="low", reason="No grounded answer was produced."),
            metadata=QuestionMetadata(
                source_row_index=question.source_row_index,
                alignment_record_id=alignment.record_id,
                alignment_score=alignment.alignment_score,
            ),
            references=_build_reference_payload(alignment.references),
            error_message=None,
            extensions={"reference_assessment_reason": assessment.reason},
        )
        return {"current_result": result}

    def assess_output(
        state: QuestionProcessingState,
    ) -> dict[str, TenderQuestionResponse]:
        """Translate generated text and review signals into the public response model."""

        question = state["current_question"]
        alignment = state["current_alignment"]
        assessment = state["current_assessment"]
        review = state["current_review"]
        answer = (state["current_answer"] or "").strip()
        usable_reference_ids = set(assessment.usable_reference_ids)
        used_references = [
            reference
            for reference in alignment.references
            if reference.record_id in usable_reference_ids
        ]
        # The highest-priority approved reference acts as the baseline for the
        # heuristic risk checks below.
        primary_reference_answer = used_references[0].answer if used_references else None

        high_risk = detect_high_risk_response(
            question=question.original_question,
            generated_answer=answer,
            historical_alignment_answer=primary_reference_answer,
        )
        inconsistent_response = detect_inconsistent_response(
            generated_answer=answer,
            historical_alignment_answer=primary_reference_answer,
        )
        domain_tag = domain_tagging_service.tag(
            question=question,
            generated_answer=answer,
            alignment=alignment,
        )

        # Drop the answer entirely when safety or consistency checks say it should not ship.
        if not answer or high_risk or inconsistent_response:
            result = TenderQuestionResponse(
                question_id=question.question_id,
                original_question=question.original_question,
                generated_answer=None,
                domain_tag=domain_tag,
                confidence_level="low",
                confidence_reason=(
                    review.confidence_reason
                    if review.confidence_reason
                    else "Confidence is low because the generated answer could not be kept."
                ),
                historical_alignment_indicator=alignment.matched,
                status="unanswered",
                grounding_status="insufficient_reference",
                flags=QuestionFlags(
                    high_risk=review.risk_level == "high" or high_risk,
                    inconsistent_response=review.inconsistent_response
                    or inconsistent_response,
                ),
                risk=QuestionRisk(level=review.risk_level, reason=review.risk_reason),
                metadata=QuestionMetadata(
                    source_row_index=question.source_row_index,
                    alignment_record_id=alignment.record_id,
                    alignment_score=alignment.alignment_score,
                ),
                references=_build_reference_payload(
                    alignment.references,
                    used_reference_ids=usable_reference_ids,
                ),
                error_message=None,
                extensions={
                    "reference_assessment_reason": assessment.reason,
                    "confidence_review_reason": review.confidence_reason,
                },
            )
            return {"current_result": result}

        result = TenderQuestionResponse(
            question_id=question.question_id,
            original_question=question.original_question,
            generated_answer=answer,
            domain_tag=domain_tag,
            confidence_level=review.confidence_level,
            confidence_reason=review.confidence_reason,
            historical_alignment_indicator=alignment.matched,
            status="completed",
            grounding_status="grounded",
            flags=QuestionFlags(
                high_risk=review.risk_level == "high" or high_risk,
                inconsistent_response=review.inconsistent_response or inconsistent_response,
            ),
            risk=QuestionRisk(level=review.risk_level, reason=review.risk_reason),
            metadata=QuestionMetadata(
                source_row_index=question.source_row_index,
                alignment_record_id=alignment.record_id,
                alignment_score=alignment.alignment_score,
            ),
            references=_build_reference_payload(
                alignment.references,
                used_reference_ids=usable_reference_ids,
            ),
            error_message=None,
            extensions={
                "reference_assessment_reason": assessment.reason,
                "confidence_review_reason": review.confidence_reason,
            },
        )
        return {"current_result": result}

    graph = StateGraph(QuestionProcessingState)
    # This subgraph handles one question end-to-end so the batch graph can fan out
    # multiple questions without duplicating the retrieval/review pipeline.
    graph.add_node("retrieve_alignment", retrieve_alignment)
    graph.add_node("assess_references", assess_references)
    graph.add_node("generate_answer", generate_answer)
    graph.add_node("finalize_unanswered", finalize_unanswered)
    graph.add_node("assess_output", assess_output)
    graph.set_entry_point("retrieve_alignment")
    graph.add_edge("retrieve_alignment", "assess_references")
    graph.add_conditional_edges("assess_references", route_after_assessment)
    graph.add_edge("generate_answer", "assess_output")
    graph.add_edge("finalize_unanswered", END)
    graph.add_edge("assess_output", END)

    return graph.compile()


def create_tender_response_graph(
    *,
    alignment_repository: QaAlignmentRepository | None = None,
    answer_generation_service: AnswerGenerationService | None = None,
    reference_assessment_service: ReferenceAssessmentService | None = None,
    domain_tagging_service: DomainTaggingService | None = None,
) -> CompiledStateGraph:
    """Create the batch graph that fans out tender questions and summarizes the run."""

    resolved_alignment_repository = alignment_repository or QaAlignmentRepository()
    resolved_answer_generation_service = answer_generation_service or AnswerGenerationService()
    resolved_reference_assessment_service = (
        reference_assessment_service or ReferenceAssessmentService()
    )
    resolved_domain_tagging_service = domain_tagging_service or DomainTaggingService()
    # Build the single-question pipeline once, then reuse it for every question in the batch.
    question_graph = _create_question_processing_graph(
        alignment_repository=resolved_alignment_repository,
        answer_generation_service=resolved_answer_generation_service,
        reference_assessment_service=resolved_reference_assessment_service,
        domain_tagging_service=resolved_domain_tagging_service,
    )
    checkpointer = MemorySaver()

    def dispatch_questions(state: BatchTenderResponseState) -> list[Send] | str:
        """Fan out a batch into one subgraph invocation per tender question."""

        questions = state.get("questions", [])
        if not questions:
            return "summarize_batch"

        # Each Send spawns an independent run of the per-question graph with clean
        # per-question state while reusing the shared batch-level threshold.
        return [
            Send(
                "process_question",
                {
                    "current_question": question,
                    "alignment_threshold": state["alignment_threshold"],
                    "current_alignment": None,
                    "current_assessment": None,
                    "current_review": None,
                    "current_grounded_result": None,
                    "current_answer": None,
                    "current_result": None,
                },
            )
            for question in questions
        ]

    async def process_question(
        state: BatchTenderResponseState,
    ) -> dict[str, list[TenderQuestionResponse] | list[str]]:
        """Run the question subgraph and convert unexpected exceptions into failures."""

        question = state["current_question"]
        try:
            # The batch graph keeps orchestration concerns only; the heavy lifting
            # stays inside the reusable single-question subgraph.
            result = await question_graph.ainvoke(
                {
                    "current_question": question,
                    "alignment_threshold": state["alignment_threshold"],
                    "current_alignment": None,
                    "current_assessment": None,
                    "current_review": None,
                    "current_grounded_result": None,
                    "current_answer": None,
                    "current_result": None,
                }
            )
            return {"question_results": [result["current_result"]]}
        except Exception as exc:
            # One question failing should not abort the entire uploaded tender file.
            return {
                "question_results": [_failed_question_result(question, str(exc))],
                "run_errors": [f"{question.question_id}: {exc}"],
            }

    def summarize_batch(
        state: BatchTenderResponseState,
    ) -> dict[str, TenderResponseSummary]:
        """Roll up per-question results into a batch summary for the API response."""

        question_results = state.get("question_results", [])
        total_questions = len(question_results)
        failed_questions = sum(item.status == "failed" for item in question_results)
        unanswered_questions = sum(item.status == "unanswered" for item in question_results)
        completed_questions = sum(item.status == "completed" for item in question_results)
        flagged_questions = sum(
            item.flags.high_risk or item.flags.inconsistent_response
            for item in question_results
        )

        # Batch status prefers the most severe aggregate outcome so clients can tell
        # the difference between clean completion, flagged completion, and failures.
        if total_questions == 0:
            overall_status = "completed"
        elif failed_questions == total_questions:
            overall_status = "failed"
        elif failed_questions > 0:
            overall_status = "partial_failure"
        elif unanswered_questions == total_questions:
            overall_status = "unanswered"
        elif flagged_questions > 0:
            overall_status = "completed_with_flags"
        else:
            overall_status = "completed"

        return {
            "summary": TenderResponseSummary(
                total_questions_processed=total_questions,
                flagged_high_risk_or_inconsistent_responses=flagged_questions,
                overall_completion_status=overall_status,
                completed_questions=completed_questions,
                unanswered_questions=unanswered_questions,
                failed_questions=failed_questions,
            )
        }

    graph = StateGraph(BatchTenderResponseState)
    # dispatch_questions itself does not mutate state; it only decides whether the
    # graph should fan out or skip straight to summary for an empty upload.
    graph.add_node("dispatch_questions", lambda state: state)
    graph.add_node("process_question", process_question)
    graph.add_node("summarize_batch", summarize_batch)
    graph.set_entry_point("dispatch_questions")
    graph.add_conditional_edges("dispatch_questions", dispatch_questions)
    graph.add_edge("process_question", "summarize_batch")
    graph.add_edge("summarize_batch", END)

    return graph.compile(checkpointer=checkpointer)
