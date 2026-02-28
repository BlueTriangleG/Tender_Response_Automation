from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from app.agents.workflows.react_agent import create as create_workflow


class Agent:
    """
    One instance per conversation session.

    Wraps a compiled LangGraph workflow. The session_id is passed as
    thread_id so the MemorySaver checkpointer can persist and restore the
    full message history across calls within the same session.
    """

    def __init__(self, session_id: str) -> None:
        self.session_id: str = session_id
        self.workflow: CompiledStateGraph = create_workflow()

    def _config(self) -> RunnableConfig:
        return {"configurable": {"thread_id": self.session_id}}

    async def chat(self, message: str) -> str:
        """
        Send a message through the ReAct workflow and return the final response.
        The workflow resolves any tool calls internally before returning.
        """
        inputs = {"messages": [HumanMessage(content=message)]}
        result = await self.workflow.ainvoke(inputs, config=self._config())
        messages = result.get("messages", [])
        if not messages:
            raise RuntimeError("Workflow returned no messages")
        content = messages[-1].content
        if not isinstance(content, str):
            raise RuntimeError(f"Expected str response, got {type(content).__name__}")
        return content
