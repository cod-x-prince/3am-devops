# IncidentEnv — Architecture Reference

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INCIDENT ENV                                │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    TRACK A (Person A)                        │  │
│  │                                                              │  │
│  │  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │  │
│  │  │ Rust Engine │    │ OpenEnv      │    │  Rewards +    │  │  │
│  │  │ (PyO3)      │───▶│ Python Wrap  │───▶│  Graders      │  │  │
│  │  │             │    │              │    │               │  │  │
│  │  │ service_    │    │ incident_    │    │ composite.py  │  │  │
│  │  │ graph.rs    │    │ env.py       │    │ llm_grader.py │  │  │
│  │  │ fault_      │    │ scenarios.py │    │ programmatic  │  │  │
│  │  │ injector.rs │    │              │    │               │  │  │
│  │  │ metrics_    │    │ obs: (72,)   │    │ Llama 3 via   │  │  │
│  │  │ engine.rs   │    │ act: MD[12,7]│    │ Ollama local  │  │  │
│  │  └─────────────┘    └──────────────┘    └───────────────┘  │  │
│  │                                                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           │                                         │
│                    API_CONTRACT.md                                  │
│                    obs(72,) + action                                │
│                           │                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    TRACK B (Person B)                        │  │
│  │                                                              │  │
│  │  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │  │
│  │  │  TorchRL    │    │  FastAPI     │    │  React +      │  │  │
│  │  │  PPO Agent  │───▶│  WebSocket   │───▶│  D3 Dashboard │  │  │
│  │  │             │    │  Server      │    │               │  │  │
│  │  │ train.py    │    │ api/main.py  │    │ ServiceGraph  │  │  │
│  │  │ curriculum  │    │ port: 8000   │    │ MetricsFeed   │  │  │
│  │  │ eval.py     │    │              │    │ AgentLog      │  │  │
│  │  │             │    │ EpisodeFrame │    │ ScoreCard     │  │  │
│  │  │ checkpoints/│    │ streams JSON │    │ port: 5173    │  │  │
│  │  └─────────────┘    └──────────────┘    └───────────────┘  │  │
│  │                                                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
1. Rust Engine generates service graph state (sub-millisecond)
        │
        ▼
2. Python IncidentEnv wraps state as obs (72,) numpy array
        │
        ▼
3. TorchRL PPO Agent receives obs → outputs action MultiDiscrete([12,7])
        │
        ▼
4. IncidentEnv.step(action) → Rust engine applies action → new state
        │
        ├──▶ reward computed by composite.py
        ├──▶ info["services_json"] produced for API
        └──▶ terminated check (all services healthy?)
                │
                ▼
5. FastAPI receives info → broadcasts EpisodeFrame via WebSocket
        │
        ▼
6. React Dashboard renders:
        ├──▶ D3 ServiceGraph (node colors update)
        ├──▶ Recharts MetricsFeed (charts update)
        ├──▶ AgentLog (action appended)
        └──▶ ScoreCard (reward + MTTR update)
                │
                ▼ (when done=True)
7. LLM Grader (Llama 3 local) evaluates episode
        │
        ▼
8. Final score shown in dashboard + LLM reasoning displayed
```

## Performance Architecture

```
Python training loop
├── env.step() calls PyO3 → Rust
│   └── ~0.1ms per step (100x faster than pure Python)
├── Torch tensor ops (GPU if available, CPU fallback)
└── Target: >10,000 env steps/second for training
```

## Port Map

| Service | Port | Started By |
|---|---|---|
| FastAPI API server | 8000 | `uvicorn api.main:app --reload` |
| Vite dev dashboard | 5173 | `npm run dev` (in dashboard/) |
| Ollama inference | 11434 | `ollama serve` (auto-starts) |
| TensorBoard | 6006 | `tensorboard --logdir logs/` |

## Directory Map

```
incident-env/
├── engine/                   # Track A: Rust simulation core
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs
│       ├── service_graph.rs
│       ├── fault_injector.rs
│       └── metrics_engine.rs
├── envs/                     # Track A: OpenEnv Python interface
│   ├── __init__.py
│   ├── incident_env.py
│   └── scenarios.py
├── rewards/                  # Track A: Reward functions
│   ├── __init__.py
│   ├── mttr.py
│   ├── blast_radius.py
│   ├── false_alarm.py
│   └── composite.py
├── graders/                  # Track A: Evaluation graders
│   ├── __init__.py
│   ├── programmatic.py
│   └── llm_grader.py
├── scenarios/                # Track A: Scenario configs
│   └── configs/
│       ├── bad_deploy.json
│       ├── memory_leak.json
│       ├── cascade_timeout.json
│       ├── thundering_herd.json
│       ├── split_brain.json
│       └── multi_fault.json
├── training/                 # Track B: RL training
│   ├── __init__.py
│   ├── train.py
│   ├── curriculum.py
│   └── eval.py
├── api/                      # Track B: FastAPI server
│   ├── __init__.py
│   └── main.py
├── dashboard/                # Track B: React dashboard
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── index.css
│       ├── App.jsx
│       ├── components/
│       │   ├── ServiceGraph.jsx
│       │   ├── MetricsFeed.jsx
│       │   ├── AgentLog.jsx
│       │   └── ScoreCard.jsx
│       └── hooks/
│           └── useEpisodeStream.js
├── tests/                    # Both tracks
│   ├── mock_env.py           # Track B (unblocking stub)
│   ├── test_smoke.py         # Track A
│   ├── test_env.py           # Track A
│   ├── test_graders.py       # Track A
│   └── test_scenarios.py     # Track A
├── checkpoints/              # Track B: Saved model weights (gitignored)
├── logs/                     # Track B: TensorBoard logs (gitignored)
├── Cargo.toml                # Rust workspace
├── pyproject.toml            # Python project
├── bootstrap.ps1             # Windows setup script
├── Makefile                  # Unix/WSL setup script
├── .env                      # Secrets (gitignored)
├── .github/
│   └── copilot-instructions.md
├── IMPLEMENTATION_PLAN.md    # This project's master plan
├── API_CONTRACT.md           # Integration agreement A↔B
├── ARCHITECTURE.md           # This file
├── AI_INSTRUCTIONS.md        # AI session bootstrap
├── trackA.md                 # Person A progress
└── trackB.md                 # Person B progress
```
