"""Unit tests for the LLM client adapter and factory."""
import pytest
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

from webapp.factory import _LLMClientAdapter
from qport_agent.llm.client import AgentMessage, ToolCall as QportToolCall


# ── Mock fast-framework types ────────────────────────────────────


@dataclass
class MockToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class MockLLMResponse:
    content: str
    tool_calls: list[MockToolCall]
    stop_reason: str
    raw_response: Any = None


class MockEnhancedClient:
    """Simulates EnhancedLLMClient from fast-framework."""

    def __init__(self, response: MockLLMResponse):
        self._response = response
        self.last_call = None

    def complete_with_tools(self, messages, tools, system_prompt=None, tool_choice="auto"):
        self.last_call = {
            "messages": messages,
            "tools": tools,
            "system_prompt": system_prompt,
            "tool_choice": tool_choice,
        }
        return self._response


# ── Adapter Tests ────────────────────────────────────────────────


class TestLLMClientAdapter:
    def test_send_returns_agent_message(self):
        """Adapter.send() returns an AgentMessage with correct fields."""
        response = MockLLMResponse(
            content="Here is my analysis.",
            tool_calls=[],
            stop_reason="end_turn",
        )
        adapter = _LLMClientAdapter(MockEnhancedClient(response))

        result = adapter.send(
            messages=[{"role": "user", "content": "Hello"}],
            system="You are helpful.",
            tools=[],
        )

        assert isinstance(result, AgentMessage)
        assert result.text == "Here is my analysis."
        assert result.tool_calls == []
        assert result.stop_reason == "end_turn"
        assert result.usage == {}

    def test_send_converts_tool_calls(self):
        """Adapter converts fast-framework ToolCalls to qport-agent ToolCalls."""
        response = MockLLMResponse(
            content="Let me check that.",
            tool_calls=[
                MockToolCall(
                    id="tc_001",
                    name="compute_portfolio_metrics",
                    input={"portfolio_id": "abc123"},
                ),
                MockToolCall(
                    id="tc_002",
                    name="get_benchmark_data",
                    input={"benchmark": "SP500"},
                ),
            ],
            stop_reason="tool_use",
        )
        adapter = _LLMClientAdapter(MockEnhancedClient(response))

        result = adapter.send(
            messages=[{"role": "user", "content": "Analyze"}],
            system="System prompt",
            tools=[{"name": "compute_portfolio_metrics"}],
        )

        assert len(result.tool_calls) == 2
        assert isinstance(result.tool_calls[0], QportToolCall)
        assert result.tool_calls[0].id == "tc_001"
        assert result.tool_calls[0].name == "compute_portfolio_metrics"
        assert result.tool_calls[0].input == {"portfolio_id": "abc123"}
        assert result.tool_calls[1].id == "tc_002"
        assert result.stop_reason == "tool_use"

    def test_send_passes_system_as_string(self):
        """Adapter passes system prompt string to complete_with_tools."""
        response = MockLLMResponse(content="Ok", tool_calls=[], stop_reason="end_turn")
        client = MockEnhancedClient(response)
        adapter = _LLMClientAdapter(client)

        adapter.send(
            messages=[{"role": "user", "content": "Hi"}],
            system="You are a portfolio builder.",
            tools=[{"name": "some_tool"}],
        )

        assert client.last_call["system_prompt"] == "You are a portfolio builder."
        assert client.last_call["messages"] == [{"role": "user", "content": "Hi"}]
        assert client.last_call["tools"] == [{"name": "some_tool"}]

    def test_send_handles_list_system_prompt(self):
        """When system is a list (Anthropic cache format), passes None."""
        response = MockLLMResponse(content="Ok", tool_calls=[], stop_reason="end_turn")
        client = MockEnhancedClient(response)
        adapter = _LLMClientAdapter(client)

        adapter.send(
            messages=[{"role": "user", "content": "Hi"}],
            system=[{"type": "text", "text": "System", "cache_control": {"type": "ephemeral"}}],
            tools=[],
        )

        # List-type system prompts can't be passed as system_prompt string
        assert client.last_call["system_prompt"] is None

    def test_send_empty_content(self):
        """Adapter handles empty content gracefully."""
        response = MockLLMResponse(content="", tool_calls=[], stop_reason="end_turn")
        adapter = _LLMClientAdapter(MockEnhancedClient(response))

        result = adapter.send(messages=[], system="", tools=[])

        assert result.text == ""
        assert result.tool_calls == []

    def test_has_tool_calls_property(self):
        """AgentMessage.has_tool_calls property works via adapter."""
        response = MockLLMResponse(
            content="Using tool",
            tool_calls=[MockToolCall(id="1", name="t", input={})],
            stop_reason="tool_use",
        )
        adapter = _LLMClientAdapter(MockEnhancedClient(response))

        result = adapter.send(messages=[], system="", tools=[])
        assert result.has_tool_calls is True

        # No tool calls
        response2 = MockLLMResponse(content="Done", tool_calls=[], stop_reason="end_turn")
        adapter2 = _LLMClientAdapter(MockEnhancedClient(response2))
        result2 = adapter2.send(messages=[], system="", tools=[])
        assert result2.has_tool_calls is False
