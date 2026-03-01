"""Workflow registry for tender-response workflow families."""

from functools import lru_cache
from typing import Literal

from langgraph.graph.state import CompiledStateGraph

from app.features.tender_response.infrastructure.services.conflict_review_service import (
    ConflictReviewService,
)
from app.features.tender_response.infrastructure.workflows.parallel.graph import (
    create_parallel_tender_response_graph,
)
from app.features.tender_response.infrastructure.workflows.sequential.graph import (
    create_sequential_tender_response_graph,
)

TenderWorkflowName = Literal["parallel", "sequential"]


class TenderWorkflowRegistry:
    """Resolve compiled graphs by workflow family name."""

    def get(self, workflow_name: TenderWorkflowName) -> CompiledStateGraph:
        """Return the compiled workflow for the requested family."""

        if workflow_name == "parallel":
            return self._parallel_graph()
        if workflow_name == "sequential":
            return self._sequential_graph()
        raise ValueError(f"Unsupported tender workflow: {workflow_name}")

    @staticmethod
    @lru_cache
    def _parallel_graph() -> CompiledStateGraph:
        return create_parallel_tender_response_graph(
            conflict_review_service=ConflictReviewService()
        )

    @staticmethod
    @lru_cache
    def _sequential_graph() -> CompiledStateGraph:
        return create_sequential_tender_response_graph()
