"""Single-question subgraph builder for the parallel tender-response workflow."""

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.features.tender_response.infrastructure.services.answer_generation_service import (
    AnswerGenerationService,
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
    QuestionProcessingState,
)
from app.features.tender_response.infrastructure.workflows.parallel.nodes import (
    make_assess_output_node,
    make_assess_references_node,
    make_fail_generation_node,
    make_finalize_unanswered_node,
    make_generate_answer_node,
    make_retrieve_alignment_node,
)
from app.features.tender_response.infrastructure.workflows.parallel.routing import (
    route_after_assessment,
    route_after_output_validation,
)


def create_question_processing_graph(
    *,
    alignment_repository: HistoricalEvidenceService,
    answer_generation_service: AnswerGenerationService,
    reference_assessment_service: ReferenceAssessmentService,
    domain_tagging_service: DomainTaggingService,
) -> CompiledStateGraph:
    """Create the per-question graph that retrieves, grounds, and validates answers."""

    graph = StateGraph(QuestionProcessingState)
    graph.add_node("retrieve_alignment", make_retrieve_alignment_node(alignment_repository))
    graph.add_node(
        "assess_references",
        make_assess_references_node(reference_assessment_service),
    )
    graph.add_node("generate_answer", make_generate_answer_node(answer_generation_service))
    graph.add_node(
        "finalize_unanswered",
        make_finalize_unanswered_node(domain_tagging_service),
    )
    graph.add_node("assess_output", make_assess_output_node(domain_tagging_service))
    graph.add_node("fail_generation", make_fail_generation_node(domain_tagging_service))
    graph.set_entry_point("retrieve_alignment")
    graph.add_edge("retrieve_alignment", "assess_references")
    graph.add_conditional_edges("assess_references", route_after_assessment)
    graph.add_edge("generate_answer", "assess_output")
    graph.add_edge("finalize_unanswered", END)
    graph.add_conditional_edges("assess_output", route_after_output_validation)
    graph.add_edge("fail_generation", END)

    return graph.compile()
