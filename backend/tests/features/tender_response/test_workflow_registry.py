import pytest

from app.features.tender_response.infrastructure.workflows.registry import (
    TenderWorkflowRegistry,
)


def test_registry_rejects_unimplemented_workflow_names() -> None:
    registry = TenderWorkflowRegistry()

    with pytest.raises(ValueError, match="Unsupported tender workflow: sequential"):
        registry.get("sequential")  # type: ignore[arg-type]
