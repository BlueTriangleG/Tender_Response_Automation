# Sendatradie AI Agent — Core Architecture

> **Scope**: Core agent chat + streaming + ReAct workflow with HITL.
> Sufficient to implement a Python/FastAPI equivalent from scratch.

---

## 1. Directory Structure (Core Only)

```
agent/
├── Agent.js               # Session lifecycle — chat / stream / interrupt / resume
├── AgentManager.js        # Singleton session pool (30-min TTL, billing hooks)
│
├── config/
│   ├── modelConfig.js     # OpenAI ChatOpenAI factory
│   └── checkpointer.js    # LangGraph MemorySaver factory
│
├── state/
│   └── agentState.js      # LangGraph state schema + custom reducers
│
├── workflows/
│   ├── reactAgent.js      # Main ReAct agent workflow (primary workflow)
│   └── nodes/
│       ├── createAgentNode.js   # Reusable agent node factory
│       └── sharedUtils.js       # StreamDataTypes, StreamStatus constants
│
├── tools/
│   ├── ragTool.js         # Example: knowledge retrieval tool
│   └── exampleTool.js     # Example: simple structured tool
│
├── lib/
│   ├── interruptManager.js  # Global session/user interrupt state (singleton)
│   └── userContext.js       # User background string builder
│
└── handlers/
    └── AgentHandler.js    # Express HTTP handlers (chat, stream, interrupt, resume)
```

---

## 2. State Schema (`agentState.js`)

The LangGraph state is a typed object. Every field declares an explicit reducer.

```python
# Python equivalent

from typing import Annotated, Any, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage

# ── Custom reducers ─────────────────────────────────────────────────────────

def smart_message_reducer(old: list, new: list) -> list:
    """
    Default: concatenate (standard LangGraph behaviour).
    Replace mode: if new[0] carries _replace=True, discard old list entirely.
    Used after token summarisation to swap history without losing the marker API.
    """
    if new and getattr(new[0], '_replace', False):
        return [m for m in new if not getattr(m, '_replace', False)]
    return old + new

def merge_reducer(old: dict, new: dict) -> dict:
    return {**(old or {}), **(new or {})}

def replace_reducer(old, new):
    return new

def keep_if_set(old, new):
    """Preserve existing value when new value is None (persists across resume)."""
    return new if new is not None else old

# ── State definition ─────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages:         Annotated[list[BaseMessage], smart_message_reducer]
    workflowMetadata: Annotated[dict,              merge_reducer]
    finalResponse:    Annotated[Optional[str],     replace_reducer]
    completed:        Annotated[bool,              replace_reducer]
    lastMessage:      Annotated[Optional[Any],     replace_reducer]
    companyConfig:    Annotated[dict,              merge_reducer]
    context:          Annotated[dict,              merge_reducer]
    error:            Annotated[Optional[str],     replace_reducer]
    isWidgetMode:     Annotated[bool,              keep_if_set]
    pageContext:      Annotated[Optional[dict],    keep_if_set]
```

---

## 3. Agent Class (`Agent.js`)

One instance per conversation session.

