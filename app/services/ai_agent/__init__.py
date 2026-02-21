"""AI Agent service package."""
from __future__ import annotations

from app.services.ai_agent.agent_service import PydanticAIAgentService
from app.services.ai_agent.tool_bridge import AgentDeps

__all__ = ["PydanticAIAgentService", "AgentDeps", "get_agent_service"]

_service: PydanticAIAgentService | None = None


def get_agent_service() -> PydanticAIAgentService:
    """Return a singleton agent service instance."""
    global _service
    if _service is None:
        _service = PydanticAIAgentService()
    return _service
