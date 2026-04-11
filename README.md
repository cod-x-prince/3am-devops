# IncidentEnv — Autonomous Incident Remediation Environment

IncidentEnv is an OpenEnv-compatible RL environment for microservice incident response.  
It includes a Rust simulation core, Python environment wrappers, reward/graders, a FastAPI runtime, Torch/PPO training, a React dashboard, and historical trace replay in reality mode.

## What this repo contains

```text
Meta_Hackathon/
├── incident-env/               # Main runtime + training package
│   ├── engine/                 # Rust simulation engine (PyO3)
│   ├── envs/                   # Gym/OpenEnv wrappers
│   ├── rewards/                # Reward components
│   ├── graders/                # Programmatic + LLM grading
│   ├── training/               # PPO training/eval/backtest
│   ├── api/                    # FastAPI server
│   ├── dashboard/              # React UI
│   ├── scenarios/              # Scenario configs + historical traces
│   └── tests/                  # Test suite
├── API_CONTRACT.md
├── ARCHITECTURE.md
├── DEMO_GUIDE.md
├── command.md                  # End-to-end commands
├── trackA.md
└── trackB.md
```

## Core contract

| Surface | Value |
| --- | --- |
| Observation | `(72,)` float32 in `[0,1]` |
| Structure | 12 services × 6 metrics |
| Metric order | `cpu, memory, error_rate, latency_p50, latency_p99, request_rate` |
| Action | `MultiDiscrete([12, 7])` |
| Action layout | `[service_id, action_type]` |
| Reward | step reward in `[-1.0, 1.0]` |

## Execution modes

- **benchmark**: synthetic incident overlays for fast iteration.
- **reality**: historical trace replay + safety rails + operational scoring + audit trail.

Reality mode supports:
- timeline-based trace events
- action cooldowns and dependency checks
- high-risk action approvals (`approval_token`)
- action justification checks
- operational metrics (`mttr_minutes`, `false_positive_rate`, `slo_recovery`, `customer_impact_minutes`)

## Quick start (Windows)

From `C:\Users\ssang\Downloads\Meta_Hackathon\incident-env`:

```powershell
.\bootstrap.ps1
.\.venv\Scripts\python.exe -m pytest tests\
```

## Run the stack

### API

```powershell
cd C:\Users\ssang\Downloads\Meta_Hackathon\incident-env
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

### Dashboard (dev)

```powershell
cd C:\Users\ssang\Downloads\Meta_Hackathon\incident-env\dashboard
npm install
npm run dev
```

### Dashboard via API static route (`/ui`)

```powershell
cd C:\Users\ssang\Downloads\Meta_Hackathon\incident-env\dashboard
npm run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Open: `http://127.0.0.1:8000/ui`

## Runtime endpoints

Required:

- `GET /`
- `GET /health`
- `POST /reset`
- `POST /step`
- `GET /state`
- `GET /metadata`
- `GET /schema`
- `POST /mcp`

Supplemental:

- `GET /episode/options`
- `POST /episode/start`
- `WS /episode/stream/{episode_id}`
- `POST /backtest/run`

## Reality mode examples

### Reset with trace replay

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/reset" -ContentType "application/json" -Body '{"scenario":"bad_deploy","execution_mode":"reality","trace_id":"bad_deploy_trace_001"}'
```

### Step with justification + approval

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/step" -ContentType "application/json" -Body '{"action":[3,2],"justification":"Rollback deploy for active deploy and error_rate symptoms while reducing escalation risk.","approval_token":"INC-APPROVED","operator_id":"oncall"}'
```

## Training, eval, inference, backtest

```powershell
cd C:\Users\ssang\Downloads\Meta_Hackathon\incident-env
.\.venv\Scripts\python.exe training\train.py --epochs 100
.\.venv\Scripts\python.exe training\eval.py --episodes 25
.\.venv\Scripts\python.exe inference.py --agent greedy
.\.venv\Scripts\python.exe -m training.backtest --agent-mode greedy --max-incidents 50 --output backtest_report.json
```

## Validation command

```powershell
cd C:\Users\ssang\Downloads\Meta_Hackathon\incident-env
.\.venv\Scripts\python.exe -m pytest tests\
```

## Docker

```powershell
cd C:\Users\ssang\Downloads\Meta_Hackathon\incident-env
docker build -t incidentenv .
docker run --rm -p 8000:7860 incidentenv
```

## Troubleshooting

### `GET /episode/options` returns 404

You are likely running the wrong backend copy. Start API from **`incident-env`** (hyphen), not a legacy `incidentenv` folder.

### `trained mode requested ... falling back to random`

No checkpoint is available/selected. Use `greedy`, `random`, or `four_stage`, or train first to generate `checkpoints\latest.pt`.

### Browser console `content-all.js` errors

Errors like `Cannot find menu item with id translate-page` are from browser extensions, not IncidentEnv.

## Important docs

- `incident-env\README.md` — deep technical details
- `command.md` — command cookbook for setup/test/run/validate
- `API_CONTRACT.md` — integration contract
- `ARCHITECTURE.md` — system architecture
- `DEMO_GUIDE.md` — demo flow
- `trackA.md`, `trackB.md` — progress and handoff status
