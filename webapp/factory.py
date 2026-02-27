"""Agent factory for the qport Planning Agent standalone webapp."""
from fast_framework.contracts import SubAgent
from fast_framework.llm.enhanced_client import create_enhanced_client
from .sub_agent import PlanningSubAgent


def create_planning_agent(
    session_id: str,
    provider: str,
    progress_callback=None,
) -> SubAgent:
    """Factory that creates a PlanningSubAgent for a standalone session.

    Signature matches the AgentFactory protocol:
        (session_id, provider, progress_callback) -> SubAgent
    """
    llm_client = create_enhanced_client(provider=provider, verbose=False)
    return PlanningSubAgent(
        llm_client=llm_client,
        progress_callback=progress_callback,
    )
