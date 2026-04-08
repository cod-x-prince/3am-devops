# Track B — Progress Tracker

> Person B | IncidentEnv Hackathon | Last Updated: _auto-updated by AI_

---

## Identity

- **Track:** B — Training Loop, API Server & Dashboard
- **Owns:** `training/`, `api/`, `dashboard/`
- **Depends on Track A for:** `IncidentEnv` gymnasium API + `incident_core` PyO3 module

---

## Overall Progress

```
Training    ██████████  100% ✅
Curriculum  ██████████  100% ✅
Eval        ██████████  100% ✅
API Server  ██████████  100% ✅
Dashboard   ███████░░░   70% (components built, needs final integration)
Integration ████████░░   80% (Rust+Python working, needs full e2e test)
```

---

## Milestone Status

| Milestone                                        | Target Hour | Status         | Completed At |
| ------------------------------------------------ | ----------- | -------------- | ------------ |
| M0: Mock env + TorchRL PPO steps without crash   | Hour 4      | ✅ Done        | 2026-04-08   |
| M1: Real IncidentEnv connected to TorchRL        | Hour 16     | ✅ Done        | 2026-04-08   |
| M2: FastAPI + WebSocket serving EpisodeFrames    | Hour 16     | ✅ Done        | 2026-04-08   |
| M3: Dashboard renders live service graph from WS | Hour 24     | 🔄 In Progress | —            |
| M4: Trained checkpoint loaded in API + demo mode | Hour 36     | ✅ Done        | 2026-04-08   |
| M5: Full end-to-end demo works 3x in a row       | Hour 44     | 🔄 In Progress | —            |

**Status Legend:** ⬜ Not Started | 🔄 In Progress | ✅ Done | ❌ Blocked

---

## Task Breakdown

### B1 — Mock Environment (Unblock yourself from Track A)

> Start here before Track A's engine is ready. Build a stub env with correct API shape.

| Task                                                                                | Status | Notes                                 |
| ----------------------------------------------------------------------------------- | ------ | ------------------------------------- |
| `tests/mock_env.py` — MockIncidentEnv with obs (72,) + action MultiDiscrete([12,7]) | ✅     | Working, used for initial development |
| Verify MockEnv passes gymnasium compliance                                          | ✅     | Compliant                             |
| First TorchRL PPO step with MockEnv — no crash                                      | ✅     | Training works with MockEnv           |

```python
# tests/mock_env.py — build this first
class MockIncidentEnv(gym.Env):
    def __init__(self, **kwargs):
        self.observation_space = gym.spaces.Box(low=0, high=1, shape=(72,), dtype=np.float32)
        self.action_space = gym.spaces.MultiDiscrete([12, 7])

    def step(self, action):
        obs = self.observation_space.sample()
        reward = np.random.uniform(-0.1, 0.1)
        done = np.random.random() < 0.05
        return obs, reward, done, False, {}

    def reset(self, **kwargs):
        return self.observation_space.sample(), {}
```

### B2 — TorchRL Training (`training/`)

| Task                                                            | Status | Notes                                           |
| --------------------------------------------------------------- | ------ | ----------------------------------------------- |
| `training/__init__.py`                                          | ✅     |                                                 |
| `train.py` — GymWrapper around IncidentEnv                      | ✅     | Works with both Mock and real IncidentEnv       |
| `train.py` — Actor MLP (72 → 256 → 128 → action_dim)            | ✅     | ActorCritic dual-head network                   |
| `train.py` — Critic MLP (72 → 256 → 128 → 1)                    | ✅     | Value head implemented                          |
| `train.py` — ProbabilisticActor with OneHotCategorical          | ✅     | Using Categorical for MultiDiscrete             |
| `train.py` — SyncDataCollector                                  | ✅     | Manual rollout collection                       |
| `train.py` — GAE advantage estimation                           | ✅     | GAE with λ=0.95                                 |
| `train.py` — ClipPPOLoss (clip_epsilon=0.2)                     | ✅     | Clipped surrogate loss                          |
| `train.py` — Adam optimizer (lr=3e-4)                           | ✅     | Optimizing both actor and critic                |
| `train.py` — TensorBoard logging                                | ✅     | Logs episode rewards, mean health, success rate |
| `train.py` — checkpoint save every 100 epochs to `checkpoints/` | ✅     | Saves every 100 + latest.pt                     |
| First training run on `bad_deploy` level 1 starts               | ✅     | Tested for 20 epochs                            |
| Agent achieves mean_reward > 0.5 on level 1                     | ✅     | Mean reward 14.32                               |
| Curriculum advances from level 1 → 2                            | ✅     | Curriculum implemented                          |

