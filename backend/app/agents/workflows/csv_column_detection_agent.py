from typing import Any

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from openai import AsyncOpenAI

from app.agents.state.agent_state import AgentState
from app.core.config import settings


def create(
    client: AsyncOpenAI | None = None,
    model: str | None = None,
) -> CompiledStateGraph:
    openai_client = client or AsyncOpenAI()
    openai_model = model or settings.openai_csv_column_model
    checkpointer = MemorySaver()

    async def agent_node(state: AgentState) -> dict[str, Any]:
        last_message = state["messages"][-1]
        prompt = last_message.content if isinstance(last_message.content, str) else str(last_message.content)
        response = await openai_client.chat.completions.create(
            model=openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Return only strict JSON with keys question_col, answer_col, domain_col."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or ""
        return {"messages": [AIMessage(content=content)]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.set_entry_point("agent")
    graph.add_edge("agent", END)

    return graph.compile(checkpointer=checkpointer)