```python
import importlib
from uuid import uuid4
from langchain_core.messages import HumanMessage
from .lib.interrupt_manager import interrupt_manager

class Agent:
    def __init__(self, session_id: str, config: dict):
        if not session_id:
            raise ValueError("session_id is required")

        self.session_id  = session_id
        self.user        = config.get('user')       # JWT-decoded user object
        self.is_interrupted = False
        self.usage_stats = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}

        workflow_name   = config.get('workflow_name', 'conversational')
        workflow_config = config.get('workflow_config', {})

        # Dynamic workflow loading — add a new workflow by dropping a file in workflows/
        module = importlib.import_module(f'workflows.{workflow_name}')
        self.workflow = module.create(workflow_config)   # compiled CompiledStateGraph

    # ── LangGraph config builder ─────────────────────────────────────────────

    def _lg_config(self, workflow_config: dict = {}) -> dict:
        return {
            'configurable': {
                'thread_id':      self.session_id,
                'user':           self.user,
                'workflow_config': workflow_config
            }
        }

    # ── Non-streaming invoke ─────────────────────────────────────────────────

    async def chat(self, message: str, workflow_config: dict = {}) -> str:
        """Invoke the workflow and return the final message content."""
        self._reset_interrupt()
        inputs = {'messages': [HumanMessage(content=message)]}
        response = await self.workflow.ainvoke(inputs, self._lg_config(workflow_config))
        return response['messages'][-1].content

    # ── Streaming invoke ─────────────────────────────────────────────────────

    async def stream(self, message, workflow_config: dict = {}, stream_modes=None):
        """
        Return an async generator yielding (mode, chunk) tuples.

        stream_modes=['custom', 'messages']:
          'custom'   → structured StreamDataType events emitted by writer()
          'messages' → raw LLM token chunks (for frontend character streaming)
        """
        self._reset_interrupt()
        inputs = {'messages': [HumanMessage(content=message)]}
        config = self._lg_config(workflow_config)
        if stream_modes:
            config['stream_mode'] = stream_modes
        return self.workflow.astream(inputs, config)

    # ── HITL controls ────────────────────────────────────────────────────────

    async def interrupt(self):
        """Signal that this session should stop at the next checkpoint."""
        self.is_interrupted = True
        interrupt_manager.set_session_interrupt(self.session_id, True)
        if self.user and self.user.get('id'):
            interrupt_manager.set_user_interrupt(self.user['id'], True)

    async def resume(self, interrupt_id: str, resume_data: dict) -> bool:
        """
        Validate a pending interrupt exists, then clear interrupt flags.
        The caller streams Command(resume=resume_data) to actually continue.
        """
        config = {'configurable': {'thread_id': self.session_id}}
        state  = await self.workflow.aget_state(config)
        if not state or not state.next:
            return False
        self._reset_interrupt()
        return True

    # ── Session utilities ────────────────────────────────────────────────────

    async def get_session_history(self) -> list:
        state = await self.workflow.aget_state(self._lg_config())
        return state.values.get('messages', [])

    async def clear_session_history(self) -> bool:
        empty = {
            'v': 1, 'ts': datetime.utcnow().isoformat(),
            'channel_values': {'messages': []},
            'channel_versions': {}, 'versions_seen': {}, 'pending_sends': []
        }
        await self.workflow.checkpointer.aput(self._lg_config(), empty, {})
        return True

    def _reset_interrupt(self):
        self.is_interrupted = False
        interrupt_manager.clear_session_interrupt(self.session_id)
        if self.user and self.user.get('id'):
            interrupt_manager.clear_user_interrupt(self.user['id'])
```

---

## 4. Agent Manager (`AgentManager.js`)

Module-level singleton. Manages instance lifecycle across all HTTP requests.

```python
import time
from .agent import Agent

class AgentManager:
    """
    One instance shared across the entire process.
    Maps session_id → { agent, metadata }.
    Inactive sessions cleaned up after max_inactive_ms (default 30 min).
    """

    def __init__(self):
        self.agents: dict[str, dict] = {}
        self.max_inactive_ms = 30 * 60 * 1000

    def get_agent(self, session_id: str, config: dict, user: dict) -> Agent:
        """Return existing agent or create a new one."""
        if session_id in self.agents:
            self.agents[session_id]['last_accessed'] = time.time()
            return self.agents[session_id]['agent']

        agent = Agent(session_id, {**config, 'user': user})
        self.agents[session_id] = {
            'agent':         agent,
            'created':       time.time(),
            'last_accessed': time.time(),
            'user':          user,
            'config':        config,
        }
        return agent

    async def interrupt(self, session_id: str) -> bool:
        data = self.agents.get(session_id)
        if data:
            await data['agent'].interrupt()
            return True
        return False

    async def resume(self, interrupt_id: str, resume_data: dict) -> dict:
        """Search all sessions for a matching pending interrupt."""
        for session_id, data in self.agents.items():
            if await data['agent'].resume(interrupt_id, resume_data):
                return {'success': True, 'session_id': session_id}
        return {'success': False}

    def remove_agent(self, session_id: str):
        self.agents.pop(session_id, None)

# Singleton
agent_manager = AgentManager()
```

---

## 5. ReAct Agent Workflow (`reactAgent.js`)

### 5.1 Graph Topology

