from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict


def smart_message_reducer(old: list[BaseMessage], new: list[BaseMessage]) -> list[BaseMessage]:
    """
    Default: concatenate (standard LangGraph behaviour).
    Replace mode: if new[0] carries _replace=True, discard old list entirely.
    Used after summarisation to atomically swap the message history.
    """
    if new and getattr(new[0], "_replace", False):
        return [m for m in new if not getattr(m, "_replace", False)]
    return old + new


def merge_reducer(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Shallow-merge two dicts; new values overwrite old."""
    return {**(old or {}), **(new or {})}


def replace_reducer(old: Any, new: Any) -> Any:  # noqa: ARG001
    """Always return the incoming value, discarding the previous."""
    return new


class AgentState(TypedDict):
    """
    Shared state threaded through every node in the LangGraph workflow.
    Each field declares an explicit reducer so LangGraph knows how to merge
    partial updates returned by nodes into the canonical state object.

    Fields used by current nodes:
      - messages: populated by agent_node and tool_node

    Fields reserved for future nodes (summarisation, error handling):
      - workflow_metadata, final_response, error
    """

    messages: Annotated[list[BaseMessage], smart_message_reducer]
    workflow_metadata: Annotated[dict[str, Any], merge_reducer]
    final_response: Annotated[str | None, replace_reducer]
    error: Annotated[str | None, replace_reducer]
