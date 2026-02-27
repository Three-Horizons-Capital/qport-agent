"""Agent factory for the qport Planning Agent standalone webapp."""
from fast_framework.contracts import SubAgent
from fast_framework.llm.enhanced_client import create_enhanced_client
from qport_agent.llm.client import AgentMessage, ToolCall as QportToolCall
from .sub_agent import PlanningSubAgent


class _LLMClientAdapter:
    """Adapts EnhancedLLMClient (.complete_with_tools) to the qport-agent
    LLMClient interface (.send) expected by QportOrchestrator."""

    def __init__(self, enhanced_client):
        self._client = enhanced_client

    def send(self, messages, system, tools):
        resp = self._client.complete_with_tools(
            messages=messages,
            tools=tools,
            system_prompt=system if isinstance(system, str) else None,
        )
        # Convert fast-framework ToolCall → qport-agent ToolCall
        tool_calls = [
            QportToolCall(id=tc.id, name=tc.name, input=tc.input)
            for tc in resp.tool_calls
        ]
        return AgentMessage(
            text=resp.content,
            tool_calls=tool_calls,
            stop_reason=resp.stop_reason,
            usage={},
        )


def create_planning_agent(
    session_id: str,
    provider: str,
    progress_callback=None,
) -> SubAgent:
    """Factory that creates a PlanningSubAgent for a standalone session.

    Signature matches the AgentFactory protocol:
        (session_id, provider, progress_callback) -> SubAgent
    """
    enhanced_client = create_enhanced_client(provider=provider, verbose=False)
    llm_client = _LLMClientAdapter(enhanced_client)
    return PlanningSubAgent(
        llm_client=llm_client,
        progress_callback=progress_callback,
    )
