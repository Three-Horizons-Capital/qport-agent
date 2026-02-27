# CLAUDE.md — qport-agent (Standalone Webapp)

## Overview

Standalone webapp for the qport Planning Agent — an interactive mandate builder that translates PM natural language into structured JSON mandates for portfolio construction. Built on the FAST framework's `create_app()` pattern.

## Architecture

```
qport-agent/
├── webapp/
│   ├── app.py          # create_app() entry point
│   ├── factory.py      # Agent factory + LLM client adapter
│   ├── sub_agent.py    # PlanningSubAgent (SubAgent ABC)
│   └── Dockerfile      # Standalone container deployment
├── vendor/
│   └── quant-platform/ # Git submodule — qport packages
├── tests/
│   ├── test_sub_agent.py  # State machine, chips, error handling (26 tests)
│   └── test_factory.py    # LLM adapter tests (6 tests)
└── pyproject.toml
```

### Package Dependency Chain

```
fast-framework (create_app, SubAgent ABC, EnhancedLLMClient)
    ↓
qport-agent/webapp (PlanningSubAgent, _LLMClientAdapter)
    ↓ imports
quant-platform/packages/qport-agent (QportOrchestrator, PlanningNeedsInput)
    ↓ imports
quant-platform/packages/qport (signals, filters, optimizers)
quant-platform/packages/qdata (BigQuery data access)
```

## LLM Client Adapter Pattern

The qport `QportOrchestrator` expects `.send(messages, system, tools) → AgentMessage`, but FAST framework provides `EnhancedLLMClient` with `.complete_with_tools(messages, tools, system_prompt) → LLMResponse`. The `_LLMClientAdapter` bridges this:

```python
class _LLMClientAdapter:
    def send(self, messages, system, tools):
        resp = self._client.complete_with_tools(
            messages=messages, tools=tools,
            system_prompt=system if isinstance(system, str) else None,
        )
        tool_calls = [QportToolCall(id=tc.id, name=tc.name, input=tc.input)
                      for tc in resp.tool_calls]
        return AgentMessage(text=resp.content, tool_calls=tool_calls,
                          stop_reason=resp.stop_reason, usage={})
```

## PlanningSubAgent State Machine

```
idle → interviewing → finalized
  |                      ↓ (revision)
  |                   finalized
  ← ← ← ← ← ← ← ← ← (start over)
```

- **idle**: First message triggers `orchestrator.plan(message, interactive=True)`
- **interviewing**: `PlanningNeedsInput` raised → return partial response with interview chips
- **finalized**: Mandate JSON produced → return success response with finalized chips

## Dynamic Action Chips

Chips are deterministic by state:
- **Interview phase**: "Looks good" (confirms section) + "Show details" (expands L2 defaults)
- **Finalized phase**: "Download Mandate" + "Revise" + "Start Over"

Pipeline: `AgentResponse.action_chips` → `_run_chat_blocking` → SSE `[ACTIONS]` event → frontend renders per-message chips

## Running

```bash
source /home/kiosk/fast-demo-webapp/venv/bin/activate
pip install -e vendor/quant-platform/packages/qdata -e vendor/quant-platform/packages/qport
pip install --no-deps -e vendor/quant-platform/packages/qdata-mcp -e vendor/quant-platform/packages/qport-mcp
pip install --no-deps -e vendor/quant-platform/packages/qport-agent
```

## Testing

```bash
python -m pytest tests/ -v  # 32 tests (26 sub_agent + 6 adapter)
```

## Deployment

```bash
# Build from fast-demo-webapp root
docker build -t capmdemoacr64338.azurecr.io/qport-webapp:TAG -f agents/qport-agent/webapp/Dockerfile .
az acr login --name capmdemoacr64338
docker push capmdemoacr64338.azurecr.io/qport-webapp:TAG
az containerapp update --name qport-webapp --resource-group capm-demo-webapp-rg --image capmdemoacr64338.azurecr.io/qport-webapp:TAG
```

## Environment Variables

Required: `GOOGLE_API_KEY` (default provider), `ACCESS_CODES`
Optional: `ANTHROPIC_API_KEY`, `AZURE_AI_KEY`, `AZURE_AI_ENDPOINT`

## Key Conventions

- No tool-calling loop — each `chat()` is one LLM round-trip (`MAX_TURNS = 1`)
- Orchestrator is provider-agnostic via the adapter pattern
- Planning prompt includes 10 decision rules, L2 defaults, data catalog, NL translation table
- Interactive interview mode triggered by `[interactive]` prefix on user message
- The webapp uses FAST framework's `create_app()` with `features.action_chips: False` (static bar disabled; dynamic chips come via SSE)
