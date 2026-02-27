"""Unit tests for PlanningSubAgent — state machine, chip parsing, error handling."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass

from webapp.sub_agent import PlanningSubAgent


# ── Fixtures ──────────────────────────────────────────────────────


class MockOrchestrator:
    """Mock QportOrchestrator that simulates planning behavior."""

    def __init__(self):
        self._planning_messages = None
        self._planning_prompt = None
        self._planning_usage = {}
        self._planning_pending = False
        self._planning_text = ""
        self._planning_mandate = None
        self._plan_result = None
        self._continue_result = None
        self._revise_result = None
        self._plan_exception = None
        self._continue_exception = None
        self._revise_exception = None

    def plan(self, user_request, interactive=False):
        if self._plan_exception:
            raise self._plan_exception
        return self._plan_result

    def continue_plan(self, user_response, max_turns=10):
        if self._continue_exception:
            raise self._continue_exception
        return self._continue_result

    def revise_plan(self, override_text, max_retries=3):
        if self._revise_exception:
            raise self._revise_exception
        return self._revise_result


SAMPLE_MANDATE = {
    "version": "1.0",
    "fund": "SP500 Multifactor",
    "sleeves": [{"name": "Main", "allocation": 1.0, "template": "multifactor"}],
}

SAMPLE_RESULT = {
    "mandate": SAMPLE_MANDATE,
    "text": "SP500 Multifactor portfolio with value and momentum.",
    "compact": None,
    "usage": {"input_tokens": 100, "output_tokens": 50},
}


def _make_agent(mock_orch=None):
    """Create a PlanningSubAgent with a mocked orchestrator."""
    agent = PlanningSubAgent.__new__(PlanningSubAgent)
    agent.orchestrator = mock_orch or MockOrchestrator()
    agent._progress = None
    agent._state = "idle"
    agent._last_mandate = None
    agent._last_llm_responses = []
    return agent


# ── State Transitions ─────────────────────────────────────────────


class TestStateTransitions:
    def test_idle_to_interviewing_on_needs_input(self):
        """First chat triggers plan(); PlanningNeedsInput → interviewing."""
        from qport_agent.orchestrator import PlanningNeedsInput

        orch = MockOrchestrator()
        orch._plan_exception = PlanningNeedsInput("What benchmark would you like?")
        agent = _make_agent(orch)

        response = agent.chat("Build me a portfolio")
        assert agent._state == "interviewing"
        assert response.status == "partial"
        assert "benchmark" in response.reasoning.lower()

    def test_idle_to_finalized_on_immediate_mandate(self):
        """Simple request returns mandate immediately → finalized."""
        orch = MockOrchestrator()
        orch._plan_result = SAMPLE_RESULT
        agent = _make_agent(orch)

        response = agent.chat("S&P 500 value tilt, weight limit 5%")
        assert agent._state == "finalized"
        assert response.status == "success"
        assert response.data["mandate"]["fund"] == "SP500 Multifactor"

    def test_interviewing_to_finalized(self):
        """continue_plan returns mandate → finalized."""
        orch = MockOrchestrator()
        orch._continue_result = SAMPLE_RESULT
        agent = _make_agent(orch)
        agent._state = "interviewing"

        response = agent.chat("Yes, equal blending")
        assert agent._state == "finalized"
        assert response.status == "success"
        assert len(response.action_chips) == 3  # Download, Revise, Start Over

    def test_interviewing_stays_on_more_questions(self):
        """continue_plan raises PlanningNeedsInput → stays interviewing."""
        from qport_agent.orchestrator import PlanningNeedsInput

        orch = MockOrchestrator()
        orch._continue_exception = PlanningNeedsInput("What constraints?")
        agent = _make_agent(orch)
        agent._state = "interviewing"

        response = agent.chat("Use value and momentum")
        assert agent._state == "interviewing"
        assert response.status == "partial"

    def test_finalized_revision_stays_finalized(self):
        """Revision in finalized state stays finalized."""
        orch = MockOrchestrator()
        orch._revise_result = SAMPLE_RESULT
        agent = _make_agent(orch)
        agent._state = "finalized"

        response = agent.chat("Change weight limit to 3%")
        assert agent._state == "finalized"
        assert response.status == "success"

    def test_start_over_resets_to_idle(self):
        """'Start over' in finalized state resets to idle."""
        agent = _make_agent()
        agent._state = "finalized"
        agent._last_mandate = SAMPLE_MANDATE

        response = agent.chat("start over")
        assert agent._state == "idle"
        assert response.status == "partial"
        assert agent._last_mandate is None


# ── Action Chips ─────────────────────────────────────────────────


class TestActionChips:
    def test_interview_chips_on_needs_input(self):
        """PlanningNeedsInput returns deterministic interview chips."""
        from qport_agent.orchestrator import PlanningNeedsInput

        orch = MockOrchestrator()
        orch._plan_exception = PlanningNeedsInput("What benchmark?")
        agent = _make_agent(orch)

        response = agent.chat("Build a portfolio")
        assert len(response.action_chips) == 2
        assert response.action_chips[0].label == "Looks good"
        assert response.action_chips[1].label == "Show details"

    def test_finalized_chips_on_success(self):
        """Finalized mandate returns Download/Revise/Start Over chips."""
        orch = MockOrchestrator()
        orch._plan_result = SAMPLE_RESULT
        agent = _make_agent(orch)

        response = agent.chat("S&P 500 value tilt")
        assert len(response.action_chips) == 3
        labels = [c.label for c in response.action_chips]
        assert "Download Mandate" in labels
        assert "Revise" in labels
        assert "Start Over" in labels

    def test_interview_chips_are_actionable_messages(self):
        """Interview chip intent_hints are human-readable messages for the chat."""
        from qport_agent.orchestrator import PlanningNeedsInput

        orch = MockOrchestrator()
        orch._plan_exception = PlanningNeedsInput("Section question")
        agent = _make_agent(orch)

        response = agent.chat("Build a portfolio")
        # intent_hint is used as the message sent when chip is clicked
        assert "looks good" in response.action_chips[0].intent_hint.lower()
        assert "details" in response.action_chips[1].intent_hint.lower()


# ── Error Handling ────────────────────────────────────────────────


class TestErrorHandling:
    def test_runtime_error(self):
        """RuntimeError (e.g., revise without plan) → error response."""
        orch = MockOrchestrator()
        orch._revise_exception = RuntimeError("No planning conversation")
        agent = _make_agent(orch)
        agent._state = "finalized"

        response = agent.chat("Change the benchmark")
        assert response.status == "error"
        assert "starting over" in response.reasoning.lower()
        assert len(response.action_chips) == 1
        assert response.action_chips[0].intent_hint == "start_over"

    def test_value_error(self):
        """ValueError (mandate parse failure) → error response."""
        orch = MockOrchestrator()
        orch._continue_exception = ValueError("Could not parse mandate")
        agent = _make_agent(orch)
        agent._state = "interviewing"

        response = agent.chat("Use all defaults")
        assert response.status == "error"
        assert "rephrase" in response.reasoning.lower()


# ── Reset ─────────────────────────────────────────────────────────


class TestReset:
    def test_reset_clears_state(self):
        agent = _make_agent()
        agent._state = "finalized"
        agent._last_mandate = SAMPLE_MANDATE
        agent._last_llm_responses = [{"tokens": 100}]

        agent.reset_conversation()

        assert agent._state == "idle"
        assert agent._last_mandate is None
        assert agent._last_llm_responses == []

    def test_reset_clears_orchestrator(self):
        agent = _make_agent()
        agent.orchestrator._planning_messages = [{"role": "user", "content": "test"}]
        agent.orchestrator._planning_pending = True

        agent.reset_conversation()

        assert agent.orchestrator._planning_messages is None
        assert agent.orchestrator._planning_pending is False


# ── SubAgent ABC Methods ──────────────────────────────────────────


class TestSubAgentABC:
    def test_get_tool_schemas_empty(self):
        agent = _make_agent()
        assert agent.get_tool_schemas() == []

    def test_get_capabilities(self):
        agent = _make_agent()
        caps = agent.get_capabilities()
        assert caps.agent_name == "qport-planning"
        assert caps.tool_count == 0
        assert "mandate" in caps.trigger_keywords

    def test_get_last_usage_stats(self):
        agent = _make_agent()
        stats = agent.get_last_usage_stats()
        assert "llm_responses" in stats
        assert stats["search_queries"] == 0


# ── Start Over Detection ─────────────────────────────────────────


class TestStartOverDetection:
    @pytest.mark.parametrize("phrase", [
        "start over", "Start Over", "start fresh", "reset",
        "new mandate", "begin again",
    ])
    def test_recognized_phrases(self, phrase):
        agent = _make_agent()
        assert agent._is_start_over(phrase) is True

    @pytest.mark.parametrize("phrase", [
        "Change the benchmark", "start over please",
        "I want to start a new analysis", "revise constraints",
    ])
    def test_non_start_over(self, phrase):
        agent = _make_agent()
        assert agent._is_start_over(phrase) is False
