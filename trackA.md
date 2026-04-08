# Track A - Progress Tracker

> Person A | IncidentEnv Hackathon | Last Updated: 2026-04-08

---

## Identity

- **Track:** A - Simulation Engine, Env Wrapper, Rewards, Graders
- **Owns:** `engine/`, `envs/`, `rewards/`, `graders/`, `scenarios/`, `tests/`
- **Integration contract:** observation `(72,)`, action `MultiDiscrete([12, 7])`

---

## Overall Progress

```
Engine      [##########] 100% DONE
EnvWrapper  [##########] 100% DONE
Rewards     [##########] 100% DONE
Graders     [##########] 100% DONE
Scenarios   [##########] 100% DONE (submission set)
Tests        [##########] 100% DONE
```

---

## Submission-Critical Status

| Area | Status | Notes |
| --- | --- | --- |
| Rust/Python env runtime | DONE | Gym-compatible `IncidentEnv` plus typed OpenEnv adapter |
| Typed OpenEnv models | DONE | `ObservationModel`, `ActionModel`, `RewardModel` |
| Reward shaping | DONE | Partial-progress rewards + penalties, bounded to `[-1, 1]` |
| Tasks + deterministic grading | DONE | Easy/medium/hard tasks scored in `[0, 1]` |
| API contract compatibility | DONE | Observation/action contract preserved for Track B |
| Tests | DONE | `pytest` suite passing locally |

---

## Key Completed Items

- `envs/openenv_models.py` and `envs/openenv_env.py` added and wired.
- `envs/incident_env.py` upgraded for scenario differentiation and shaped rewards.
- `rewards/` modules (`mttr`, `blast_radius`, `false_alarm`, `composite`) implemented and bounded.
- `graders/programmatic.py` normalized grading path exposed for task scoring.
- Scenario configs present for submission flows (`bad_deploy`, `cascade_timeout`, `split_brain`, `thundering_herd`, `multi_fault`).
- Reward/task coverage tests added (`tests/test_rewards.py`) and passing.

---

## Blockers

- None.

---

## Messages for Person B

- [DONE] Contract is stable: obs `(72,)`, action `MultiDiscrete([12, 7])`.
- [DONE] Typed OpenEnv wrapper is in place and exposed.
- [DONE] No Track A blockers for submission handoff.
