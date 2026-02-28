from app.agents.agent_manager import AgentManager, agent_manager
from app.features.history_ingest.application.ingest_history_use_case import (
    IngestHistoryUseCase,
)


def get_agent_manager() -> AgentManager:
    return agent_manager


def get_history_ingest_use_case() -> IngestHistoryUseCase:
    return IngestHistoryUseCase()
