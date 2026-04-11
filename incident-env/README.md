---
title: IncidentEnv
emoji: 🚨
colorFrom: red
colorTo: yellow
sdk: docker
pinned: false
tags:
  - openenv
  - incident-remediation
  - microservices
  - reinforcement-learning
---

# IncidentEnv

IncidentEnv is a real-world inspired OpenEnv-style environment for autonomous incident remediation in microservice systems. The agent must detect failures, choose remediation actions, and reduce blast radius under time pressure.

## Judge Quickstart

From `incident-env/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\
.\.venv\Scripts\python.exe inference.py
docker build -t incidentenv-openenv . && docker run --rm -p 8000:7860 incidentenv-openenv
```

Expected runtime endpoints after container start:

- `GET /`
- `GET /health`
- `POST /reset`
- `POST /step`
- `GET /state`
- `GET /metadata`
- `GET /schema`
- `POST /mcp`

## Why this environment matters

This is not a toy game. It simulates an incident response workflow that real SRE and platform teams perform: diagnose service health, stop propagation, restart or reroute affected services, and restore the system to a healthy state.

## Environment Summary

- Observation space: `(72,)` float32 normalized to `[0, 1]`
- Action space: `MultiDiscrete([12, 7])`
- State API: `state()` returns a JSON-serializable snapshot
- Episode length: up to 50 steps
- Core scenarios: bad deploy, memory leak, cascade timeout, thundering herd, split brain, multi fault

## Execution Modes

IncidentEnv now supports two runtime modes:

- `benchmark` (default): synthetic incident overlays for fast iteration.
- `reality`: timeline-based trace replay from `scenarios/traces/` with safety rails, action justification checks, approval gates for high-risk actions, and per-step audit logs.

Reality mode can be selected via API payloads (`execution_mode: "reality"`) and can pin a trace with `trace_id`.

The observation vector contains 12 services x 6 metrics each:

- cpu
- memory
- error_rate
- latency_p50
- latency_p99
- request_rate

The action space uses two discrete choices:

- service target: `0-11`
- action type: `0-6`

Action types:

- RestartService
- ScaleUp
- RollbackDeploy
- RerouteTraffic
- ToggleFeatureFlag
- TriggerCircuitBreaker
- NoOp

## OpenEnv Interface

The OpenEnv entrypoint is `envs.openenv_env:OpenIncidentEnv` and exposes typed models:

- `ObservationModel` (72 normalized float values)
- `ActionModel` (`service_id` in `[0,11]`, `action_type` in `[0,6]`)
- `RewardModel` (`value` in `[-1.0, 1.0]`)

Lifecycle:

- `reset()` returns `ObservationModel`
- `step(ActionModel)` returns `(ObservationModel, RewardModel, done, info)`
- `state()` returns a stable JSON-serializable snapshot

## Task Ladder

IncidentEnv includes three graded tasks with increasing difficulty:

1. `bad_deploy_easy`
   - Scenario: `bad_deploy`
   - Goal: resolve a single faulty deploy quickly with no unnecessary actions
   - Grader: programmatic
   - Reward range: `[0.0, 1.0]`

2. `cascade_timeout_medium`
   - Scenario: `cascade_timeout`
   - Goal: stop downstream propagation before it spreads too far
   - Grader: programmatic
   - Reward range: `[0.0, 1.0]`

3. `multi_fault_hard`
   - Scenario: `multi_fault`
   - Goal: resolve simultaneous failures while minimizing blast radius
   - Grader: programmatic
   - Reward range: `[0.0, 1.0]`

The full scenario set also includes `memory_leak`, `thundering_herd`, and `split_brain` for broader evaluation and curriculum coverage.

## Reward Design

The reward system provides partial progress signals instead of binary end-of-episode scoring.

- `mttr_reward()` rewards fast incident resolution
- `blast_radius_reward()` rewards reducing the number of unhealthy services
- `false_alarm_reward()` penalizes unnecessary actions
- `composite_reward()` combines the above into a bounded `[-1.0, 1.0]` reward

## Baseline Inference

The baseline entrypoint is `inference.py` at the repo root.

It:

