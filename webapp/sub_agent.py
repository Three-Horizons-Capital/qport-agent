"""PlanningSubAgent — wraps the qport Planning Agent for the FAST standalone webapp."""
import json
import logging
from typing import Optional

from fast_framework.contracts import SubAgent, AgentResponse, ActionChip, AgentCapabilities
from qport_agent.orchestrator import QportOrchestrator, PlanningNeedsInput

logger = logging.getLogger(__name__)

# Deterministic chips for each interview phase
_INTERVIEW_CHIPS = [
    ActionChip(label="Looks good", intent_hint="Looks good, move to the next section"),
    ActionChip(label="Show details", intent_hint="Show me the full parameter details"),
]

_FINALIZED_CHIPS = [
    ActionChip(label="Download Mandate", intent_hint="download_mandate"),
    ActionChip(label="Revise", intent_hint="revise_mandate"),
    ActionChip(label="Start Over", intent_hint="start_over"),
]

_START_OVER_PHRASES = {"start over", "start fresh", "reset", "new mandate", "begin again"}


class PlanningSubAgent(SubAgent):
    """SubAgent that wraps the qport Planning Agent for interactive mandate building.

    State machine:
        idle → interviewing → finalized
        Any state → idle (via reset_conversation)
        finalized → finalized (via revise_plan)
    """

    MAX_TURNS = 1  # No tool-calling loop — each chat() is one LLM round-trip

    def __init__(self, llm_client, progress_callback=None):
        self.orchestrator = QportOrchestrator(llm_client)
        self._progress = progress_callback
        self._state = "idle"  # idle | interviewing | finalized
        self._last_mandate = None
        self._last_llm_responses = []

    # ── SubAgent ABC ──────────────────────────────────────────────

    def chat(self, message: str, context: Optional[dict] = None) -> AgentResponse:
        """Route message to the correct orchestrator method based on state."""
        try:
            if self._state == "idle":
                return self._start_planning(message)
            elif self._state == "interviewing":
                return self._continue_planning(message)
            elif self._state == "finalized":
                return self._handle_revision(message)
        except PlanningNeedsInput as e:
            self._state = "interviewing"
            return AgentResponse(
                status="partial",
                data=None,
                reasoning=e.text,
                action_chips=list(_INTERVIEW_CHIPS),
            )
        except RuntimeError as e:
            logger.error(f"Planning runtime error: {e}")
            return AgentResponse(
                status="error",
                data=None,
                reasoning=f"Something went wrong: {e}\n\nPlease try starting over.",
                action_chips=[ActionChip(label="Start Over", intent_hint="start_over")],
            )
        except ValueError as e:
            logger.error(f"Planning parse error: {e}")
            return AgentResponse(
                status="error",
                data=None,
                reasoning=(
                    "I wasn't able to generate a valid mandate from that request. "
                    "Could you rephrase or provide more detail?"
                ),
                action_chips=[],
            )

    def get_tool_schemas(self) -> list[dict]:
        """Planning agent has no tools — it's a pure conversational LLM."""
        return []

    def get_system_prompt(self) -> str:
        return self.orchestrator._planning_prompt or ""

    def get_capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            agent_name="qport-planning",
            description="Interactive portfolio mandate builder — NL to structured JSON",
            handles_intents=[
                "build portfolio", "create mandate", "portfolio construction",
                "multifactor", "benchmark replication", "index replication",
            ],
            trigger_keywords=[
                "mandate", "portfolio", "multifactor", "benchmark",
                "value", "momentum", "quality", "lowvol", "carry",
                "S&P 500", "SP500", "USIG", "HYG", "credit",
            ],
            tool_count=0,
        )

    def get_last_usage_stats(self) -> dict:
        return {
            "llm_responses": self._last_llm_responses,
            "search_queries": 0,
        }

    def reset_conversation(self) -> None:
        self._state = "idle"
        self._last_mandate = None
        self._last_llm_responses = []
        # Reset orchestrator planning state
        self.orchestrator._planning_messages = None
        self.orchestrator._planning_prompt = None
        self.orchestrator._planning_usage = {}
        self.orchestrator._planning_pending = False
        self.orchestrator._planning_text = ""
        self.orchestrator._planning_mandate = None

    # ── Internal methods ──────────────────────────────────────────

    def _start_planning(self, message: str) -> AgentResponse:
        """Begin a new interactive planning session."""
        self._report_progress("on_llm_start")
        result = self.orchestrator.plan(message, interactive=True)
        self._report_progress("on_response_ready")
        # Mandate returned immediately (simple single-shot request)
        return self._finalize(result)

    def _continue_planning(self, message: str) -> AgentResponse:
        """Continue the interactive interview."""
        self._report_progress("on_llm_start")
        result = self.orchestrator.continue_plan(message)
        self._report_progress("on_response_ready")
        return self._finalize(result)

    def _handle_revision(self, message: str) -> AgentResponse:
        """Handle revision or start-over in finalized state."""
        if self._is_start_over(message):
            self.reset_conversation()
            return AgentResponse(
                status="partial",
                data=None,
                reasoning=(
                    "Starting fresh. What portfolio would you like to build?\n\n"
                    "Tell me about the benchmark, asset class, and strategy you have in mind."
                ),
                action_chips=[],
            )
        self._report_progress("on_llm_start")
        result = self.orchestrator.revise_plan(message)
        self._report_progress("on_response_ready")
        return self._finalize(result)

    def _finalize(self, result: dict) -> AgentResponse:
        """Wrap a completed mandate result into an AgentResponse."""
        self._state = "finalized"
        self._last_mandate = result["mandate"]
        self._last_llm_responses = []
        # Extract usage if available
        usage = result.get("usage", {})
        if usage:
            self._last_llm_responses = [usage]
        return AgentResponse(
            status="success",
            data={"mandate": result["mandate"]},
            reasoning=result["text"],
            action_chips=list(_FINALIZED_CHIPS),
            metadata={"mandate_version": "1.0"},
        )

    def _is_start_over(self, message: str) -> bool:
        """Check if the user wants to start a completely new mandate."""
        normalized = message.strip().lower()
        return normalized in _START_OVER_PHRASES

    def _report_progress(self, method: str, *args, **kwargs):
        if self._progress and hasattr(self._progress, method):
            try:
                getattr(self._progress, method)(*args, **kwargs)
            except Exception:
                logger.debug(f"Progress callback error: {method}", exc_info=True)
