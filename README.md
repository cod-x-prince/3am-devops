# IncidentEnv - OpenEnv Hackathon Submission

IncidentEnv is a **real-world incident-response environment** for training and evaluating AI agents on microservice outage remediation.  
It is designed for OpenEnv-style workflows with typed models, deterministic grading, and reproducible baseline inference.

---

## Why this is a genuine environment (not a toy)

This environment models work that real SRE/on-call teams do:

- triage unhealthy services from noisy telemetry
- choose targeted remediation actions under time pressure
- reduce blast radius while avoiding false-positive interventions
- restore service health across dependency graphs

The task is not "winning a game"; it is operational incident recovery with realistic tradeoffs.

---

## Quick judge path (fast verification)

From `incident-env\` on Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\
.\.venv\Scripts\python.exe inference.py
docker build -t incidentenv-openenv .
docker run --rm -p 8000:8000 incidentenv-openenv
```

Then verify endpoints:

- `GET http://localhost:8000/`
- `GET http://localhost:8000/health`
- `POST http://localhost:8000/reset`
- `POST http://localhost:8000/step`
- `GET http://localhost:8000/state`
- `GET http://localhost:8000/metadata`
- `GET http://localhost:8000/schema`
- `POST http://localhost:8000/mcp`

---

## Environment contract

| Item | Value |
| --- | --- |
| Observation space | `Box(shape=(72,), dtype=float32, range=[0,1])` |
| Observation layout | 12 services x 6 metrics |
| Metric order | `cpu, memory, error_rate, latency_p50, latency_p99, request_rate` |
| Action space | `MultiDiscrete([12, 7])` |
| Action meaning | `[target_service_id, action_type]` |
| Action types | RestartService, ScaleUp, RollbackDeploy, RerouteTraffic, ToggleFeatureFlag, TriggerCircuitBreaker, NoOp |
| Reward range (step) | `[-1.0, 1.0]` |
| Task score range | `[0.0, 1.0]` |

Typed OpenEnv models are implemented and wired in:

- `incident-env\envs\openenv_models.py`
- `incident-env\envs\openenv_env.py`
- `incident-env\openenv.yaml`

---

## Task ladder (easy -> medium -> hard)

| Task ID | Difficulty | Scenario | Objective | Grader |
| --- | --- | --- | --- | --- |
| `bad_deploy_easy` | Easy | `bad_deploy` | resolve single bad deployment quickly | programmatic |
| `cascade_timeout_medium` | Medium | `cascade_timeout` | stop failure propagation early | programmatic |
| `multi_fault_hard` | Hard | `multi_fault` | recover from simultaneous faults | programmatic |

All task graders output normalized scores in `[0.0, 1.0]`.

---

## Reward design (meaningful shaping)

Per-step reward includes partial progress and penalties:

- **MTTR signal**: faster resolution gets higher reward
- **Blast radius signal**: fewer unhealthy services improves reward
- **False alarm penalty**: unnecessary or low-value actions reduce reward
- **Composite bounded reward** in `[-1.0, 1.0]`

Reward implementation lives in:

- `incident-env\rewards\mttr.py`
- `incident-env\rewards\blast_radius.py`
- `incident-env\rewards\false_alarm.py`
- `incident-env\rewards\composite.py`

---

## Reproducibility + evidence stats

### Latest local validation snapshot

| Proof point | Latest observed result | How to reproduce |
| --- | --- | --- |
| Test suite | `17 passed` | `.\.venv\Scripts\python.exe -m pytest tests\` |
| OpenEnv structural validation | `[OK] incident-env: Ready for multi-mode deployment` | `.\.venv\Scripts\openenv.exe validate` (or `openenv validate`) |
| Baseline task scores | `0.85`, `0.33`, `0.69` (avg `0.62`) | `.\.venv\Scripts\python.exe inference.py` |
| Docker runtime health | `root=200`, `health=healthy`, `reset_obs_len=72` | `docker build` + `docker run` + endpoint checks |

### Baseline scores (inference.py)

| Task | Score |
| --- | --- |
| `bad_deploy_easy` | `0.85` |
| `cascade_timeout_medium` | `0.33` |
| `multi_fault_hard` | `0.69` |
| **Average** | **`0.62`** |

Inference logs follow strict required format:

- `[START] task=... env=... model=...`
- `[STEP] step=... action=... reward=... done=... error=...`
- `[END] success=... steps=... score=... rewards=...`

---

## Submission environment variables

Set these before running inference/deployment:

- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`

Used by: `incident-env\inference.py`

---

## Hugging Face Space deployment checklist

1. Create a Space with **Docker** SDK.
2. Point Space to this repository (`main` branch).
3. Add Space variables: `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`.
4. Wait for build completion.
5. Run endpoint checks on the live Space URL.
6. Run the official pre-validation script against the live URL.

---

## Repository map

```text
Meta_Hackathon/
├── incident-env/                 # Main submission package
│   ├── engine/                   # Rust simulation core
│   ├── envs/                     # Gym/OpenEnv wrappers + typed models
│   ├── rewards/                  # Reward shaping
│   ├── graders/                  # Programmatic grading
│   ├── api/                      # FastAPI runtime
│   ├── dashboard/                # React dashboard
│   ├── training/                 # TorchRL training/eval
│   ├── tests/                    # Test suite
│   ├── openenv.yaml              # OpenEnv contract metadata
│   ├── inference.py              # Required baseline script
│   └── Dockerfile                # Containerized runtime
├── API_CONTRACT.md
├── ARCHITECTURE.md
├── DEMO_GUIDE.md
├── trackA.md
└── trackB.md
```

---

## Additional docs

- Deep technical README: `incident-env\README.md`
- Integration contract: `API_CONTRACT.md`
- Architecture overview: `ARCHITECTURE.md`
- Demo flow: `DEMO_GUIDE.md`
- Track status and remaining ops: `trackA.md`, `trackB.md`
