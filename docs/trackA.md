# Track A — Progress Tracker
> Person A | IncidentEnv Hackathon | Last Updated: _auto-updated by AI_

---

## Identity
- **Track:** A — Simulation Engine, Environment & Graders
- **Owns:** `engine/`, `envs/`, `rewards/`, `graders/`, `scenarios/`, `tests/`
- **Dependency for Track B:** `IncidentEnv` gymnasium API + `incident_core` PyO3 module

---

## Overall Progress

```
Engine      ████████░░  0%
EnvWrapper  ░░░░░░░░░░  0%
Rewards     ░░░░░░░░░░  0%
Graders     ░░░░░░░░░░  0%
Scenarios   ░░░░░░░░░░  0%
Tests       ░░░░░░░░░░  0%
```

---

## Milestone Status

| Milestone | Target Hour | Status | Completed At |
|---|---|---|---|
| M0: Rust compiles + PyO3 imports | Hour 4 | ⬜ Not Started | — |
| M1: `env.reset()` returns (72,) obs | Hour 8 | ⬜ Not Started | — |
| M2: 3 scenarios + rewards working | Hour 16 | ⬜ Not Started | — |
| M3: All 6 scenarios + graders done | Hour 24 | ⬜ Not Started | — |
| M4: All tests passing | Hour 32 | ⬜ Not Started | — |
| M5: Integration validated with B | Hour 40 | ⬜ Not Started | — |

**Status Legend:** ⬜ Not Started | 🔄 In Progress | ✅ Done | ❌ Blocked

---

## Task Breakdown

### A1 — Rust Engine (`engine/src/`)

| Task | Status | Notes |
|---|---|---|
| `engine/Cargo.toml` — lib name = `incident_core`, crate-type cdylib+rlib | ⬜ | |
| `service_graph.rs` — ServiceNode struct + petgraph setup | ⬜ | |
| `service_graph.rs` — `new()` with topology support | ⬜ | |
| `service_graph.rs` — `inject_fault()` | ⬜ | |
| `service_graph.rs` — `propagate_failure()` | ⬜ | |
| `service_graph.rs` — `step()` → (obs, reward, done) | ⬜ | |
| `service_graph.rs` — `reset()` | ⬜ | |
| `service_graph.rs` — `get_service_states_json()` for API | ⬜ | |
| `fault_injector.rs` — all 8 FaultType variants | ⬜ | |
| `fault_injector.rs` — seeded RNG for reproducibility | ⬜ | |
| `metrics_engine.rs` — rolling 60-tick window | ⬜ | |
| `metrics_engine.rs` — Gaussian noise | ⬜ | |
| `metrics_engine.rs` — `get_observation_vector()` → Vec<f32> shape [72] | ⬜ | |
| `lib.rs` — PyO3 module registration | ⬜ | |
| **Windows Defender exclusion added for `target/`** | ⬜ | Run as Admin first! |
| `maturin develop -m engine/Cargo.toml --release` succeeds | ⬜ | |
| Smoke test: `import incident_core` passes | ⬜ | |

### A2 — OpenEnv Python Interface (`envs/`)

| Task | Status | Notes |
|---|---|---|
| `envs/__init__.py` | ⬜ | |
| `incident_env.py` — observation_space Box(72,) | ⬜ | |
| `incident_env.py` — action_space MultiDiscrete([12, 7]) | ⬜ | |
| `incident_env.py` — `reset()` gymnasium-compliant | ⬜ | |
| `incident_env.py` — `step()` delegates to Rust | ⬜ | |
| `incident_env.py` — `render()` stub | ⬜ | |
| `envs/scenarios.py` — scenario registry dict | ⬜ | |
| Confirm with B: `env.observation_space.shape == (72,)` | ⬜ | **SYNC POINT** |
| Confirm with B: `env.action_space == MultiDiscrete([12, 7])` | ⬜ | **SYNC POINT** |

### A3 — Rewards (`rewards/`)

