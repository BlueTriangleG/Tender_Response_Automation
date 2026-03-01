"""Batch graph wiring for the parallel tender-response workflow."""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.features.tender_response.infrastructure.services.answer_generation_service import (
    AnswerGenerationService,
)
from app.features.tender_response.infrastructure.services.conflict_review_service import (
    ConflictReviewService,
    NoopConflictReviewService,
)
from app.features.tender_response.infrastructure.services.domain_tagging_service import (
    DomainTaggingService,
)
from app.features.tender_response.infrastructure.services.historical_evidence_service import (
    HistoricalEvidenceService,
)
from app.features.tender_response.infrastructure.services.reference_assessment_service import (
    ReferenceAssessmentService,
)
from app.features.tender_response.infrastructure.workflows.common.state import (
    BatchTenderResponseState,
)
from app.features.tender_response.infrastructure.workflows.parallel.nodes import (
    apply_conflicts,
    make_process_question_node,
    make_review_conflict_group_node,
    prepare_conflict_review,
    summarize_batch,
)
from app.features.tender_response.infrastructure.workflows.parallel.question_graph import (
    create_question_processing_graph,
)
from app.features.tender_response.infrastructure.workflows.parallel.routing import (
    dispatch_conflict_review_jobs,
    dispatch_questions,
)


def create_parallel_tender_response_graph(
    *,
    alignment_repository: HistoricalEvidenceService | None = None,
    answer_generation_service: AnswerGenerationService | None = None,
    reference_assessment_service: ReferenceAssessmentService | None = None,
    domain_tagging_service: DomainTaggingService | None = None,
    conflict_review_service: ConflictReviewService | None = None,
) -> CompiledStateGraph:
    """Create the batch graph that fans out tender questions and summarizes the run."""

    resolved_alignment_repository = alignment_repository or HistoricalEvidenceService()
    resolved_answer_generation_service = answer_generation_service or AnswerGenerationService()
    resolved_reference_assessment_service = (
        reference_assessment_service or ReferenceAssessmentService()
    )
    resolved_domain_tagging_service = domain_tagging_service or DomainTaggingService()
    resolved_conflict_review_service = conflict_review_service or NoopConflictReviewService()
    question_graph = create_question_processing_graph(
        alignment_repository=resolved_alignment_repository,
        answer_generation_service=resolved_answer_generation_service,
        reference_assessment_service=resolved_reference_assessment_service,
        domain_tagging_service=resolved_domain_tagging_service,
    )
    checkpointer = MemorySaver()

    graph = StateGraph(BatchTenderResponseState)
    graph.add_node("process_question", make_process_question_node(question_graph))
    graph.add_node("prepare_conflict_review", prepare_conflict_review)
    graph.add_node(
        "review_conflict_group",
        make_review_conflict_group_node(resolved_conflict_review_service),
    )
    graph.add_node("apply_conflicts", apply_conflicts)
    graph.add_node("summarize_batch", summarize_batch)
    graph.add_conditional_edges(START, dispatch_questions)
    graph.add_edge("process_question", "prepare_conflict_review")
    graph.add_conditional_edges("prepare_conflict_review", dispatch_conflict_review_jobs)
    graph.add_edge("review_conflict_group", "apply_conflicts")
    graph.add_edge("apply_conflicts", "summarize_batch")
    graph.add_edge("summarize_batch", END)

    return graph.compile(checkpointer=checkpointer)