```
START
  │
  ▼
[agent_node]  ─── has tool_calls AND any tool is HIGH RISK? ──► [human_review_node]
  │                                                                      │ (resume)
  │ ◄─────────────────────────────────────────────────────────────────── │
  │                                                                      ▼
  ├── has tool_calls AND all tools are LOW RISK? ──────────────► [tool_node]
  │                                                                      │
  │ ◄─────────────────────────────────────────────────────────────────── │
  │
  └── no tool_calls (final answer) ──────────────────────────── ► END
```

### 5.2 Tool Risk Classification

```python
HIGH_RISK_TOOLS = {'create_job', 'update_job', 'create_form', 'update_form'}

LOW_RISK_TOOLS = {
    'knowledge_retrieval', 'knowledge_status', 'company_info',
    'get_job', 'search_jobs', 'get_clients', 'get_workers',
    'crm_data_analysis',
    # ... all read-only tools
}

DEFAULT_POLICY = 'require_review'   # unknown tools require approval

def needs_human_approval(tool_name: str) -> bool:
    if tool_name in HIGH_RISK_TOOLS:  return True
    if tool_name in LOW_RISK_TOOLS:   return False
    return DEFAULT_POLICY == 'require_review'
```

### 5.3 Agent Node

```python
async def agent_node(state: AgentState, config: dict):
    """
    Core reasoning node.
    1. Injects user context into system prompt.
    2. Calls LLM with bound tools.
    3. If LLM returns tool_calls → return AIMessage for routing.
    4. If LLM returns final text → stream tokens and return AIMessage.
    """
    user        = config['configurable']['user']
    messages    = state['messages']
    system_msg  = SystemMessage(content=f"{SYSTEM_PROMPT}\n\n{create_user_background(user)}")
    model_bound = model.bind_tools(active_tools)

    # ── LLM call with retry ──────────────────────────────────────────────────
    for attempt in range(1, 4):
        try:
            response = await model_bound.ainvoke([system_msg, *messages])
            break
        except Exception as e:
            if is_retryable(e) and attempt < 3:
                await asyncio.sleep(2 ** attempt)
            else:
                raise

    if response.tool_calls:
        # Emit THINKING event — frontend shows "working on it…"
        config['writer']({'type': 'thinking', 'content': 'Using tools...', 'status': 'running'})
        return {'messages': [response]}

    # Final response — stream tokens to frontend
    full_text = ''
    async for chunk in model.astream([system_msg, *messages]):
        if chunk.content:
            full_text += chunk.content
            config['writer']({
                'type': 'response', 'content': chunk.content,
                'status': 'running', 'metadata': {'streaming': True}
            })
    return {'messages': [AIMessage(content=full_text)]}
```

### 5.4 Human Review Node (HITL)

```python
async def human_review_node(state: AgentState, config: dict):
    """
    Pauses execution before high-risk tool calls.
    Sends HUMAN_REVIEW SSE event to frontend (confirm card shown).
    Resumes via /agent/resume with { action: 'approve' | 'reject', ... }.
    """
    last_msg   = state['messages'][-1]
    review_id  = str(uuid4())

    review_payload = {
        'review_id': review_id,
        'session_id': config['configurable']['thread_id'],
        'tool_calls': [
            {'tool_id': tc['id'], 'tool_name': tc['name'], 'tool_args': tc['args']}
            for tc in last_msg.tool_calls
            if needs_human_approval(tc['name'])
        ]
    }

    # Notify frontend
    config['writer']({
        'type': 'human_review', 'content': 'Approval required',
        'status': 'waiting', 'metadata': review_payload
    })

    # ── PAUSE ── frontend calls POST /agent/resume to continue
    human_decision = interrupt(review_payload)

    if human_decision.get('action') == 'reject':
        return {'messages': [AIMessage(content='Action cancelled by user.')]}

    # Approved — optionally with modified args
    if human_decision.get('approved_tools'):
        updated_calls = rebuild_tool_calls(last_msg.tool_calls, human_decision['approved_tools'])
        return {'messages': [AIMessage(content=last_msg.content, tool_calls=updated_calls)]}

    return {}   # proceed with original tool calls
```

### 5.5 Tool Node

