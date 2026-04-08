# Copilot Instructions — IncidentEnv Hackathon

## Project Overview

**IncidentEnv** is an OpenEnv-compatible reinforcement learning environment for autonomous incident remediation in microservice architectures. The project is split into two parallel development tracks:

- **Track A**: Rust simulation engine, OpenEnv Python wrapper, reward functions, and graders
- **Track B**: TorchRL training pipeline, FastAPI server, and React dashboard

## Build, Test, and Run Commands

### Initial Setup

**Windows (PowerShell):**
```powershell
cd incident-env
.\bootstrap.ps1
```

**Linux/MacOS:**
```bash
cd incident-env
make install
make build-rust
cd dashboard && npm install
```

### Building

**Rebuild Rust engine:**
```bash
# Unix/WSL
cd incident-env && make build-rust

# Windows (from incident-env directory)
.\.venv\Scripts\maturin.exe develop -m engine\Cargo.toml --release
```

**Note:** Always use `.venv\Scripts\python.exe` on Windows, not bare `python`.

### Testing

**Run all tests:**
```bash
# Unix/WSL
cd incident-env && make test

# Windows
cd incident-env && .\.venv\Scripts\python.exe -m pytest tests\
```

**Run a single test file:**
```bash
# Unix/WSL
pytest tests/test_env.py

# Windows
.\.venv\Scripts\python.exe -m pytest tests\test_env.py
```

**Run a single test:**
```bash
pytest tests/test_env.py::test_reset_returns_valid_obs
```

### Linting

```bash
cd incident-env && make lint
# Or manually:
ruff check . && black --check .
```

### Running Services

**Training:**
```bash
cd incident-env && make train
# Or: python training/train.py
```

**API Server (port 8000):**
```bash
cd incident-env && make api
# Or: uvicorn api.main:app --reload --port 8000
```

**Dashboard (port 5173):**
```bash
cd incident-env && make dashboard
# Or: cd dashboard && npm run dev
```

**Demo mode (API + Dashboard together):**
```bash
cd incident-env && make demo
```

**TensorBoard (port 6006):**
```bash
tensorboard --logdir incident-env/logs/
```

## Architecture

### System Layers

```
┌─────────────────────────────────────────────────────────┐
│ Track B: React Dashboard (D3 + Recharts)               │
│         ↕ WebSocket (EpisodeFrame JSON)                │
│ Track B: FastAPI Server (port 8000)                    │
│         ↕ Python API calls                             │
│ Track B: TorchRL PPO Agent                             │
│         ↕ gymnasium API (obs, reward, terminated)      │
│ Track A: IncidentEnv (Python wrapper)                  │
│         ↕ PyO3 bindings                                │
│ Track A: Rust simulation engine (incident_core)        │
└─────────────────────────────────────────────────────────┘
```

### Performance Model

The Rust engine provides sub-millisecond step execution (~0.1ms per step). The target is >10,000 environment steps/second during training. Python code wraps this for API compliance but delegates heavy computation to Rust.

### Integration Contract

The handoff between Track A and Track B is defined in `API_CONTRACT.md`:

- **Observation space:** `(72,)` numpy array, float32, normalized to [0, 1]
  - 12 services × 6 metrics each
  - Metric order: [cpu, memory, error_rate, latency_p50, latency_p99, request_rate]
  
- **Action space:** `MultiDiscrete([12, 7])`
  - action[0]: target service ID (0-11)
  - action[1]: action type (0-6) → RestartService, ScaleUp, RollbackDeploy, RerouteTraffic, ToggleFeatureFlag, TriggerCircuitBreaker, NoOp

- **`env.step()` returns:** `(obs, reward, terminated, truncated, info)`
  - `reward` is always in [-1.0, 1.0]
  - `info["services_json"]` contains full state for API/dashboard

### Directory Structure