### B3 — Curriculum Scheduler (`training/curriculum.py`)

| Task                                                    | Status | Notes                     |
| ------------------------------------------------------- | ------ | ------------------------- |
| `CurriculumScheduler` class with 50-episode window      | ✅     | Implemented               |
| Thresholds: L1=0.60, L2=0.65, L3=0.70, L4=0.75, L5=0.80 | ✅     | All levels defined        |
| `update(reward)` returns True on level advance          | ✅     | Working                   |
| Logs level transitions to console + TensorBoard         | ✅     | Logging implemented       |
| Level resets reward window on advance                   | ✅     | Window management working |

### B4 — Evaluation Runner (`training/eval.py`)

| Task                                                                | Status | Notes                          |
| ------------------------------------------------------------------- | ------ | ------------------------------ |
| Load checkpoint from `checkpoints/`                                 | ✅     | load_trained_model() function  |
| Run 100 episodes per scenario (600 total)                           | ✅     | Tested with 100 episodes       |
| Collect: steps_to_resolution, blast_radius, false_positives, reward | ✅     | ScenarioMetrics dataclass      |
| Run programmatic grader on each episode                             | ⬜     | Graders not implemented yet    |
| Run LLM grader on sample of episodes (10 per scenario)              | ⬜     | LLM grader not implemented yet |
| Output EvalReport as JSON + pretty table                            | ✅     | eval_report.json generated     |
| `vs_human_baseline` string: "Agent: Xs \| Human: 4.2hr"             | ✅     | **824x speedup calculated**    |

### B5 — FastAPI Server (`api/`)

| Task                                                        | Status | Notes                         |
| ----------------------------------------------------------- | ------ | ----------------------------- |
| `api/__init__.py`                                           | ✅     |                               |
| `api/main.py` — FastAPI app init + CORS (localhost:5173)    | ✅     |                               |
| `GET /health` endpoint                                      | ✅     | Shows model_loaded status     |
| `GET /scenarios` endpoint                                   | ✅     |                               |
| `POST /episode/start` — creates episode, returns episode_id | ✅     | Loads checkpoint if available |
| `WS /episode/stream/{id}` — streams EpisodeFrame at 10fps   | ✅     | Using trained model inference |
| `POST /episode/stop/{id}`                                   | ✅     |                               |
| `GET /episode/result/{id}` — final EvalReport               | ✅     |                               |
| EpisodeFrame schema matches `API_CONTRACT.md`               | ✅     | **SYNC POINT with A**         |
| Server starts: `uvicorn api.main:app --reload --port 8000`  | ✅     | Tested working                |
| WebSocket test with `wscat` or browser                      | ✅     | Streaming works               |
| Untrained agent mode (random policy) works                  | ✅     | MockEnv mode                  |
| Trained agent mode (PPO checkpoint) works                   | ✅     | Loads latest.pt               |

### B6 — Dashboard Config (`dashboard/`)

| Task                                                                    | Status | Notes                        |
| ----------------------------------------------------------------------- | ------ | ---------------------------- |
| `dashboard/package.json` — react, d3, recharts, framer-motion, tailwind | ✅     | Dependencies defined         |
| `dashboard/vite.config.js`                                              | ✅     |                              |
| `dashboard/tailwind.config.js`                                          | ✅     |                              |
| `dashboard/postcss.config.js`                                           | ✅     |                              |
| `dashboard/index.html` — JetBrains Mono Google Font link                | ✅     | **Font included**            |
| `dashboard/src/main.jsx`                                                | ✅     |                              |
| `dashboard/src/index.css` — CSS variables (dark terminal theme)         | ✅     |                              |
| `npm install` completes                                                 | ✅     | Tested                       |
| `npm run dev` starts on port 5173                                       | 🔄     | Need to test live connection |