```python
async def tool_node(state: AgentState, config: dict):
    """
    Execute all tool calls from the last AIMessage.
    Each tool receives user context via config['configurable'].
    Failures are caught per-tool and returned as error ToolMessages.
    """
    last_msg = state['messages'][-1]
    results  = []

    for tc in last_msg.tool_calls:
        tool = tools_by_name.get(tc['name'])
        try:
            result = await tool.ainvoke(tc['args'], config={
                'configurable': {
                    'user':      config['configurable']['user'],
                    'thread_id': config['configurable']['thread_id']
                }
            })
        except Exception as e:
            result = f"Tool error: {e}"

        config['writer']({
            'type': 'tool', 'content': tc['name'],
            'status': 'complete', 'metadata': {'tool_name': tc['name']}
        })
        results.append(ToolMessage(content=str(result), tool_call_id=tc['id']))

    return {'messages': results}
```

### 5.6 Routing Functions

```python
def route_after_agent(state: AgentState) -> str:
    last = state['messages'][-1]
    if not getattr(last, 'tool_calls', None):
        return END                          # final answer
    if any(needs_human_approval(tc['name']) for tc in last.tool_calls):
        return 'human_review'
    return 'tools'

def route_after_tools(state: AgentState) -> str:
    return 'agent'                          # always loop back
```

### 5.7 Graph Assembly

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

def create(workflow_config: dict = {}) -> CompiledStateGraph:
    model       = ChatOpenAI(model='gpt-4o-mini')
    checkpointer = MemorySaver()            # swap for PostgresSaver in production

    graph = StateGraph(AgentState)
    graph.add_node('agent',        agent_node)
    graph.add_node('human_review', human_review_node)
    graph.add_node('tools',        tool_node)

    graph.set_entry_point('agent')
    graph.add_conditional_edges('agent', route_after_agent, {
        'human_review': 'human_review',
        'tools':        'tools',
        END:            END
    })
    graph.add_edge('human_review', 'tools')
    graph.add_edge('tools',        'agent')

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=['human_review']   # required for HITL to work
    )
```

---

## 6. Streaming Events Protocol

All streaming uses **Server-Sent Events (SSE)**. The LangGraph `writer` callable
emits structured JSON objects down the SSE channel.

### Event Shape

```json
{
  "type": "thinking | tool | response | human_review | error | progress",
  "content": "Human-readable description",
  "status": "waiting | running | complete | error | paused",
  "metadata": { "streaming": true, "tool_name": "create_job", "node": "agent" }
}
```

### Event Types Reference

| `type`           | When emitted                                  | Frontend action              |
| ---------------- | --------------------------------------------- | ---------------------------- |
| `thinking`       | Agent is reasoning / calling a tool           | Show spinner / status text   |
| `tool`           | Tool execution started or finished            | Show tool activity indicator |
| `response`       | Final answer token stream (`status: running`) | Append to chat bubble        |
| `response`       | Final answer complete (`status: complete`)    | Stop cursor                  |
| `human_review`   | High-risk tool paused awaiting approval       | Show confirm card            |
| `human_decision` | Decision result after approve/reject          | Update card state            |
| `error`          | Unrecoverable failure                         | Show error message           |

### FastAPI SSE Endpoint

```python
from fastapi import FastAPI, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.types import Command
import json

app = FastAPI()

@app.post('/agent/stream')
async def stream_chat(req: StreamRequest, user=Depends(get_current_user)):
    session_id = req.session_id or str(uuid4())
    agent = agent_manager.get_agent(session_id, req.workflow_config or {}, user)

    async def generate():
        # 1. Announce session_id so client can attach to this session
        yield f"data: {json.dumps({'event': 'session_id', 'sessionId': session_id})}\n\n"

        stream = await agent.stream(
            req.message,
            req.workflow_config or {},
            stream_modes=['custom', 'messages']
        )

        async for mode, chunk in stream:
            if mode == 'custom':
                # Structured events emitted by writer() inside nodes
                yield f"data: {json.dumps(chunk)}\n\n"
            elif mode == 'messages' and getattr(chunk, 'content', None):
                # Raw LLM token stream
                yield f"data: {json.dumps({'type': 'response', 'content': chunk.content, 'status': 'running'})}\n\n"

        yield f"data: {json.dumps({'event': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
    })

