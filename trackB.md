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
Training    ░░░░░░░░░░  0%
Curriculum  ░░░░░░░░░░  0%
Eval        ░░░░░░░░░░  0%
API Server  ░░░░░░░░░░  0%
Dashboard   ░░░░░░░░░░  0%
Integration ░░░░░░░░░░  0%
```

---

## Milestone Status

| Milestone                                        | Target Hour | Status         | Completed At |
| ------------------------------------------------ | ----------- | -------------- | ------------ |
| M0: Mock env + TorchRL PPO steps without crash   | Hour 4      | ⬜ Not Started | —            |
| M1: Real IncidentEnv connected to TorchRL        | Hour 16     | ⬜ Not Started | —            |
| M2: FastAPI + WebSocket serving EpisodeFrames    | Hour 16     | ⬜ Not Started | —            |
| M3: Dashboard renders live service graph from WS | Hour 24     | ⬜ Not Started | —            |
| M4: Trained checkpoint loaded in API + demo mode | Hour 36     | ⬜ Not Started | —            |
| M5: Full end-to-end demo works 3x in a row       | Hour 44     | ⬜ Not Started | —            |

**Status Legend:** ⬜ Not Started | 🔄 In Progress | ✅ Done | ❌ Blocked

---

## Task Breakdown

### B1 — Mock Environment (Unblock yourself from Track A)

> Start here before Track A's engine is ready. Build a stub env with correct API shape.

| Task                                                                                | Status | Notes                                    |
| ----------------------------------------------------------------------------------- | ------ | ---------------------------------------- |
| `tests/mock_env.py` — MockIncidentEnv with obs (72,) + action MultiDiscrete([12,7]) | ⬜     | Lets you build training before A is done |
| Verify MockEnv passes gymnasium compliance                                          | ⬜     |                                          |
| First TorchRL PPO step with MockEnv — no crash                                      | ⬜     |                                          |

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

| Task                                                            | Status | Notes |
| --------------------------------------------------------------- | ------ | ----- |
| `training/__init__.py`                                          | ⬜     |       |
| `train.py` — GymWrapper around IncidentEnv                      | ⬜     |       |
| `train.py` — Actor MLP (72 → 256 → 128 → action_dim)            | ⬜     |       |
| `train.py` — Critic MLP (72 → 256 → 128 → 1)                    | ⬜     |       |
| `train.py` — ProbabilisticActor with OneHotCategorical          | ⬜     |       |
| `train.py` — SyncDataCollector                                  | ⬜     |       |
| `train.py` — GAE advantage estimation                           | ⬜     |       |
| `train.py` — ClipPPOLoss (clip_epsilon=0.2)                     | ⬜     |       |
| `train.py` — Adam optimizer (lr=3e-4)                           | ⬜     |       |
| `train.py` — TensorBoard logging                                | ⬜     |       |
| `train.py` — checkpoint save every 100 epochs to `checkpoints/` | ⬜     |       |
| First training run on `bad_deploy` level 1 starts               | ⬜     |       |
| Agent achieves mean_reward > 0.5 on level 1                     | ⬜     |       |
| Curriculum advances from level 1 → 2                            | ⬜     |       |

### B3 — Curriculum Scheduler (`training/curriculum.py`)

| Task                                                    | Status | Notes |
| ------------------------------------------------------- | ------ | ----- |
| `CurriculumScheduler` class with 50-episode window      | ⬜     |       |
| Thresholds: L1=0.60, L2=0.65, L3=0.70, L4=0.75, L5=0.80 | ⬜     |       |
| `update(reward)` returns True on level advance          | ⬜     |       |
| Logs level transitions to console + TensorBoard         | ⬜     |       |
| Level resets reward window on advance                   | ⬜     |       |

### B4 — Evaluation Runner (`training/eval.py`)

| Task                                                                | Status | Notes |
| ------------------------------------------------------------------- | ------ | ----- |
| Load checkpoint from `checkpoints/`                                 | ⬜     |       |
| Run 100 episodes per scenario (600 total)                           | ⬜     |       |
| Collect: steps_to_resolution, blast_radius, false_positives, reward | ⬜     |       |
| Run programmatic grader on each episode                             | ⬜     |       |
| Run LLM grader on sample of episodes (10 per scenario)              | ⬜     |       |
| Output EvalReport as JSON + pretty table                            | ⬜     |       |
| `vs_human_baseline` string: "Agent: Xs \| Human: 4.2hr"             | ⬜     |       |

### B5 — FastAPI Server (`api/`)

| Task                                                        | Status | Notes                 |
| ----------------------------------------------------------- | ------ | --------------------- |
| `api/__init__.py`                                           | ⬜     |                       |
| `api/main.py` — FastAPI app init + CORS (localhost:5173)    | ⬜     |                       |
| `GET /health` endpoint                                      | ⬜     |                       |
| `GET /scenarios` endpoint                                   | ⬜     |                       |
| `POST /episode/start` — creates episode, returns episode_id | ⬜     |                       |
| `WS /episode/stream/{id}` — streams EpisodeFrame at 10fps   | ⬜     |                       |
| `POST /episode/stop/{id}`                                   | ⬜     |                       |
| `GET /episode/result/{id}` — final EvalReport               | ⬜     |                       |
| EpisodeFrame schema matches `API_CONTRACT.md`               | ⬜     | **SYNC POINT with A** |
| Server starts: `uvicorn api.main:app --reload --port 8000`  | ⬜     |                       |
| WebSocket test with `wscat` or browser                      | ⬜     |                       |
| Untrained agent mode (random policy) works                  | ⬜     |                       |
| Trained agent mode (PPO checkpoint) works                   | ⬜     |                       |

### B6 — Dashboard Config (`dashboard/`)

| Task                                                                    | Status | Notes                  |
| ----------------------------------------------------------------------- | ------ | ---------------------- |
| `dashboard/package.json` — react, d3, recharts, framer-motion, tailwind | ⬜     |                        |
| `dashboard/vite.config.js`                                              | ⬜     |                        |
| `dashboard/tailwind.config.js`                                          | ⬜     |                        |
| `dashboard/postcss.config.js`                                           | ⬜     |                        |
| `dashboard/index.html` — JetBrains Mono Google Font link                | ⬜     | **Don't forget font!** |
| `dashboard/src/main.jsx`                                                | ⬜     |                        |
| `dashboard/src/index.css` — CSS variables (dark terminal theme)         | ⬜     |                        |
| `npm install` completes                                                 | ⬜     |                        |
| `npm run dev` starts on port 5173                                       | ⬜     |                        |

### B7 — Dashboard Components (`dashboard/src/`)

| Task                                                                        | Status | Notes                                   |
| --------------------------------------------------------------------------- | ------ | --------------------------------------- |
| `hooks/useEpisodeStream.js` — WS lifecycle + reconnect backoff              | ⬜     | Build first, everything depends on this |
| `components/ServiceGraph.jsx` — D3 force graph renders 12 nodes             | ⬜     |                                         |
| `components/ServiceGraph.jsx` — node colors by health                       | ⬜     |                                         |
| `components/ServiceGraph.jsx` — pulse animation on Critical/Down            | ⬜     |                                         |
| `components/ServiceGraph.jsx` — hover tooltip with metrics                  | ⬜     |                                         |
| `components/ServiceGraph.jsx` — edges with dependency_strength weight       | ⬜     |                                         |
| `components/MetricsFeed.jsx` — error_rate AreaChart                         | ⬜     |                                         |
| `components/MetricsFeed.jsx` — latency LineChart (multi-series)             | ⬜     |                                         |
| `components/MetricsFeed.jsx` — CPU BarChart                                 | ⬜     |                                         |
| `components/AgentLog.jsx` — terminal-style scrolling log                    | ⬜     |                                         |
| `components/AgentLog.jsx` — auto-scroll to bottom                           | ⬜     |                                         |
| `components/AgentLog.jsx` — LLM reasoning box on episode end                | ⬜     |                                         |
| `components/ScoreCard.jsx` — CountUp animation                              | ⬜     |                                         |
| `components/ScoreCard.jsx` — human vs agent comparison line                 | ⬜     |                                         |
| `components/ScoreCard.jsx` — speedup multiplier calculation                 | ⬜     |                                         |
| `App.jsx` — grid layout (ServiceGraph + MetricsFeed + AgentLog + ScoreCard) | ⬜     |                                         |
| `App.jsx` — scenario dropdown                                               | ⬜     |                                         |
| `App.jsx` — untrained / trained toggle                                      | ⬜     |                                         |
| `App.jsx` — WS connection status indicator                                  | ⬜     |                                         |
| Full demo flow works end-to-end                                             | ⬜     |                                         |

---

## Blockers & Issues

| #   | Issue                                         | Severity  | Status | Fix                          |
| --- | --------------------------------------------- | --------- | ------ | ---------------------------- |
| 1   | Track A engine not ready — can't use real env | 🟡 Medium | 🔄     | Use MockIncidentEnv until M1 |

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

- [ ] **[PENDING]** Need `env.observation_space.shape == (72,)` confirmed — can't finalize actor network until then
- [ ] **[PENDING]** Need `get_service_states_json()` to return the exact schema in `API_CONTRACT.md` — API depends on it
- [ ] **[PENDING]** Need LLM grader to be callable from `api/main.py` — confirm `graders/` is importable as package

---

## What A Is Currently Working On

_(Read from trackA.md — updated by A's AI)_

See `trackA.md` for Person A's current status.
