"""Workflow-local debug helpers for tender-response processing."""

from app.core.config import settings


def debug_log(message: str) -> None:
    """Emit a workflow debug line only when the feature flag is enabled."""

    if settings.tender_workflow_debug:
        print(f"[tender_response] {message}")

