# Track B - Progress Tracker

> Person B | IncidentEnv Hackathon | Last Updated: 2026-04-11

---

## Identity

- **Track:** B - Training, API Server, Dashboard
- **Owns:** `training/`, `api/`, `dashboard/`
- **Depends on Track A for:** core environment contract and runtime behavior

---

## Overall Progress

```
Training    [##########] 100% DONE
Curriculum  [##########] 100% DONE
Evaluation  [##########] 100% DONE
API Server  [##########] 100% DONE
Dashboard   [##########] 100% DONE
Integration [##########] 100% DONE
```

---

## Progress Update (2026-04-11)

- ✅ Phase 2 win-plan execution status is finalized and synced.
- ✅ Track B delivery status remains 100% complete and integration-ready.
- ✅ No new blockers introduced.
- ✅ Added API support for execution mode split (`benchmark` vs `reality`) and trace selection.
- ✅ Added historical backtest runner (`training/backtest.py`) and API endpoint (`POST /backtest/run`).
- ✅ Updated dashboard controls to select execution mode and trace in episode runs.
- ✅ Hardened HF dashboard serving: browser `/` now routes to `/ui` when static assets exist, while API clients still receive JSON metadata at `/`.
- ✅ Updated Docker builds to compile `dashboard/dist` inside container images so `/ui` is available on hosted runtimes.

---

## Submission-Critical Status

| Area | Status | Notes |
| --- | --- | --- |
| PPO training pipeline | DONE | TorchRL training/eval code integrated with IncidentEnv |
| FastAPI runtime | DONE | `/health`, `/metadata`, `/schema`, `/mcp`, `/reset`, `/step`, `/state` |
| Episode API + WS stream | DONE | Episode lifecycle + streaming endpoints implemented |
| Dashboard components | DONE | Graph, metrics, logs, score card, scenario/mode controls |
| Dashboard production build | DONE | `npm run build` passes |
| OpenEnv submission surface | DONE | `openenv.yaml`, `inference.py`, `Dockerfile` wired and validated |

---

## What Is Left (Final Ops)

- [ ] Set Hugging Face Space environment variables: `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`.
- [ ] Deploy the current image/repo to the Space and verify live endpoints (`/`, `/health`, `/metadata`, `/schema`, `/mcp`, `/reset`, `/step`).
- [ ] Run the official pre-validation script against the live Space URL and keep the output artifact.
- [ ] Run a final `inference.py` pass in the deployment context and keep `[START]/[STEP]/[END]` logs for submission evidence.

---

## Key Completed Items

- `api/main.py` aligned for validator/runtime requirements, including metadata/schema/MCP paths.
- Baseline inference script emits strict `[START]`, `[STEP]`, `[END]` logs.
- Docker image builds successfully and serves required OpenEnv endpoints.
- Root/reset/health and schema/metadata/MCP endpoint checks pass on rebuilt container.
- API + dashboard integration is in a releasable state for demo/submission.
- Phase 2 execution summary finalized and synced with shared progress docs.
- Reality-mode controls and backtest surfaces are now wired across API + dashboard + tests.

---

## Blockers

- None.

---

## Messages for Person A

- [DONE] Track B is fully synced to the current API contract.
- [DONE] No additional Track A changes are required for submission.
- [DONE] Phase 2 completion status and evidence links are synced in shared docs.