- uses the OpenAI client
- reads `API_BASE_URL`, `MODEL_NAME`, and `HF_TOKEN` from the environment
- supports multiple policy modes via `--agent`:
  - `llm` (strict LLM mode, default)
  - `greedy` (fault-aware heuristic)
  - `random` (seeded random baseline)
  - `four-stage` (detect → prioritize → shortlist → LLM/heuristic choose)
- prints strict structured logs in `[START]`, `[STEP]`, and `[END]` format
- produces reproducible scores across the configured tasks

Example:

```powershell
$env:API_BASE_URL = "https://router.huggingface.co/v1"
$env:MODEL_NAME = "Qwen/Qwen2.5-72B-Instruct"
$env:HF_TOKEN = "your-token"
.\.venv\Scripts\python.exe inference.py
.\.venv\Scripts\python.exe inference.py --agent greedy
.\.venv\Scripts\python.exe inference.py --agent random --seed 42
.\.venv\Scripts\python.exe inference.py --agent four-stage
```

`HF_TOKEN` (or `OPENAI_API_KEY`) is required. In strict mode, no heuristic fallback is used for action generation.

Latest local baseline snapshot:

| Task | Score (0.0-1.0) |
| --- | --- |
| `bad_deploy_easy` | `0.85` |
| `cascade_timeout_medium` | `0.33` |
| `multi_fault_hard` | `0.69` |
| **Average** | **`0.62`** |

## Setup

Windows:

```powershell
cd incident-env
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest tests\
```

Optional OpenEnv validator command:

```powershell
openenv validate
```

Run the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000
```

Reality mode reset + step example:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/reset" -ContentType "application/json" -Body '{"scenario":"bad_deploy","execution_mode":"reality","trace_id":"bad_deploy_trace_001"}'
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/step" -ContentType "application/json" -Body '{"action":[3,2],"justification":"Rollback deploy for active deploy and error_rate symptoms","approval_token":"INC-APPROVED","operator_id":"oncall"}'
```

Run historical backtests (reality traces):

```powershell
.\.venv\Scripts\python.exe -m training.backtest --agent-mode greedy --max-incidents 50 --output backtest_report.json
```

Run the dashboard:

```powershell
cd dashboard
npm install
npm run dev
```

## Docker

Build and run the container:

```powershell
docker build -t incidentenv .
docker run --rm -p 8000:7860 incidentenv
```

The container binds Uvicorn to `${PORT:-7860}` so it stays healthy on hosted runtimes (including Hugging Face Spaces).

## Hugging Face Spaces

### Deploy to Hugging Face Spaces

The project is fully containerized and ready to deploy as a Hugging Face Space. The Docker container packages the FastAPI backend and serves the interactive React dashboard.

**Deployment Steps:**

1. Create a Hugging Face Space at [https://huggingface.co/spaces](https://huggingface.co/spaces)
2. Select **Docker** as the SDK
3. Upload your repository or connect your GitHub fork
4. HF will automatically build the image and serve on the platform-provided `PORT` (default fallback: 7860)

**What You'll Get:**

- FastAPI backend running on the platform-provided port
- Interactive React dashboard with:
  - Service graph visualization
  - Real-time metrics feed
  - Agent action logs
  - Scenario scorecard
- Full OpenEnv compliance for programmatic access

**Local Testing (Before HF Deployment):**

```powershell
docker build -t incidentenv .
docker run --rm -p 8000:7860 incidentenv
# API metadata: http://localhost:8000/
# Dashboard: http://localhost:8000/ui
```

**Note:** The container uses `python:3.11-slim` with Rust toolchain for compilation. Build may take 5-10 minutes on first run. Subsequent deployments will use cached layers.

When the dashboard bundle is present, browser requests to `/` are redirected to `/ui`. API clients can still call `/` and receive JSON runtime metadata.

---

The submission validator should be able to build the image, start the service, and reach:

- `/` (200 health/root response)
- `/reset` (OpenEnv reset endpoint)
- `/step` (OpenEnv step endpoint)
- `/state` (OpenEnv state endpoint)

## Files of Interest

- `envs/incident_env.py`
- `openenv.yaml`
- `inference.py`
- `Dockerfile`
- `rewards/`
- `graders/`
- `scenarios/configs/`
- `tests/`
