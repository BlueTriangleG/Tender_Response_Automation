from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.state.agent_state import AgentState
from app.agents.tools.math_tool import add_numbers_tool


def route_after_agent(state: AgentState) -> str:
    """
    Routing function called after agent_node.
    Returns 'tools' if the LLM issued tool calls, END otherwise.
    Defined at module level (not inside create()) so it is unit-testable.
    """
    if not state["messages"]:
        return END
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return END


def create(model: BaseChatModel | None = None) -> CompiledStateGraph:
    """
    Build and compile the ReAct agent graph.

    Accepts an optional model so tests can inject a mock without making real
    API calls. Production code calls create() with no arguments.

    Graph topology:
        START → agent_node ── has tool_calls? ──► tool_node ──┐
                           │                                   │
                           └◄──────────────────────────────────┘
                           └── no tool_calls ──► END
    """
    _tools = [add_numbers_tool]
    _model = (model or ChatOpenAI(model="gpt-4o-mini")).bind_tools(_tools)
    _tools_by_name = {t.name: t for t in _tools}
    # Each Agent gets its own MemorySaver. Session isolation is correct because
    # AgentManager reuses Agent instances per session_id. Upgrade to PostgresSaver
    # for persistence across restarts or multi-process deployments.
    _checkpointer = MemorySaver()

    async def agent_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        """Call the LLM with the full message history and all bound tools."""
        response = await _model.ainvoke(state["messages"], config)
        return {"messages": [response]}

    async def tool_node(state: AgentState) -> dict[str, Any]:
        """
        Execute every tool call from the last AIMessage.
        Failures are caught per-call so one bad tool does not abort the loop.
        """
        last_msg = state["messages"][-1]
        if not isinstance(last_msg, AIMessage):
            return {"messages": []}
        results: list[ToolMessage] = []

        for tc in last_msg.tool_calls:
            tool = _tools_by_name.get(tc["name"])
            if tool is None:
                content = f"Error: unknown tool '{tc['name']}'"
            else:
                try:
                    content = str(await tool.ainvoke(tc["args"]))
                except Exception as exc:
                    content = f"Error: {exc}"

            results.append(ToolMessage(content=content, tool_call_id=tc["id"]))

        return {"messages": results}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=_checkpointer)