@app.post('/agent/chat')
async def chat(req: ChatRequest, user=Depends(get_current_user)):
    """Non-streaming fallback."""
    session_id = req.session_id or str(uuid4())
    agent    = agent_manager.get_agent(session_id, req.workflow_config or {}, user)
    response = await agent.chat(req.message, req.workflow_config or {})
    return {'response': response, 'session_id': session_id}

@app.post('/agent/interrupt/{session_id}')
async def interrupt_agent(session_id: str, user=Depends(get_current_user)):
    success = await agent_manager.interrupt(session_id)
    return {'success': success}

@app.post('/agent/resume')
async def resume_agent(req: ResumeRequest, user=Depends(get_current_user)):
    """
    Called by frontend after user approves or rejects a HUMAN_REVIEW event.
    req.interrupt_id  — from the human_review event metadata
    req.action        — 'approve' | 'reject'
    req.approved_tools — optional list of {tool_id, tool_args} with modified args
    """
    result = await agent_manager.resume(req.interrupt_id, req.dict())
    if not result['success']:
        raise HTTPException(404, 'No pending interrupt found')

    # Stream the resumed execution
    session_id = result['session_id']
    agent = agent_manager.get_agent(session_id, {}, user)

    async def generate():
        stream = await agent.workflow.astream(
            Command(resume=req.dict()),
            {'configurable': {'thread_id': session_id}, 'stream_mode': ['custom', 'messages']}
        )
        async for mode, chunk in stream:
            if mode == 'custom':
                yield f"data: {json.dumps(chunk)}\n\n"
            elif mode == 'messages' and getattr(chunk, 'content', None):
                yield f"data: {json.dumps({'type': 'response', 'content': chunk.content, 'status': 'running'})}\n\n"
        yield f"data: {json.dumps({'event': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type='text/event-stream')
```

---

## 7. Interrupt Manager (`interruptManager.js`)

```python
import threading, time

class InterruptManager:
    """
    Singleton that tracks interrupt flags per session and per user.
    Production note: replace dict with Redis for multi-process deployments.
    """

    def __init__(self):
        self._lock            = threading.Lock()
        self.interrupts: dict = {}        # session_id → {interrupted, timestamp}
        self.user_interrupts: dict = {}   # user_id    → {interrupted, timestamp}

    def set_session_interrupt(self, session_id: str, interrupted: bool = True):
        with self._lock:
            self.interrupts[session_id] = {'interrupted': interrupted, 'timestamp': time.time()}

    def set_user_interrupt(self, user_id, interrupted: bool = True):
        with self._lock:
            self.user_interrupts[str(user_id)] = {'interrupted': interrupted, 'timestamp': time.time()}

    def is_interrupted(self, session_id: str, user_id=None) -> bool:
        session_flag = (self.interrupts.get(session_id) or {}).get('interrupted', False)
        user_flag    = (self.user_interrupts.get(str(user_id)) or {}).get('interrupted', False) if user_id else False
        return session_flag or user_flag

    def clear_session_interrupt(self, session_id: str):
        with self._lock:
            self.interrupts.pop(session_id, None)

    def clear_user_interrupt(self, user_id):
        with self._lock:
            self.user_interrupts.pop(str(user_id), None)

# Module-level singleton
interrupt_manager = InterruptManager()
```

---

## 8. User Context Builder (`userContext.js`)

```python
from datetime import datetime
import pytz

ROLES = {1: 'Administrator', 2: 'Manager', 3: 'Worker', 4: 'Client', 5: 'Viewer'}
PACKS = {1: 'Basic (30 jobs/mo)', 2: 'Professional (150 jobs/mo)', 3: 'Enterprise', 4: 'Premium'}

def create_user_background(user: dict) -> str:
    """
    Returns a system-prompt block injected into every agent call.
    Contains: identity, role, permissions, current time, data isolation rules.
    """
    if not user:
        return "No user information available."

    tz  = user.get('time_zone', 'UTC')
    now = datetime.now(pytz.timezone(tz))

    return f"""## USER CONTEXT

Current Time : {now.strftime('%A %B %d %Y %I:%M %p %Z')}
User         : {user.get('full_name') or user.get('name', 'Unknown')}
Company      : {user.get('company_name', f"Company {user.get('company')}")}
Role         : {ROLES.get(user.get('role'), 'Unknown')}
Subscription : {PACKS.get(user.get('pack_id'), 'Unknown')}

## SECURITY
- ONLY access data where company_id = {user.get('company')} OR user_id = {user.get('id')}
- NEVER expose internal IDs (company_id, user_id) in user-facing responses"""
```

---

## 9. Example Tools

Two patterns cover every tool in the system.

### Pattern A — Simple tool (no user context needed)

```python
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