```
incident-env/
├── engine/                  # Track A: Rust simulation core
│   ├── src/
│   │   ├── service_graph.rs
│   │   ├── fault_injector.rs
│   │   ├── metrics_engine.rs
│   │   └── lib.rs
│   └── Cargo.toml
├── envs/                    # Track A: OpenEnv wrapper
│   ├── incident_env.py
│   └── scenarios.py
├── rewards/                 # Track A: Reward functions
│   ├── mttr.py
│   ├── blast_radius.py
│   ├── false_alarm.py
│   └── composite.py
├── graders/                 # Track A: Evaluation
│   ├── programmatic.py
│   └── llm_grader.py
├── scenarios/               # Track A: Scenario configs
│   └── configs/
├── training/                # Track B: RL training
│   ├── train.py
│   ├── curriculum.py
│   └── eval.py
├── api/                     # Track B: FastAPI server
│   └── main.py
├── dashboard/               # Track B: React dashboard
│   └── src/
│       ├── components/
│       │   ├── ServiceGraph.jsx
│       │   ├── MetricsFeed.jsx
│       │   ├── AgentLog.jsx
│       │   └── ScoreCard.jsx
│       └── hooks/
│           └── useEpisodeStream.js
└── tests/
    ├── test_smoke.py        # Track A: Smoke tests
    ├── test_env.py          # Track A: Environment tests
    ├── test_graders.py      # Track A: Grader tests
    ├── test_scenarios.py    # Track A: Scenario tests
    └── mock_env.py          # Track B: Unblocking stub
```

## Key Conventions

### Python

- **Full type annotations required** for all function signatures
- Use **Pydantic** for data validation and models
- Reward functions must return `float` in `[-1.0, 1.0]` (normalized)
- All OpenEnv wrappers must comply with the `gymnasium` API
- No synchronous Ollama calls in the training loop (use async or separate process)

### Rust

- PyO3 bindings: use `#[pyclass]`, `#[pymethods]`, `#[pymodule]`
- Performance-critical code lives in Rust; Python handles orchestration
- Return types must be PyO3-compatible (use `.into_py(py)` for conversions)
- Use `petgraph` for service graph topology
- Use seeded RNG for reproducibility

### Tech Stack Requirements (Meta Hackathon)

This project is for a Meta hackathon. **Use Meta's own libraries:**

- **TorchRL** for RL training (not Stable Baselines or RLlib)
- **Llama 3** via Ollama (`llama3:8b-instruct-q4_K_M`) for LLM grading (not GPT/Claude)
- **PyTorch** (not JAX or TensorFlow)
- **ollama.chat()** for local inference (no API calls to external services)

### Windows-Specific Conventions

- Always use `.\.venv\Scripts\python.exe` not bare `python`
- Always use `.\.venv\Scripts\maturin.exe` for building
- If `os error 32` appears during build, Windows Defender exclusion is needed for the `target/` folder
- Use `python -m pytest` not bare `pytest`

### Git Workflow

- **Branch strategy:**
  - `main` — always runnable, merge at milestones only
  - `feat/track-a` — Person A's work (engine, env, rewards, graders)
  - `feat/track-b` — Person B's work (training, API, dashboard)
  
- **Commit message format:**
  ```
  [A] feat: description
  [B] fix: description
  [BOTH] chore: description
  ```

- **Critical:** Test locally before merging to `main`. A broken `main` blocks both tracks.

### Integration Sync Points

Before changing anything in `API_CONTRACT.md`:
1. Announce the change in your track file's "Messages for Person X" section
2. Wait for confirmation from the other person
3. Both make the change in the same commit if possible
4. Update `API_CONTRACT.md` after both sides are synced

The **observation shape (72,)** and **action space MultiDiscrete([12, 7])** were set at project start and should NOT change.

## Session Workflow

When starting a session:

1. **Ask which track** the user is working on (A or B)
2. **Read the relevant track file** (`trackA.md` or `trackB.md`) to understand current status
3. **Check for messages** from the other person in their track file
4. **Read `API_CONTRACT.md`** to understand the integration contract
5. **Summarize status** and suggest next steps

After completing meaningful tasks:
- Update the relevant track file (`trackA.md` or `trackB.md`)
- Mark completed tasks as `✅`
- Update progress bars
- Add blockers if any
- Leave messages for the other person if needed

## Documentation

- `AI_INSTRUCTIONS.md` — AI session bootstrap instructions
- `API_CONTRACT.md` — Integration contract between Track A and Track B
- `ARCHITECTURE.md` — System architecture and data flow
- `IMPLEMENTATION_PLAN.md` — Full task breakdown and timeline
- `GIT_WORKFLOW.md` — Git collaboration guide
- `DEMO_GUIDE.md` — Demo preparation and presentation guide
- `trackA.md` / `trackB.md` — Per-person progress tracking

## Demo Requirements

The demo must:
- Run **entirely offline** (no internet connection)
- Use Ollama for local Llama 3 inference
- Show live dashboard with service graph visualization
- Display the key metric: "Human SRE average: 4.2 hours | Agent: 4.3 seconds | Speedup: 3,527x"
