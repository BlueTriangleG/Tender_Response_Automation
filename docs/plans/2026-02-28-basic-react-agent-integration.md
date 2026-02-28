# Basic LangGraph ReAct Agent Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate a minimal LangGraph ReAct agent into the existing FastAPI backend, exposing `POST /api/agent/chat` backed by an `agent_node → tool_node` loop with a real `add_numbers` math tool.

**Architecture:** The `agents/` module owns all workflow/state/node code as a self-contained toolkit. A thin API route calls `agent_manager` directly — no service layer at this scope (YAGNI). `MemorySaver` persists conversation state per `session_id` (= `thread_id`) for the process lifetime.

**Tech Stack:** FastAPI · LangGraph · LangChain OpenAI · pytest · pytest-asyncio

---

## Directory Map

```
backend/
├── app/
│   ├── agents/
│   │   ├── __init__.py              (exists, empty)
│   │   ├── agent.py                 NEW
│   │   ├── agent_manager.py         NEW
│   │   ├── state/
│   │   │   ├── __init__.py          NEW
│   │   │   └── agent_state.py       NEW
│   │   ├── tools/
│   │   │   ├── __init__.py          NEW
│   │   │   └── math_tool.py         NEW
│   │   └── workflows/
│   │       ├── __init__.py          NEW
│   │       └── react_agent.py       NEW
│   ├── api/routes/
│   │   ├── __init__.py              MODIFY
│   │   ├── health.py                (unchanged)
│   │   └── agent.py                 NEW
│   └── schemas/
│       ├── health.py                (unchanged)
│       └── agent.py                 NEW
└── tests/
    ├── agents/
    │   ├── state/
    │   │   └── test_agent_state.py  NEW
    │   ├── workflows/
    │   │   └── test_react_agent.py  NEW
    │   ├── test_agent.py            NEW
    │   └── test_agent_manager.py    NEW
    └── api/routes/
        └── test_agent_route.py      NEW
```

---

## Task 1: Add Dependencies

**Files:**
- Modify: `backend/pyproject.toml`

**Step 1: Update pyproject.toml**

`dependencies` block:

```toml
dependencies = [
    "fastapi>=0.134.0,<1.0.0",
    "langchain-core>=0.3.0,<1.0.0",
    "langchain-openai>=0.3.0,<1.0.0",
    "langgraph>=0.3.0,<1.0.0",
    "pydantic-settings>=2.10.1,<3.0.0",
    "python-dotenv>=1.0.0,<2.0.0",
    "uvicorn[standard]>=0.41.0,<1.0.0",
]
```

`[dependency-groups]` dev block:

```toml
[dependency-groups]
dev = [
    "httpx>=0.28.1,<1.0.0",
    "mypy>=1.19.1,<2.0.0",
    "pytest>=9.0.2,<10.0.0",
    "pytest-asyncio>=0.24.0,<1.0.0",
    "ruff>=0.15.4,<1.0.0",
]
```

Add `asyncio_mode = "auto"` to the pytest block:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
testpaths = ["tests"]
```

**Step 2: Install**

```bash
cd backend
uv sync
```

Expected: resolves without conflicts.

**Step 3: Create .env**

Create `backend/.env`:

```
OPENAI_API_KEY=sk-your-key-here
```

> `ChatOpenAI` reads `OPENAI_API_KEY` from the environment automatically. Keep this file out of version control.

**Step 4: Verify existing tests still pass**

```bash
uv run pytest -v
```

Expected: 2 tests PASS.

**Step 5: Commit**

```bash
git add backend/pyproject.toml
git commit -m "feat: add langgraph, langchain-openai, pytest-asyncio dependencies"
```

---

## Task 2: AgentState

**Files:**
- Create: `backend/app/agents/state/__init__.py`
- Create: `backend/app/agents/state/agent_state.py`
- Create: `backend/tests/agents/state/test_agent_state.py`

The only function worth testing here is `smart_message_reducer` — it has a non-trivial replace-mode branch. `merge_reducer` and `replace_reducer` are one-liners with no logic.

**Step 1: Write the failing tests**

Create `backend/tests/agents/state/test_agent_state.py`:

```python
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.state.agent_state import smart_message_reducer


def test_smart_message_reducer_appends_by_default() -> None:
    old = [HumanMessage(content="hello")]
    new = [AIMessage(content="world")]

    result = smart_message_reducer(old, new)

    assert len(result) == 2
    assert result[0].content == "hello"
    assert result[1].content == "world"


