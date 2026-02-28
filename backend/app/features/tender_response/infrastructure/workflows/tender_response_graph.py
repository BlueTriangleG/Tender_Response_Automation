import operator
from typing import Annotated

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send
from typing_extensions import TypedDict

from app.features.tender_response.domain.models import (
    HistoricalAlignmentResult,
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
from app.features.tender_response.infrastructure.services.confidence_service import (
    ConfidenceService,
)
from app.features.tender_response.infrastructure.services.domain_tagging_service import (
    DomainTaggingService,
)
from app.features.tender_response.schemas.responses import (
    QuestionFlags,
    QuestionMetadata,
    TenderQuestionResponse,
    TenderResponseSummary,
)


def replace_reducer(_old, new):
    return new


class BatchTenderResponseState(TypedDict):
    session_id: Annotated[str, replace_reducer]
    source_file_name: Annotated[str, replace_reducer]
    alignment_threshold: Annotated[float, replace_reducer]
    questions: Annotated[list[TenderQuestion], replace_reducer]
    question_results: Annotated[list[TenderQuestionResponse], operator.add]
    run_errors: Annotated[list[str], operator.add]
    summary: Annotated[TenderResponseSummary | None, replace_reducer]
    current_question: Annotated[TenderQuestion | None, replace_reducer]
    current_alignment: Annotated[HistoricalAlignmentResult | None, replace_reducer]
    current_answer: Annotated[str | None, replace_reducer]
    current_result: Annotated[TenderQuestionResponse | None, replace_reducer]


class QuestionProcessingState(TypedDict):
    current_question: Annotated[TenderQuestion, replace_reducer]
    alignment_threshold: Annotated[float, replace_reducer]
    current_alignment: Annotated[HistoricalAlignmentResult | None, replace_reducer]
    current_answer: Annotated[str | None, replace_reducer]
    current_result: Annotated[TenderQuestionResponse | None, replace_reducer]


def _failed_question_result(question: TenderQuestion, error_message: str) -> TenderQuestionResponse:
    return TenderQuestionResponse(
        question_id=question.question_id,
        original_question=question.original_question,
        generated_answer=None,
        domain_tag=question.declared_domain.lower() if question.declared_domain else None,
        confidence_level=None,
        historical_alignment_indicator=False,
        status="failed",
        flags=QuestionFlags(high_risk=False, inconsistent_response=False),
        metadata=QuestionMetadata(
            source_row_index=question.source_row_index,
            alignment_record_id=None,
            alignment_score=None,
        ),
        error_message=error_message,
        extensions={},
    )


def _create_question_processing_graph(
    *,
    alignment_repository: QaAlignmentRepository,
    answer_generation_service: AnswerGenerationService,
    domain_tagging_service: DomainTaggingService,
    confidence_service: ConfidenceService,
) -> CompiledStateGraph:
    async def retrieve_alignment(
        state: QuestionProcessingState,
    ) -> dict[str, HistoricalAlignmentResult]:
        alignment = await alignment_repository.find_best_match(
            state["current_question"],
            threshold=state["alignment_threshold"],
        )
        return {"current_alignment": alignment}

    def route_after_alignment(state: QuestionProcessingState) -> str:
        alignment = state.get("current_alignment")
        if alignment and alignment.matched:
            return "generate_with_alignment"
        return "generate_without_alignment"

    async def generate_with_alignment(
        state: QuestionProcessingState,
    ) -> dict[str, str]:
        answer = await answer_generation_service.generate_with_alignment(
            question=state["current_question"],
            alignment=state["current_alignment"],
        )
        return {"current_answer": answer}

    async def generate_without_alignment(
        state: QuestionProcessingState,
    ) -> dict[str, str]:
        answer = await answer_generation_service.generate_without_alignment(
            state["current_question"]
        )
        return {"current_answer": answer}

    def assess_output(
        state: QuestionProcessingState,
    ) -> dict[str, TenderQuestionResponse]:
        question = state["current_question"]
        alignment = state["current_alignment"]
        answer = state["current_answer"] or ""

        high_risk = detect_high_risk_response(
            question=question.original_question,
            generated_answer=answer,
            historical_alignment_answer=alignment.answer if alignment else None,
        )
        inconsistent_response = detect_inconsistent_response(
            generated_answer=answer,
            historical_alignment_answer=alignment.answer if alignment else None,
        )
        domain_tag = domain_tagging_service.tag(
            question=question,
            generated_answer=answer,
            alignment=alignment,
        )
        confidence_level = confidence_service.classify(
            alignment=alignment,
            high_risk=high_risk,
            inconsistent_response=inconsistent_response,
        )

        result = TenderQuestionResponse(
            question_id=question.question_id,
            original_question=question.original_question,
            generated_answer=answer,
            domain_tag=domain_tag,
            confidence_level=confidence_level,
            historical_alignment_indicator=alignment.matched,
            status="completed",
            flags=QuestionFlags(
                high_risk=high_risk,
                inconsistent_response=inconsistent_response,
            ),
            metadata=QuestionMetadata(
                source_row_index=question.source_row_index,
                alignment_record_id=alignment.record_id,
                alignment_score=alignment.alignment_score,
            ),
            error_message=None,
            extensions={},
        )
        return {"current_result": result}

    graph = StateGraph(QuestionProcessingState)
    graph.add_node("retrieve_alignment", retrieve_alignment)
    graph.add_node("generate_with_alignment", generate_with_alignment)
    graph.add_node("generate_without_alignment", generate_without_alignment)
    graph.add_node("assess_output", assess_output)
    graph.set_entry_point("retrieve_alignment")
    graph.add_conditional_edges("retrieve_alignment", route_after_alignment)
    graph.add_edge("generate_with_alignment", "assess_output")
    graph.add_edge("generate_without_alignment", "assess_output")
    graph.add_edge("assess_output", END)

    return graph.compile()


def create_tender_response_graph(
    *,
    alignment_repository: QaAlignmentRepository | None = None,
    answer_generation_service: AnswerGenerationService | None = None,
    domain_tagging_service: DomainTaggingService | None = None,
    confidence_service: ConfidenceService | None = None,
) -> CompiledStateGraph:
    resolved_alignment_repository = alignment_repository or QaAlignmentRepository()
    resolved_answer_generation_service = answer_generation_service or AnswerGenerationService()
    resolved_domain_tagging_service = domain_tagging_service or DomainTaggingService()
    resolved_confidence_service = confidence_service or ConfidenceService()
    question_graph = _create_question_processing_graph(
        alignment_repository=resolved_alignment_repository,
        answer_generation_service=resolved_answer_generation_service,
        domain_tagging_service=resolved_domain_tagging_service,
        confidence_service=resolved_confidence_service,
    )
    checkpointer = MemorySaver()

    def dispatch_questions(
        state: BatchTenderResponseState,
    ) -> list[Send] | str:
        questions = state.get("questions", [])
        if not questions:
            return "summarize_batch"

        return [
            Send(
                "process_question",
                {
                    "current_question": question,
                    "alignment_threshold": state["alignment_threshold"],
                    "question_results": [],
                    "run_errors": [],
                    "summary": None,
                    "current_alignment": None,
                    "current_answer": None,
                    "current_result": None,
                },
            )
            for question in questions
        ]

    async def process_question(
        state: BatchTenderResponseState,
    ) -> dict[str, list[TenderQuestionResponse] | list[str]]:
        question = state["current_question"]
        try:
            result = await question_graph.ainvoke(
                {
                    "current_question": question,
                    "alignment_threshold": state["alignment_threshold"],
                    "current_alignment": None,
                    "current_answer": None,
                    "current_result": None,
                }
            )
            return {"question_results": [result["current_result"]]}
        except Exception as exc:
            return {
                "question_results": [_failed_question_result(question, str(exc))],
                "run_errors": [f"{question.question_id}: {exc}"],
            }

    def summarize_batch(
        state: BatchTenderResponseState,
    ) -> dict[str, TenderResponseSummary]:
        question_results = state.get("question_results", [])
        total_questions = len(question_results)
        failed_questions = sum(item.status == "failed" for item in question_results)
        completed_questions = total_questions - failed_questions
        flagged_questions = sum(
            item.flags.high_risk or item.flags.inconsistent_response
            for item in question_results
        )

        if total_questions == 0:
            overall_status = "completed"
        elif failed_questions == total_questions:
            overall_status = "failed"
        elif failed_questions > 0:
            overall_status = "partial_failure"
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
                failed_questions=failed_questions,
            )
        }

    graph = StateGraph(BatchTenderResponseState)
    graph.add_node("dispatch_questions", lambda state: state)
    graph.add_node("process_question", process_question)
    graph.add_node("summarize_batch", summarize_batch)
    graph.set_entry_point("dispatch_questions")
    graph.add_conditional_edges("dispatch_questions", dispatch_questions)
    graph.add_edge("process_question", "summarize_batch")
    graph.add_edge("summarize_batch", END)

    return graph.compile(checkpointer=checkpointer)
