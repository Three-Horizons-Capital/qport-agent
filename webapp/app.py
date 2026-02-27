"""Standalone Portfolio Mandate Builder webapp entry point."""
from pathlib import Path

from fast_framework.webapp import create_app
from .factory import create_planning_agent

# Resolve frontend dist — Docker: /app/frontend/dist, local dev: ../../frontend/dist
_FRONTEND_CANDIDATES = [
    Path("/app/frontend/dist"),
    Path(__file__).parent.parent.parent / "frontend" / "dist",
]
_frontend_dist = next((str(p) for p in _FRONTEND_CANDIDATES if p.exists()), None)

_WELCOME_MESSAGE = (
    "Welcome to the **Portfolio Mandate Builder**.\n\n"
    "I'll help you build a structured portfolio mandate through "
    "a guided conversation. Tell me what you're looking to build "
    "and I'll walk you through each section.\n\n"
    "**Examples to get started:**\n"
    "- *Build me an S&P 500 value + momentum portfolio*\n"
    "- *USIG credit multifactor with value, carry, and lowvol*\n"
    "- *Replicate the S&P 500 excluding Energy with 50 positions*\n"
)

_DEFAULT_CHIPS = [
    {
        "label": "Equity Multifactor",
        "message": "Build an S&P 500 multifactor portfolio",
        "autoSend": False,
    },
    {
        "label": "Credit Multifactor",
        "message": "Build a USIG credit multifactor portfolio",
        "autoSend": False,
    },
    {
        "label": "ESG Replication",
        "message": "Replicate the S&P 500 with ESG exclusions",
        "autoSend": False,
    },
    {
        "label": "Sampled Index",
        "message": "Replicate an index with sampled positions",
        "autoSend": False,
    },
]

app = create_app(
    agent_name="qport-agent",
    agent_factory=create_planning_agent,
    title="Portfolio Mandate Builder",
    subtitle="Three Horizons Capital",
    welcome_message=_WELCOME_MESSAGE,
    features={
        "upload": False,
        "mandate": True,
        "benchmarks": False,
        "action_chips": True,
    },
    default_chips=_DEFAULT_CHIPS,
    allowed_providers=["google", "glm"],
    default_provider="google",
    frontend_dist=_frontend_dist,
)
