"""Workflow-local debug helpers for tender-response processing."""

from typing import Any

from langchain_core.messages import BaseMessage

from app.core.config import settings


def debug_log(message: str) -> None:
    """Emit a workflow debug line only when the feature flag is enabled."""

    if settings.tender_workflow_debug:
        print(f"[tender_response] {message}")


def print_llm_bug_report(
    *,
    service: str,
    error: str,
    messages: list[BaseMessage],
    metadata: dict[str, Any] | None = None,
) -> None:
    """Print a console bug report with the full LLM request when a call fails."""

    print("[tender_response] BUG REPORT START")
    print(f"[tender_response] service={service}")
    print(f"[tender_response] error={error}")
    if metadata:
        for key, value in metadata.items():
            print(f"[tender_response] {key}={value}")
    print("[tender_response] request_messages_begin")
    for index, message in enumerate(messages, start=1):
        print(f"[tender_response] message[{index}] role={message.type}")
        print(f"[tender_response] message[{index}] content_begin")
        print(_stringify_message_content(message.content))
        print(f"[tender_response] message[{index}] content_end")
    print("[tender_response] request_messages_end")
    print("[tender_response] BUG REPORT END")


def _stringify_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    return str(content)