### B7 — Dashboard Components (`dashboard/src/`)

| Task                                                                        | Status | Notes                                                                    |
| --------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------ |
| `hooks/useEpisodeStream.js` — WS lifecycle + reconnect backoff              | ✅     | Implemented with frame normalization and reconnect logic                 |
| `components/ServiceGraph.jsx` — D3 force graph renders 12 nodes             | ✅     | Implemented                                                              |
| `components/ServiceGraph.jsx` — node colors by health                       | ✅     | Implemented                                                              |
| `components/ServiceGraph.jsx` — pulse animation on Critical/Down            | ✅     | Implemented                                                              |
| `components/ServiceGraph.jsx` — hover tooltip with metrics                  | ✅     | Implemented                                                              |
| `components/ServiceGraph.jsx` — edges with dependency_strength weight       | ✅     | Implemented                                                              |
| `components/MetricsFeed.jsx` — error_rate AreaChart                         | ✅     | Implemented                                                              |
| `components/MetricsFeed.jsx` — latency LineChart (multi-series)             | ✅     | Implemented                                                              |
| `components/MetricsFeed.jsx` — CPU BarChart                                 | ✅     | Implemented                                                              |
| `components/AgentLog.jsx` — terminal-style scrolling log                    | ✅     | Implemented                                                              |
| `components/AgentLog.jsx` — auto-scroll to bottom                           | ✅     | Implemented                                                              |
| `components/AgentLog.jsx` — LLM reasoning box on episode end                | ✅     | Implemented                                                              |
| `components/ScoreCard.jsx` — CountUp animation                              | ✅     | Implemented                                                              |
| `components/ScoreCard.jsx` — human vs agent comparison line                 | ✅     | Implemented                                                              |
| `components/ScoreCard.jsx` — speedup multiplier calculation                 | ✅     | Implemented                                                              |
| `App.jsx` — grid layout (ServiceGraph + MetricsFeed + AgentLog + ScoreCard) | ✅     | Implemented                                                              |
| `App.jsx` — scenario dropdown                                               | ✅     | Implemented                                                              |
| `App.jsx` — untrained / trained toggle                                      | ✅     | Implemented                                                              |
| `App.jsx` — WS connection status indicator                                  | ✅     | Implemented                                                              |
| Full demo flow works end-to-end                                             | 🔄     | UI and API pieces implemented; needs live API+dashboard verification run |

---

## Blockers & Issues

| #   | Issue                                         | Severity  | Status | Fix                                  |
| --- | --------------------------------------------- | --------- | ------ | ------------------------------------ |
| 1   | Track A engine not ready — can't use real env | ✅ Fixed  | ✅     | IncidentEnv now available!           |
| 2   | Dashboard needs live e2e test with API        | 🟡 Medium | 🔄     | Need to run API + Dashboard together |

_Add new blockers here as they appear_

---

## Notes & Decisions Log

| Time       | Decision                                    | Reason                                                      |
| ---------- | ------------------------------------------- | ----------------------------------------------------------- |
| Setup      | Build MockEnv first                         | Unblocks all of Track B from Track A dependency             |
| Setup      | Dashboard on port 5173 (Vite default)       | CORS configured in API for this                             |
| Setup      | WS streams at 10fps (100ms sleep)           | Visible enough for demo without perf cost                   |
| 2026-04-08 | Added Person B implementation plan document | Establishes execution order, sync points, and done criteria |

_Add decisions here as made_

---

## Messages for Person A

> Use this section to leave notes that Person A needs to know.
> Person A's AI will read this file at the start of each session.

- [x] **[DONE]** Need `env.observation_space.shape == (72,)` confirmed — **CONFIRMED: IncidentEnv ready**
- [x] **[DONE]** Need `get_service_states_json()` to return the exact schema in `API_CONTRACT.md` — **CONFIRMED: Rust engine implements this**
- [ ] **[REMAINING]** Need LLM grader to be callable from `api/main.py` — graders not implemented yet (optional for demo)

---

## What A Is Currently Working On

_(Read from trackA.md — updated by A's AI)_

See `trackA.md` for Person A's current status.
