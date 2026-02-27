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

## Chat UX

The webapp uses the FAST framework's React frontend — a dark-themed two-panel layout.

### Layout

```
┌──────────────────────────────────────────────────────┐
│  Portfolio Mandate Builder     Three Horizons Capital │  ← Header
├──────────┬───────────────────────────────────────────┤
│  Input   │  Analysis Report                          │
│          │                                           │
│          │  [A] Welcome message with example prompts │
│          │                                           │
│          │       [U] "Build me an S&P 500 value..."  │
│          │                                           │
│          │  [A] Section 1/6: Sleeves                 │
│          │      ... sleeve summary ...               │
│          │      ┌──────────┐ ┌──────────────┐        │
│          │      │Looks good│ │Show details  │        │  ← Dynamic chips
│          │      └──────────┘ └──────────────┘        │
│          │                                           │
│ ┌──────────────┐                                     │
│ │Mandate Ready │  ┌──────────────────────────────┐   │
│ │Download JSON │  │ Type a message...        Send │   │  ← Chat input
│ └──────────────┘  └──────────────────────────────┘   │
└──────────┴───────────────────────────────────────────┘
```

- **Left panel ("Input")**: Shows mandate download card when the interview finalizes. Upload is disabled for this app.
- **Center panel ("Analysis Report")**: Chat conversation with streaming responses and embedded action chips.

### Conversation Flow

1. **Welcome message** — displays on load with example prompts (equity multifactor, credit multifactor, ESG replication, sampled index)
2. **PM sends first message** — e.g., "Build me an S&P 500 value + momentum portfolio"
3. **Agent responds with Section 1/6: Sleeves** — summarizes sleeve allocation in plain English, with two action chips:
   - **"Looks good"** — confirms the section and advances to the next
   - **"Show details"** — expands L2 default parameters for that section
4. **Repeat for Sections 2-5** (Filters, Factors, Constraints, Extras) — same confirm/detail pattern
5. **Section 6: Final Confirmation** — full expanded mandate in readable NL, with three chips:
   - **"Download Mandate"** — triggers JSON download via the left panel
   - **"Revise"** — re-enters the interview for targeted changes
   - **"Start Over"** — resets state to idle for a new mandate

### Streaming

Responses stream line-by-line via Server-Sent Events (SSE). During streaming:
- A "typing..." indicator with blinking cursor appears
- Progress events show contextual status (e.g., "Analyzing request...")
- Action chips appear after the response completes (attached to the final message)

### Action Chips

Chips render as rounded pill buttons below each assistant message:
- **Emerald-colored** for qport domain actions
- **Only the latest message's chips are clickable** — older chips are greyed out
- Clicking a chip sends its `message` text as the next user message (with an `intent_hint` for backend routing)

### Mandate Download

When the agent finalizes a mandate, the backend emits a `[MANDATE]` SSE event with an `export_id`. The left panel shows a "Mandate Ready" card with a **"Download Mandate (JSON)"** button that fetches the full mandate JSON via `/api/mandate/download/{export_id}`.

### Input

- **Text area** at the bottom of the center panel — Enter to send, Shift+Enter for newline
- Benchmark selector is disabled (not relevant for mandate building)
- Static chip bar is disabled (dynamic chips via SSE replace it)

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