def test_smart_message_reducer_replaces_when_first_message_has_replace_flag() -> None:
    old = [HumanMessage(content="stale"), HumanMessage(content="also stale")]
    marker = AIMessage(content="")
    marker._replace = True  # type: ignore[attr-defined]
    fresh = AIMessage(content="fresh summary")

    result = smart_message_reducer(old, [marker, fresh])

    # old list is discarded; marker itself is filtered out; only fresh remains
    assert len(result) == 1
    assert result[0].content == "fresh summary"
```

**Step 2: Run to confirm failure**

```bash
uv run pytest tests/agents/state/test_agent_state.py -v
```

Expected: `ModuleNotFoundError`

**Step 3: Implement**

Create `backend/app/agents/state/__init__.py` — empty.

Create `backend/app/agents/state/agent_state.py`:

```python
from typing import Annotated, Any, Optional

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
    """

    messages: Annotated[list[BaseMessage], smart_message_reducer]
    workflow_metadata: Annotated[dict[str, Any], merge_reducer]
    final_response: Annotated[Optional[str], replace_reducer]
    error: Annotated[Optional[str], replace_reducer]
```

**Step 4: Run tests**

```bash
uv run pytest tests/agents/state/test_agent_state.py -v
```

Expected: 2 tests PASS.

**Step 5: Commit**

```bash
git add app/agents/state/ tests/agents/state/
git commit -m "feat: add AgentState with smart_message, merge, and replace reducers"
```

---

## Task 3: Math Tool

**Files:**
- Create: `backend/app/agents/tools/__init__.py`
- Create: `backend/app/agents/tools/math_tool.py`

No dedicated test file. The function is `return a + b` — there is no logic to assert. The tool's correctness will be covered by the workflow smoke test at the end.

**Step 1: Create the package init**

Create `backend/app/agents/tools/__init__.py` — empty.

**Step 2: Implement**

Create `backend/app/agents/tools/math_tool.py`:

```python
from langchain_core.tools import StructuredTool
from pydantic import BaseModel


class AddNumbersInput(BaseModel):
    """Input schema for the add_numbers tool."""

    a: int
    b: int


async def add_numbers(a: int, b: int) -> int:
    """Add two integers and return their sum."""
    return a + b


add_numbers_tool = StructuredTool.from_function(
    coroutine=add_numbers,
    name="add_numbers",
    description="Add two integers together and return the sum.",
    args_schema=AddNumbersInput,
)
```

**Step 3: Commit**

```bash
git add app/agents/tools/
git commit -m "feat: add add_numbers StructuredTool"
```

---

## Task 4: ReAct Workflow

**Files:**
- Create: `backend/app/agents/workflows/__init__.py`
- Create: `backend/app/agents/workflows/react_agent.py`
- Create: `backend/tests/agents/workflows/test_react_agent.py`

`route_after_agent` is module-level (not a closure) so it can be tested independently. It is worth testing because it directly controls which branch the graph takes.

**Step 1: Write the failing tests**

Create `backend/tests/agents/workflows/test_react_agent.py`:

```python
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END
from langgraph.graph.state import CompiledStateGraph

from app.agents.state.agent_state import AgentState
from app.agents.workflows.react_agent import create, route_after_agent


def _state(messages: list) -> AgentState:
    return AgentState(messages=messages, workflow_metadata={}, final_response=None, error=None)


def test_route_after_agent_returns_tools_when_last_message_has_tool_calls() -> None:
    tool_call = {"id": "c1", "name": "add_numbers", "args": {"a": 1, "b": 2}, "type": "tool_call"}
    state = _state([AIMessage(content="", tool_calls=[tool_call])])

    assert route_after_agent(state) == "tools"


def test_route_after_agent_returns_end_when_no_tool_calls() -> None:
    state = _state([AIMessage(content="The answer is 7.")])

    assert route_after_agent(state) == END


def test_create_returns_compiled_state_graph() -> None:
    mock_model = MagicMock()
    mock_model.bind_tools.return_value = mock_model

    workflow = create(model=mock_model)

    assert isinstance(workflow, CompiledStateGraph)
```

**Step 2: Run to confirm failure**

```bash
uv run pytest tests/agents/workflows/test_react_agent.py -v
```

Expected: `ModuleNotFoundError`

**Step 3: Create the package init**

Create `backend/app/agents/workflows/__init__.py` — empty.

**Step 4: Implement**

Create `backend/app/agents/workflows/react_agent.py`:

```python
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
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
        last = state["messages"][-1]
        results: list[ToolMessage] = []

        for tc in last.tool_calls:
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
```

**Step 5: Run tests**

```bash
uv run pytest tests/agents/workflows/test_react_agent.py -v
```

Expected: 3 tests PASS.

**Step 6: Commit**

```bash
git add app/agents/workflows/ tests/agents/workflows/
git commit -m "feat: add ReAct workflow with agent_node, tool_node, and conditional routing"
```

---

## Task 5: Agent Class

**Files:**
- Create: `backend/app/agents/agent.py`
- Create: `backend/tests/agents/test_agent.py`

Worth testing: that `chat()` passes `session_id` as `thread_id` in the LangGraph config. This is the contract between `Agent` and the checkpointer — if it breaks, session memory silently stops working.

**Step 1: Write the failing tests**

Create `backend/tests/agents/test_agent.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.agent import Agent


async def test_agent_chat_returns_last_message_content() -> None:
    mock_workflow = MagicMock()
    mock_workflow.ainvoke = AsyncMock(
        return_value={
            "messages": [HumanMessage(content="3+4"), AIMessage(content="The sum is 7.")]
        }
    )

    with patch("app.agents.agent.create_workflow", return_value=mock_workflow):
        agent = Agent(session_id="s1")
        result = await agent.chat("3+4")

    assert result == "The sum is 7."


async def test_agent_chat_passes_session_id_as_thread_id() -> None:
    """session_id must become thread_id in the LangGraph config so the
    MemorySaver checkpointer can store and restore state per session."""
    mock_workflow = MagicMock()
    mock_workflow.ainvoke = AsyncMock(
        return_value={"messages": [AIMessage(content="ok")]}
    )

    with patch("app.agents.agent.create_workflow", return_value=mock_workflow):
        agent = Agent(session_id="my-session")
        await agent.chat("hello")

    _, call_kwargs = mock_workflow.ainvoke.call_args
    config = call_kwargs["config"]
    assert config["configurable"]["thread_id"] == "my-session"
```

**Step 2: Run to confirm failure**

```bash
uv run pytest tests/agents/test_agent.py -v
```

Expected: `ModuleNotFoundError`

**Step 3: Implement**

Create `backend/app/agents/agent.py`:

```python
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
        return result["messages"][-1].content
```

**Step 4: Run tests**

```bash
uv run pytest tests/agents/test_agent.py -v
```

Expected: 2 tests PASS.

**Step 5: Commit**

```bash
git add app/agents/agent.py tests/agents/test_agent.py
git commit -m "feat: add Agent class with session-scoped thread_id config"
```

---

## Task 6: AgentManager

**Files:**
- Create: `backend/app/agents/agent_manager.py`
- Create: `backend/tests/agents/test_agent_manager.py`

Worth testing: that the same session_id returns the same instance (reuse), and different session_ids produce different instances (isolation). These properties are the entire point of the manager.

**Step 1: Write the failing tests**

Create `backend/tests/agents/test_agent_manager.py`:

```python
from unittest.mock import MagicMock, patch

from app.agents.agent_manager import AgentManager


def test_get_agent_creates_new_agent_for_unknown_session() -> None:
    manager = AgentManager()

    with patch("app.agents.agent_manager.Agent") as MockAgent:
        MockAgent.return_value = MagicMock()
        manager.get_agent("session-1")

    MockAgent.assert_called_once_with(session_id="session-1")


def test_get_agent_returns_same_instance_for_same_session() -> None:
    manager = AgentManager()

    with patch("app.agents.agent_manager.Agent") as MockAgent:
        MockAgent.return_value = MagicMock()
        first = manager.get_agent("session-1")
        second = manager.get_agent("session-1")

    assert first is second
    MockAgent.assert_called_once()  # constructed only once


def test_get_agent_creates_separate_instances_for_different_sessions() -> None:
    manager = AgentManager()

    with patch("app.agents.agent_manager.Agent") as MockAgent:
        MockAgent.side_effect = [MagicMock(), MagicMock()]
        a = manager.get_agent("session-a")
        b = manager.get_agent("session-b")

    assert a is not b
```

**Step 2: Run to confirm failure**

```bash
uv run pytest tests/agents/test_agent_manager.py -v
```

Expected: `ModuleNotFoundError`

**Step 3: Implement**

Create `backend/app/agents/agent_manager.py`:

```python
from app.agents.agent import Agent


class AgentManager:
    """
    Module-level singleton that maps session_id → Agent instance.

    Agents are created on first access and reused for all subsequent requests
    with the same session_id, preserving conversation history via the
    LangGraph MemorySaver checkpointer.

    Production note: replace the in-process dict with a distributed store
    (e.g. Redis) for multi-process deployments.
    """

    def __init__(self) -> None:
        self.agents: dict[str, Agent] = {}

    def get_agent(self, session_id: str) -> Agent:
        """Return the existing Agent for this session, or create a new one."""
        if session_id not in self.agents:
            self.agents[session_id] = Agent(session_id=session_id)
        return self.agents[session_id]

    def remove_agent(self, session_id: str) -> None:
        """Remove an agent from the pool. No-op if the session does not exist."""
        self.agents.pop(session_id, None)


agent_manager = AgentManager()
```

**Step 4: Run tests**

```bash
uv run pytest tests/agents/test_agent_manager.py -v
```

Expected: 3 tests PASS.

**Step 5: Commit**

```bash
git add app/agents/agent_manager.py tests/agents/test_agent_manager.py
git commit -m "feat: add AgentManager singleton for session-scoped Agent lifecycle"
```

---

## Task 7: Schemas, API Route, and Wire-Up

**Files:**
- Create: `backend/app/schemas/agent.py`
- Create: `backend/app/api/routes/agent.py`
- Modify: `backend/app/api/routes/__init__.py`
- Create: `backend/tests/api/routes/test_agent_route.py`

Schemas are straightforward Pydantic models with no custom logic — no unit tests needed. The route test covers the full HTTP contract including schema validation.

**Step 1: Write the failing tests**

Create `backend/tests/api/routes/test_agent_route.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


def test_chat_returns_200_with_response_and_session_id() -> None:
    client = TestClient(app)
    mock_agent = MagicMock()
    mock_agent.chat = AsyncMock(return_value="The sum is 7.")

    with patch("app.api.routes.agent.agent_manager") as mock_manager:
        mock_manager.get_agent.return_value = mock_agent
        response = client.post(
            "/api/agent/chat",
            json={"message": "What is 3 + 4?", "session_id": "test-session"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "The sum is 7."
    assert data["session_id"] == "test-session"


def test_chat_returns_422_when_message_is_missing() -> None:
    client = TestClient(app)
    response = client.post("/api/agent/chat", json={})
    assert response.status_code == 422
```

**Step 2: Run to confirm failure**

```bash
uv run pytest tests/api/routes/test_agent_route.py -v
```

Expected: 404 or import error — route does not exist yet.

**Step 3: Create schemas**

Create `backend/app/schemas/agent.py`:

```python
from uuid import uuid4

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    session_id: str = Field(default_factory=lambda: str(uuid4()))


class ChatResponse(BaseModel):
    response: str
    session_id: str
```

**Step 4: Implement the route**

Create `backend/app/api/routes/agent.py`:

```python
from fastapi import APIRouter

from app.agents.agent_manager import agent_manager
from app.core.config import settings
from app.schemas.agent import ChatRequest, ChatResponse

router = APIRouter(prefix=settings.api_prefix)


@router.post("/agent/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """
    Send a message to the ReAct agent and return its response.

    The agent resolves tool calls (e.g. add_numbers) automatically before
    returning the final answer. Conversation history is preserved across
    requests that share the same session_id.
    """
    agent = agent_manager.get_agent(req.session_id)
    response = await agent.chat(req.message)
    return ChatResponse(response=response, session_id=req.session_id)
```

**Step 5: Register the route**

Modify `backend/app/api/routes/__init__.py`:

```python
from fastapi import APIRouter

from app.api.routes.agent import router as agent_router
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(agent_router, tags=["agent"])
```

**Step 6: Run all tests**

```bash
uv run pytest -v
```

Expected: all tests PASS.

**Step 7: Commit**

```bash
git add app/schemas/agent.py app/api/routes/agent.py app/api/routes/__init__.py tests/api/routes/test_agent_route.py
git commit -m "feat: add POST /api/agent/chat — basic ReAct agent integration complete"
```

---

## Final Smoke Test

```bash
cd backend
uv run uvicorn app.main:app --reload
```

```bash
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 42 plus 58?"}'
```

Expected:

```json
{
  "response": "42 plus 58 equals 100.",
  "session_id": "<auto-generated-uuid>"
}
```

Follow-up with the same `session_id` to verify conversation memory:

```bash
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What was the first number?", "session_id": "<uuid-from-above>"}'
```

Expected: agent recalls `42` from the MemorySaver checkpoint.

---

## Summary

| Task | Files | Tests |
|------|-------|-------|
| 1 | `pyproject.toml` | — |
| 2 | `agents/state/agent_state.py` | 2 (smart_message_reducer branches) |
| 3 | `agents/tools/math_tool.py` | — |
| 4 | `agents/workflows/react_agent.py` | 3 (routing + graph creation) |
| 5 | `agents/agent.py` | 2 (response content + thread_id config) |
| 6 | `agents/agent_manager.py` | 3 (create + reuse + isolation) |
| 7 | `schemas/agent.py` + `api/routes/agent.py` | 2 (200 contract + 422 validation) |

**Total: 12 targeted tests across the 5 modules that have real logic to assert.**
