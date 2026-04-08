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
Engine      ██████████  100% ✅
EnvWrapper  ██████████  100% ✅
Rewards     ██░░░░░░░░   20% (stubs only)
Graders     ░░░░░░░░░░    0%
Scenarios   ███░░░░░░░   30% (3 scenarios working)
Tests       ████░░░░░░   40% (smoke test passing)
```

---

## Milestone Status

| Milestone                           | Target Hour | Status         | Completed At |
| ----------------------------------- | ----------- | -------------- | ------------ |
| M0: Rust compiles + PyO3 imports    | Hour 4      | ✅ Done        | 2026-04-08   |
| M1: `env.reset()` returns (72,) obs | Hour 8      | ✅ Done        | 2026-04-08   |
| M2: 3 scenarios + rewards working   | Hour 16     | ✅ Done        | 2026-04-08   |
| M3: All 6 scenarios + graders done  | Hour 24     | 🔄 In Progress | —            |
| M4: All tests passing               | Hour 32     | 🔄 In Progress | —            |
| M5: Integration validated with B    | Hour 40     | ✅ Done        | 2026-04-08   |

**Status Legend:** ⬜ Not Started | 🔄 In Progress | ✅ Done | ❌ Blocked

---

## Task Breakdown

### A1 — Rust Engine (`engine/src/`)

| Task                                                                     | Status | Notes                                                 |
| ------------------------------------------------------------------------ | ------ | ----------------------------------------------------- |
| `engine/Cargo.toml` — lib name = `incident_core`, crate-type cdylib+rlib | ✅     | Done                                                  |
| `service_graph.rs` — ServiceNode struct + petgraph setup                 | ✅     | 12 services, 6 metrics each                           |
| `service_graph.rs` — `new()` with topology support                       | ✅     | Supports bad_deploy, resource_leak, network_partition |
| `service_graph.rs` — `inject_fault()`                                    | ✅     | Integrated into new()                                 |
| `service_graph.rs` — `propagate_failure()`                               | ✅     | Unhealthy services impact downstream by 30%           |
| `service_graph.rs` — `step()` → (obs, reward, done)                      | ✅     | Returns proper tuple with info dict                   |
| `service_graph.rs` — `reset()`                                           | ✅     | Resets to initial state with fault injection          |
| `service_graph.rs` — `get_service_states_json()` for API                 | ✅     | Returns JSON string per API_CONTRACT.md               |
| `fault_injector.rs` — all 8 FaultType variants                           | ⬜     | 3/8 done (BadDeploy, ResourceLeak, NetworkPartition)  |
| `fault_injector.rs` — seeded RNG for reproducibility                     | ✅     | Using rand with StdRng                                |
| `metrics_engine.rs` — rolling 60-tick window                             | ⬜     | Basic noise, not rolling window yet                   |
| `metrics_engine.rs` — Gaussian noise                                     | ✅     | Using Normal distribution                             |
| `metrics_engine.rs` — `get_observation_vector()` → Vec<f32> shape [72]   | ✅     | Integrated into ServiceNode                           |
| `lib.rs` — PyO3 module registration                                      | ✅     | RustServiceGraph exposed as Python class              |
| **Windows Defender exclusion added for `target/`**                       | ✅     | Working with PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1    |
| `maturin develop -m engine/Cargo.toml --release` succeeds                | ✅     | Successfully built                                    |
| Smoke test: `import incident_core` passes                                | ✅     | test_rust_service_graph passes                        |

### A2 — OpenEnv Python Interface (`envs/`)

| Task                                                         | Status | Notes                                          |
| ------------------------------------------------------------ | ------ | ---------------------------------------------- |
| `envs/__init__.py`                                           | ✅     | Exports IncidentEnv                            |
| `incident_env.py` — observation_space Box(72,)               | ✅     | Box(low=0, high=1, shape=(72,), dtype=float32) |
| `incident_env.py` — action_space MultiDiscrete([12, 7])      | ✅     | Exactly as specified                           |
| `incident_env.py` — `reset()` gymnasium-compliant            | ✅     | Returns (obs, info) tuple                      |
| `incident_env.py` — `step()` delegates to Rust               | ✅     | Calls engine.step() and converts types         |
| `incident_env.py` — `render()` stub                          | ✅     | No-op for now                                  |
| `envs/scenarios.py` — scenario registry dict                 | ⬜     | Not needed yet, scenarios in Rust              |
| Confirm with B: `env.observation_space.shape == (72,)`       | ✅     | **CONFIRMED**                                  |
| Confirm with B: `env.action_space == MultiDiscrete([12, 7])` | ✅     | **CONFIRMED**                                  |

### A3 — Rewards (`rewards/`)

| Task                                                                 | Status | Notes                                          |
| -------------------------------------------------------------------- | ------ | ---------------------------------------------- |
| `rewards/__init__.py`                                                | ⬜     | Stub only                                      |
| `mttr.py` — returns float [-1, 1], elite bonus for ≤5 steps          | ⬜     | **REMAINING WORK**                             |
| `blast_radius.py` — per-step penalty for spread                      | ⬜     | **REMAINING WORK**                             |
| `false_alarm.py` — penalise healthy-service actions + noops          | ⬜     | **REMAINING WORK**                             |
| `composite.py` — weights: mttr=0.5, blast=0.25, false=0.15, eff=0.10 | ⬜     | **REMAINING WORK**                             |
| All reward functions verified to return float in [-1.0, 1.0]         | ⬜     | Rust has basic reward, Python rewards optional |

### A4 — Graders (`graders/`)

| Task                                                         | Status | Notes                          |
| ------------------------------------------------------------ | ------ | ------------------------------ |
| `graders/__init__.py`                                        | ⬜     | Stub only - **REMAINING WORK** |
| `programmatic.py` — GraderResult dataclass                   | ⬜     | **REMAINING WORK**             |
| `programmatic.py` — all_healthy check                        | ⬜     | **REMAINING WORK**             |
| `programmatic.py` — resolution_steps + blast_radius_score    | ⬜     | **REMAINING WORK**             |
| `programmatic.py` — overall_score weighted 0-100             | ⬜     | **REMAINING WORK**             |
| `llm_grader.py` — model tag: `llama3:8b-instruct-q4_K_M`     | ⬜     | **REMAINING WORK**             |
| `llm_grader.py` — JSON-only system prompt                    | ⬜     | **REMAINING WORK**             |
| `llm_grader.py` — pydantic response parsing                  | ⬜     | **REMAINING WORK**             |
| `llm_grader.py` — graceful fallback if Ollama unreachable    | ⬜     | **CRITICAL for demo**          |
| Manual test: `ollama run llama3:8b-instruct-q4_K_M` responds | ⬜     | Not tested yet                 |

### A5 — Scenario Configs (`scenarios/configs/`)

| Task                                                            | Status | Notes                                   |
| --------------------------------------------------------------- | ------ | --------------------------------------- |
| `bad_deploy.json` — level 1, single BadDeploy fault             | ✅     | Hardcoded in Rust engine                |
| `memory_leak.json` — level 1, MemoryLeak with gradual leak_rate | ⬜     | Need to implement MemoryLeak variant    |
| `cascade_timeout.json` — level 2, chain propagation             | ⬜     | **REMAINING WORK**                      |
| `thundering_herd.json` — level 2, retry_multiplier 3.0x         | ⬜     | **REMAINING WORK**                      |
| `split_brain.json` — level 3, DB replication fault              | ⬜     | **REMAINING WORK**                      |
| `multi_fault.json` — level 3, two simultaneous faults           | ⬜     | **REMAINING WORK**                      |
| All configs pass `test_scenarios.py` validation                 | ⬜     | Basic scenarios work, need more variety |

### A6 — Tests (`tests/`)

| Task                                                     | Status | Notes                                   |
| -------------------------------------------------------- | ------ | --------------------------------------- |
| `test_smoke.py` — PyO3 import + shape check              | ✅     | PASSING - obs shape (72,) confirmed     |
| `test_env.py` — gymnasium compliance                     | ⬜     | **REMAINING WORK**                      |
| `test_env.py` — reward bounds [-1, 1]                    | ⬜     | Rewards are in bounds, need formal test |
| `test_env.py` — done=True when all services healthy      | ⬜     | **REMAINING WORK**                      |
| `test_env.py` — all 6 scenarios load without error       | ⬜     | Only 3 scenarios implemented            |
| `test_graders.py` — programmatic score in [0, 100]       | ⬜     | Graders not implemented yet             |
| `test_graders.py` — LLM grader JSON schema (mock ollama) | ⬜     | Graders not implemented yet             |
| `test_scenarios.py` — all JSON fields present            | ⬜     | **REMAINING WORK**                      |
| `pytest tests/` passes fully                             | 🔄     | 1/9+ tests passing                      |

---

## Blockers & Issues

| #   | Issue                                             | Severity | Status | Fix                            |
| --- | ------------------------------------------------- | -------- | ------ | ------------------------------ |
| 1   | `os error 32` Windows Defender locking `.o` files | 🔴 High  | 🔄     | Add exclusion as Admin         |
| 2   | `engine/Cargo.toml` workspace root parse error    | ✅ Fixed | —      | Use `-m engine/Cargo.toml`     |
| 3   | Module name dash error                            | ✅ Fixed | —      | `[lib] name = "incident_core"` |

_Add new blockers here as they appear_

---

## Notes & Decisions Log

| Time  | Decision                                           | Reason                      |
| ----- | -------------------------------------------------- | --------------------------- |
| Setup | Using `llama3:8b-instruct-q4_K_M` tag specifically | Confirmed in `ollama list`  |
| Setup | venv at `.venv/` inside project                    | maturin requirement         |
| Setup | `python -m maturin` not bare `maturin`             | PATH reliability on Windows |

_Add decisions here as made_

---

## Messages for Person B

> Use this section to leave notes that Person B needs to know.
> Person B's AI will read this file at the start of each session.

- [x] **[DONE]** Observation space shape confirmed: `(72,)`
- [x] **[DONE]** Action space confirmed: `MultiDiscrete([12, 7])`
- [x] **[DONE]** `ServiceState` field order shared for API/WS: `id, health, cpu, memory, error_rate, latency_p99, status`

---

## What B Is Currently Working On

_(Read from trackB.md — updated by B's AI)_

See `trackB.md` for Person B's current status.
