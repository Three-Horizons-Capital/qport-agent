# qport-agent — Current Status (Feb 27, 2026)

## What Was Built

Standalone webapp for the **qport Planning Agent** — an interactive mandate builder that translates PM natural language into structured JSON mandates for portfolio construction.

### Repos Involved

| Repo | Path | Branch |
|------|------|--------|
| qport-agent (standalone) | `/home/kiosk/qport-agent` | `main` |
| fast-demo-webapp (parent) | `/home/kiosk/fast-demo-webapp` | `main` |
| quant-platform (vendor submodule) | `/home/kiosk/qport-agent/vendor/quant-platform` | `main` |

### Deployed

- **Live URL**: https://qport-webapp.yellowwave-e379fb09.centralus.azurecontainerapps.io
- **Image**: `capmdemoacr64338.azurecr.io/qport-webapp:v5`
- **Container App**: `qport-webapp` in `capm-demo-webapp-rg` (subscription `b6ab34c0-522c-46d7-a09a-5eecedb132b2`)
- **Provider**: Google Gemini (`GOOGLE_API_KEY`)

### Tests

32/32 passing (26 sub_agent + 6 adapter) in 0.67s.

## What Was Done (Feb 27 Session)

1. **Fixed missing dynamic action chips** — replaced fragile `_parse_chips()` regex with deterministic state-based chips (`_INTERVIEW_CHIPS`, `_FINALIZED_CHIPS`)
2. **Fixed unclear section progression** — updated interactive interview prompt to require "Section N/6: [Name]" headers and opening explanation
3. **Added 3 NotebookLM knowledge sources** (CLAUDE.md, interview design, webapp architecture)
4. **Updated 2 outdated NotebookLM sources** (nithin-handoff, roadmap) to reflect standalone webapp
5. **Updated source-registry.yaml** — 33 total sources, 10 qport-related, routing patterns updated
6. **Created README.md** for qport-agent repo with architecture, state machine, UX, setup, deployment
7. **Updated fast-demo-webapp CLAUDE.md** with standalone qport webapp documentation
8. **Wrote memo to Bin** (Google Doc: `1TP6PiH_ShW7UWcKCu7CQJ5eHq4frpRsetTAyGkhZruY`)
9. **Added Chat UX section** to README with layout diagram, conversation flow, streaming, chips, mandate download

## Known Bug — `continue_plan()` 10-turn failure

**Symptom**: "Something went wrong: continue_plan() did not produce a valid mandate after 10 turns."

**Root cause**: In `orchestrator.py:648-711`, after the PM confirms all 6 sections, the LLM outputs mandate JSON. If Pydantic validation fails (`Mandate(**data)` in `parse_mandate_response`), the retry message is generic ("Please output the mandate as a JSON object...") — it doesn't tell the LLM WHAT validation failed. The LLM produces the same wrong JSON 10 times.

**Fix needed**: Pass the Pydantic `ValueError` message back to the LLM in the retry prompt:
```python
# In continue_plan(), line ~695-706 of orchestrator.py:
except ValueError as e:
    if "?" in resp.text:
        raise PlanningNeedsInput(resp.text)
    messages.append({
        "role": "user",
        "content": f"JSON validation error: {e}\n\nFix the error and output only valid JSON.",
    })
```

**Same fix needed in `_planning_phase()`** (line ~880-897) which has the identical pattern.

**Compounding factor**: Gemini rate limits — the 10-turn retry loop burns through tokens (32K-48K per batch), hitting rate limits and making each retry slower.

**File**: `vendor/quant-platform/packages/qport-agent/qport_agent/orchestrator.py`

## Pending Work

- [ ] **Fix continue_plan() retry loop** — pass validation errors to LLM (see above)
- [ ] Full eval validation pass (planning + E2E tiers)
- [ ] Planning prompt audit and cleanup
- [ ] Agent reorganization (enforce ownership boundaries)
- [ ] Integration into main fast-demo-webapp (currently standalone)
- [ ] Commit untracked `CLAUDE.md` in qport-agent
- [ ] Update `fast-demo-webapp` submodule pointer for `agents/qport-agent`

## Uncommitted State

| Repo | Status |
|------|--------|
| qport-agent | 1 untracked file: `CLAUDE.md` |
| fast-demo-webapp | Submodule pointers dirty (`agents/qport-agent` ahead), untracked `docs/plans/` |
| quant-platform | Clean |

## Key Files

### Standalone Webapp
| File | Purpose |
|------|---------|
| `webapp/app.py` | `create_app()` entry point, welcome message, feature flags |
| `webapp/factory.py` | Agent factory + `_LLMClientAdapter` bridging FAST → qport |
| `webapp/sub_agent.py` | `PlanningSubAgent` state machine + deterministic chips |
| `webapp/Dockerfile` | Standalone container build |
| `tests/test_sub_agent.py` | State machine, chips, error handling (26 tests) |
| `tests/test_factory.py` | LLM adapter tests (6 tests) |

### Planning Core (in vendor/quant-platform)
| File | Purpose |
|------|---------|
| `qport_agent/planning/prompts.py` | `build_planning_prompt()`, 10 rules, interactive interview |
| `qport_agent/planning/data_catalog.json` | Benchmark/factor/template catalog |
| `qport_agent/mandate/schema.py` | Pydantic v2 models (Mandate, Sleeve, Factor, etc.) |
| `qport_agent/mandate/resolver.py` | `expand_mandate()`, L2 default resolution |
| `qport_agent/mandate/defaults.json` | Canonical L2 defaults |
| `qport_agent/orchestrator.py` | `plan()`, `continue_plan()`, `revise_plan()` — **bug is here** |

### NotebookLM
- Source registry: `vendor/quant-platform/.standards/notebooklm/source-registry.yaml`
- Notebook ID: `1d98c72a-9caf-4bf6-b735-f195a5fd0466`
- CLI: `/home/kiosk/.local/bin/nlm`
