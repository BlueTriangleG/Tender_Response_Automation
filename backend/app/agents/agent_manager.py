from app.agents.agent import Agent


class AgentManager:
    """
    Module-level singleton that maps session_id -> Agent instance.

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
