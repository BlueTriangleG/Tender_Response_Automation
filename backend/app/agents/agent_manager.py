from app.agents.agent import Agent

# Composite key type: (session_id, workflow_name).
# A session that switches workflow is treated as a distinct agent instance,
# preventing silent workflow mismatches when the same session_id is reused
# across different workflow types.
_AgentKey = tuple[str, str]


class AgentManager:
    """
    Module-level singleton that maps (session_id, workflow_name) -> Agent instance.

    Agents are created on first access and reused for all subsequent requests
    with the same (session_id, workflow_name) pair, preserving conversation
    history via the LangGraph MemorySaver checkpointer.

    Production note: replace the in-process dict with a distributed store
    (e.g. Redis) for multi-process deployments.
    """

    def __init__(self) -> None:
        self.agents: dict[_AgentKey, Agent] = {}

    def get_agent(self, session_id: str, workflow_name: str = "react_agent") -> Agent:
        """
        Return the existing Agent for this (session_id, workflow_name) pair,
        or create a new one.

        Using a composite key prevents a session that previously used one
        workflow from silently receiving a cached instance of a different
        workflow on a subsequent call.
        """
        key: _AgentKey = (session_id, workflow_name)
        if key not in self.agents:
            self.agents[key] = Agent(session_id=session_id, workflow_name=workflow_name)
        return self.agents[key]

    def remove_agent(self, session_id: str, workflow_name: str = "react_agent") -> None:
        """Remove an agent from the pool. No-op if the key does not exist."""
        self.agents.pop((session_id, workflow_name), None)


agent_manager = AgentManager()