| Task | Status | Notes |
|---|---|---|
| `rewards/__init__.py` | ⬜ | |
| `mttr.py` — returns float [-1, 1], elite bonus for ≤5 steps | ⬜ | |
| `blast_radius.py` — per-step penalty for spread | ⬜ | |
| `false_alarm.py` — penalise healthy-service actions + noops | ⬜ | |
| `composite.py` — weights: mttr=0.5, blast=0.25, false=0.15, eff=0.10 | ⬜ | |
| All reward functions verified to return float in [-1.0, 1.0] | ⬜ | |

### A4 — Graders (`graders/`)

| Task | Status | Notes |
|---|---|---|
| `graders/__init__.py` | ⬜ | |
| `programmatic.py` — GraderResult dataclass | ⬜ | |
| `programmatic.py` — all_healthy check | ⬜ | |
| `programmatic.py` — resolution_steps + blast_radius_score | ⬜ | |
| `programmatic.py` — overall_score weighted 0-100 | ⬜ | |
| `llm_grader.py` — model tag: `llama3:8b-instruct-q4_K_M` | ⬜ | exact tag from `ollama list` |
| `llm_grader.py` — JSON-only system prompt | ⬜ | |
| `llm_grader.py` — pydantic response parsing | ⬜ | |
| `llm_grader.py` — graceful fallback if Ollama unreachable | ⬜ | **CRITICAL for demo** |
| Manual test: `ollama run llama3:8b-instruct-q4_K_M` responds | ⬜ | |

### A5 — Scenario Configs (`scenarios/configs/`)

| Task | Status | Notes |
|---|---|---|
| `bad_deploy.json` — level 1, single BadDeploy fault | ⬜ | |
| `memory_leak.json` — level 1, MemoryLeak with gradual leak_rate | ⬜ | |
| `cascade_timeout.json` — level 2, chain propagation | ⬜ | |
| `thundering_herd.json` — level 2, retry_multiplier 3.0x | ⬜ | |
| `split_brain.json` — level 3, DB replication fault | ⬜ | |
| `multi_fault.json` — level 3, two simultaneous faults | ⬜ | |
| All configs pass `test_scenarios.py` validation | ⬜ | |

### A6 — Tests (`tests/`)

| Task | Status | Notes |
|---|---|---|
| `test_smoke.py` — PyO3 import + shape check | ⬜ | |
| `test_env.py` — gymnasium compliance | ⬜ | |
| `test_env.py` — reward bounds [-1, 1] | ⬜ | |
| `test_env.py` — done=True when all services healthy | ⬜ | |
| `test_env.py` — all 6 scenarios load without error | ⬜ | |
| `test_graders.py` — programmatic score in [0, 100] | ⬜ | |
| `test_graders.py` — LLM grader JSON schema (mock ollama) | ⬜ | |
| `test_scenarios.py` — all JSON fields present | ⬜ | |
| `pytest tests/` passes fully | ⬜ | |

---

## Blockers & Issues

| # | Issue | Severity | Status | Fix |
|---|---|---|---|---|
| 1 | `os error 32` Windows Defender locking `.o` files | 🔴 High | 🔄 | Add exclusion as Admin |
| 2 | `engine/Cargo.toml` workspace root parse error | ✅ Fixed | — | Use `-m engine/Cargo.toml` |
| 3 | Module name dash error | ✅ Fixed | — | `[lib] name = "incident_core"` |

_Add new blockers here as they appear_

---

## Notes & Decisions Log

| Time | Decision | Reason |
|---|---|---|
| Setup | Using `llama3:8b-instruct-q4_K_M` tag specifically | Confirmed in `ollama list` |
| Setup | venv at `.venv/` inside project | maturin requirement |
| Setup | `python -m maturin` not bare `maturin` | PATH reliability on Windows |

_Add decisions here as made_

---

## Messages for Person B

> Use this section to leave notes that Person B needs to know.
> Person B's AI will read this file at the start of each session.

- [ ] **[PENDING]** Confirm observation space shape once env is running — B needs `(72,)` confirmed before training
- [ ] **[PENDING]** Confirm action space `MultiDiscrete([12, 7])` before B builds actor network
- [ ] **[PENDING]** Share `ServiceState` field order for WebSocket integration with API

---

## What B Is Currently Working On
_(Read from trackB.md — updated by B's AI)_

See `trackB.md` for Person B's current status.
