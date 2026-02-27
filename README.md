# Portfolio Mandate Builder

Standalone webapp for the **qport Planning Agent** — an interactive mandate builder that translates PM natural language into structured JSON mandates for portfolio construction.

Built on the [FAST framework](https://github.com/Three-Horizons-Capital/fast-demo-webapp/tree/main/agents/fast-framework) using the `create_app()` factory pattern.

**Live:** https://qport-webapp.yellowwave-e379fb09.centralus.azurecontainerapps.io

## How It Works

The agent walks PMs through a **6-section interactive interview**:

1. **Sleeves** — names, allocations, asset class, benchmark, template
2. **Filters** — exclusions, rating screens, ratio screens
3. **Factors** — names, blending scheme + weights
4. **Constraints** — names, bounds
5. **Extras** — feasibility, sampling, overlay (if applicable)
6. **Final Confirmation** — full expanded mandate in readable NL

At each section the PM can confirm ("Looks good"), request detail ("Show details"), or provide overrides. The agent outputs a complete JSON mandate with all parameters resolved via L2 defaults.

## Architecture

```
qport-agent/
├── webapp/
│   ├── app.py              # create_app() entry point
│   ├── factory.py          # Agent factory + LLM client adapter
│   ├── sub_agent.py        # PlanningSubAgent (SubAgent ABC)
│   ├── Dockerfile          # Standalone container
│   └── requirements.txt
├── tests/
│   ├── test_sub_agent.py   # State machine, chips, error handling (26 tests)
│   └── test_factory.py     # LLM adapter tests (6 tests)
├── vendor/
│   └── quant-platform/     # Git submodule — qport core packages
├── CLAUDE.md
└── pyproject.toml
```

### State Machine

```
idle ──→ interviewing ──→ finalized
  ↑                          │
  └──── (start over) ←──────┘
                             │
                  (revise) ──┘──→ finalized
```

- **idle** — first message triggers `orchestrator.plan(message, interactive=True)`
- **interviewing** — each response awaits PM input; `PlanningNeedsInput` exception drives the loop
- **finalized** — mandate JSON produced; PM can revise or start over

### LLM Client Adapter

The qport `QportOrchestrator` expects a `.send()` interface while FAST framework provides `EnhancedLLMClient` with `.complete_with_tools()`. The `_LLMClientAdapter` in `factory.py` bridges the two without modifying either package.

### Dynamic Action Chips

Chips are deterministic by state — not extracted from LLM output:

| State | Chips |
|-------|-------|
| Interviewing | "Looks good", "Show details" |
| Finalized | "Download Mandate", "Revise", "Start Over" |

Delivered to the frontend via SSE `[ACTIONS]` events for per-message rendering.

## Setup

### Prerequisites

- Python 3.12+
- Access to the [fast-demo-webapp](https://github.com/Three-Horizons-Capital/fast-demo-webapp) parent repo (for the FAST framework and frontend build)

### Install (local development)

```bash
git clone --recurse-submodules https://github.com/Three-Horizons-Capital/qport-agent.git
cd qport-agent

python3 -m venv venv && source venv/bin/activate
pip install -e vendor/quant-platform/packages/qdata \
            -e vendor/quant-platform/packages/qport
pip install --no-deps -e vendor/quant-platform/packages/qdata-mcp \
                      -e vendor/quant-platform/packages/qport-mcp
pip install --no-deps -e vendor/quant-platform/packages/qport-agent
pip install -e .
```

### Run Tests

```bash
python -m pytest tests/ -v
```

32 tests covering state transitions, action chips, error handling, adapter conversion, and start-over detection.

## Deployment

Builds from the `fast-demo-webapp` root (Docker context needs access to `agents/fast-framework/` and `frontend/dist/`):

```bash
cd /path/to/fast-demo-webapp

# Build frontend (if not already built)
cd frontend && npm run build && cd ..

# Build and push
docker build -t capmdemoacr64338.azurecr.io/qport-webapp:TAG \
  -f agents/qport-agent/webapp/Dockerfile .

az acr login --name capmdemoacr64338
docker push capmdemoacr64338.azurecr.io/qport-webapp:TAG

# Deploy
az containerapp update \
  --name qport-webapp \
  --resource-group capm-demo-webapp-rg \
  --image capmdemoacr64338.azurecr.io/qport-webapp:TAG
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes | Default LLM provider (Gemini) |
| `ACCESS_CODES` | Yes | Comma-separated access codes for authentication |
| `ANTHROPIC_API_KEY` | No | Alternative provider |
| `AZURE_AI_KEY` | No | Alternative provider |
| `AZURE_AI_ENDPOINT` | No | Required if using Azure AI |

## Dependencies

This repo vendors the [quant-platform](https://github.com/Three-Horizons-Capital/quant-platform) monorepo as a git submodule. The relevant packages:

| Package | Role |
|---------|------|
| `qport-agent` | `QportOrchestrator` — planning prompt, mandate parsing, multi-turn conversation |
| `qport` | Portfolio construction engine — signals, filters, optimizers |
| `qdata` | Data access layer — BigQuery loaders, panel data |
| `qdata-mcp` / `qport-mcp` | MCP tool layers (transitive dependencies) |

The [FAST framework](https://github.com/Three-Horizons-Capital/fast-demo-webapp/tree/main/agents/fast-framework) provides the webapp scaffold (`create_app`), `SubAgent` ABC, `EnhancedLLMClient`, SSE streaming, and the React frontend.