class CompanyInfoInput(BaseModel):
    query: str

async def get_company_info(query: str) -> str:
    # Static or lightly dynamic lookup
    return f"Company info for query: {query}"

company_info_tool = StructuredTool.from_function(
    coroutine  = get_company_info,
    name       = 'company_info',
    description= 'Get general company information.',
    args_schema= CompanyInfoInput
)
```

### Pattern B — Tool that needs authenticated user context

```python
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

class SearchJobsInput(BaseModel):
    query: str
    limit: int = 10

async def search_jobs_func(query: str, limit: int = 10, config: dict = {}) -> dict:
    """
    Tools receive the LangGraph config as a kwarg.
    Extract user from config['configurable']['user'].
    company_id is taken from user — never from the tool input (security).
    """
    user       = config.get('configurable', {}).get('user', {})
    company_id = user.get('company')

    if not company_id:
        return {'error': 'Authentication required'}

    # Query DB scoped to company_id
    results = await db.query(
        'SELECT * FROM jobs WHERE company_id = ? AND name LIKE ? LIMIT ?',
        [company_id, f'%{query}%', limit]
    )
    return {'jobs': results, 'total': len(results)}

search_jobs_tool = StructuredTool.from_function(
    coroutine  = search_jobs_func,
    name       = 'search_jobs',
    description= 'Search jobs by keyword. Only returns jobs for the authenticated company.',
    args_schema= SearchJobsInput
)
```

---

## 10. Session Persistence

```
Layer 1 — LangGraph MemorySaver (in-process)
  Key   : thread_id = session_id
  Stores: full AgentState (messages, interrupt state, metadata)
  Scope : process lifetime only — lost on restart
  Used for: agent reasoning continuity, HITL interrupt/resume

Layer 2 — Database (optional, for UI history)
  Tables: agent_threads (id, user_id, title, workflow)
          agent_messages (id, thread_id, role, content JSON, created_at)
  Scope : permanent
  Used for: displaying past conversations in frontend

Production upgrade path:
  Replace MemorySaver with PostgresSaver to unify both layers.
  Single store, survives restarts, works across multiple processes.
```

---

## 11. Python Project Layout

```
project/
├── main.py                    # FastAPI app + lifespan
├── requirements.txt
├── .env
│
├── agent/
│   ├── agent.py
│   └── agent_manager.py
│
├── state/
│   └── agent_state.py
│
├── workflows/
│   ├── react_agent.py
│   └── nodes/
│       ├── agent_node.py
│       └── shared_utils.py
│
├── tools/
│   ├── example_tool.py
│   └── search_jobs_tool.py
│
├── lib/
│   ├── interrupt_manager.py
│   └── user_context.py
│
└── handlers/
    └── agent_handler.py
```

---

## 12. Key Environment Variables

```bash
OPENAI_API_KEY=sk-...      # Required — LLM calls
DATABASE_URL=...           # Optional — agent_threads persistence
LANGSMITH_API_KEY=...      # Optional — recommended for production tracing
```

---

## 13. Critical Design Rules (do not skip)

1. **Dynamic workflow loading**: `Agent.__init__` imports the workflow module by name.
   Adding a new workflow = dropping a new file in `workflows/`. No registry needed.

2. **`interrupt_before=['human_review']`** must be in `graph.compile()`.
   Without it, the graph will not pause at the human review node.

3. **`Command(resume=data)`** is how you send the human decision back into the graph.
   Pass it as the _input_ to `workflow.astream()`, not as config.

4. **`stream_mode=['custom', 'messages']`** enables both channels simultaneously.
   `'custom'` = structured events from `writer()`; `'messages'` = raw LLM tokens.

5. **session_id = thread_id**. Keep them the same value throughout.
   The checkpointer uses `thread_id` to store/restore state.

6. **User context injected at node level, not at HTTP level**.
   The `user` object lives in `config['configurable']['user']` and is read by
   each node that needs it. This keeps `Agent` and `AgentManager` user-agnostic.
