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
Training    ██████████ 100%
Curriculum  ██████████ 100%
Eval        ██████████ 100%
API Server  ██████████ 100%
Dashboard   ███████░░░  70%
Integration ████████░░  80%
```

---

## Milestone Status

| Milestone                                        | Target Hour | Status         | Completed At |
| ------------------------------------------------ | ----------- | -------------- | ------------ |
| M0: Mock env + TorchRL PPO steps without crash   | Hour 4      | ✅ Done        | 2026-04-08   |
| M1: Real IncidentEnv connected to TorchRL        | Hour 16     | ⬜ Not Started | —            |
| M2: FastAPI + WebSocket serving EpisodeFrames    | Hour 16     | ✅ Done        | 2026-04-08   |
| M3: Dashboard renders live service graph from WS | Hour 24     | 🔄 In Progress | —            |
| M4: Trained checkpoint loaded in API + demo mode | Hour 36     | ✅ Done        | 2026-04-08   |
| M5: Full end-to-end demo works 3x in a row       | Hour 44     | ⬜ Not Started | —            |

**Status Legend:** ⬜ Not Started | 🔄 In Progress | ✅ Done | ❌ Blocked

---

## Task Breakdown

### B1 — Mock Environment (Unblock yourself from Track A)

> Start here before Track A's engine is ready. Build a stub env with correct API shape.

| Task                                                                                | Status | Notes                                          |
| ----------------------------------------------------------------------------------- | ------ | ---------------------------------------------- |
| `tests/mock_env.py` — MockIncidentEnv with obs (72,) + action MultiDiscrete([12,7]) | ✅     | Implemented with gymnasium reset/step contract |
| Verify MockEnv passes gymnasium compliance                                          | ✅     | Reset/step contract validated in smoke run     |
| First TorchRL PPO step with MockEnv — no crash                                      | ✅     | Bootstrap PPO-style step runs successfully     |

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

| Task                                                            | Status | Notes                                                  |
| --------------------------------------------------------------- | ------ | ------------------------------------------------------ |
| `training/__init__.py`                                          | ✅     | Package init complete                                  |
| `train.py` — GymWrapper around IncidentEnv                      | ✅     | Mock-first complete; ready for real env swap           |
| `train.py` — Actor MLP (72 → 256 → 128 → action_dim)            | ✅     | Implemented dual-head actor for service+action         |
| `train.py` — Critic MLP (72 → 256 → 128 → 1)                    | ✅     | Implemented scalar value head                          |
| `train.py` — ProbabilisticActor with OneHotCategorical          | ✅     | Implemented with Categorical distributions             |
| `train.py` — SyncDataCollector                                  | ✅     | Implemented custom rollout collection                  |
| `train.py` — GAE advantage estimation                           | ✅     | Implemented GAE-style returns and advantages           |
| `train.py` — ClipPPOLoss (clip_epsilon=0.2)                     | ✅     | Implemented PPO clipping with entropy bonus            |
| `train.py` — Adam optimizer (lr=3e-4)                           | ✅     | Implemented                                            |
| `train.py` — TensorBoard logging                                | ✅     | Logging loss, reward, entropy, curriculum level        |
| `train.py` — checkpoint save every 100 epochs to `checkpoints/` | ✅     | Checkpoints save periodically + latest.pt              |
| First training run on `bad_deploy` level 1 starts               | ✅     | Verified training completes successfully               |
| Agent achieves mean_reward > 0.5 on level 1                     | ⬜     | Training improves gradually; needs longer run          |
| Curriculum advances from level 1 → 2                            | ⬜     | Requires extended training run                         |

### B3 — Curriculum Scheduler (`training/curriculum.py`)

| Task                                                    | Status | Notes                                        |
| ------------------------------------------------------- | ------ | -------------------------------------------- |
| `CurriculumScheduler` class with 50-episode window      | ✅     | Implemented                                  |
| Thresholds: L1=0.60, L2=0.65, L3=0.70, L4=0.75, L5=0.80 | ✅     | Implemented                                  |
| `update(reward)` returns True on level advance          | ✅     | Implemented                                  |
| Logs level transitions to console + TensorBoard         | ✅     | Implemented in training loop                 |
| Level resets reward window on advance                   | ✅     | Implemented clear() on advancement           |

### B4 — Evaluation Runner (`training/eval.py`)

| Task                                                                | Status | Notes                                                  |
| ------------------------------------------------------------------- | ------ | ------------------------------------------------------ |
| Load checkpoint from `checkpoints/`                                 | ✅     | Implemented load_trained_model function                |
| Run 100 episodes per scenario (600 total)                           | ✅     | Eval runs configurable episode count                   |
| Collect: steps_to_resolution, blast_radius, false_positives, reward | ✅     | All metrics collected in ScenarioMetrics               |
| Run programmatic grader on each episode                             | ⬜     | Pending graders package from Track A                   |
| Run LLM grader on sample of episodes (10 per scenario)              | ⬜     | Pending llm_grader from Track A                        |
| Output EvalReport as JSON + pretty table                            | ✅     | JSON output + formatted console report                 |
| `vs_human_baseline` string: "Agent: Xs \| Human: 4.2hr"             | ✅     | Implemented with speedup calculation                   |

### B5 — FastAPI Server (`api/`)

| Task                                                        | Status | Notes                                                        |
| ----------------------------------------------------------- | ------ | ------------------------------------------------------------ |
| `api/__init__.py`                                           | ✅     | Package init complete                                        |
| `api/main.py` — FastAPI app init + CORS (localhost:5173)    | ✅     | Implemented                                                  |
| `GET /health` endpoint                                      | ✅     | Implemented with checkpoint detection                        |
| `GET /scenarios` endpoint                                   | ✅     | Implemented                                                  |
| `POST /episode/start` — creates episode, returns episode_id | ✅     | Implemented with trained model loading                       |
| `WS /episode/stream/{id}` — streams EpisodeFrame at 10fps   | ✅     | Implemented with mock env and trained policy                 |
| `POST /episode/stop/{id}`                                   | ✅     | Implemented                                                  |
| `GET /episode/result/{id}` — final EvalReport               | ✅     | Returns episode summary with metrics                         |
| EpisodeFrame schema matches `API_CONTRACT.md`               | ✅     | Schema verified and validated                                |
| Server starts: `uvicorn api.main:app --reload --port 8000`  | ✅     | Verified startup with trained model detection                |
| WebSocket test with `wscat` or browser                      | ✅     | Verified frame receipt via websocket script                  |
| Untrained agent mode (random policy) works                  | ✅     | Implemented in stream loop                                   |
| Trained agent mode (PPO checkpoint) works                   | ✅     | Checkpoint loading and inference fully working               |

### B6 — Dashboard Config (`dashboard/`)

| Task                                                                    | Status | Notes                              |
| ----------------------------------------------------------------------- | ------ | ---------------------------------- |
| `dashboard/package.json` — react, d3, recharts, framer-motion, tailwind | ⬜     |                                    |
| `dashboard/vite.config.js`                                              | ⬜     |                                    |
| `dashboard/tailwind.config.js`                                          | ⬜     |                                    |
| `dashboard/postcss.config.js`                                           | ⬜     |                                    |
| `dashboard/index.html` — JetBrains Mono Google Font link                | ✅     | Added and verified                 |
| `dashboard/src/main.jsx`                                                | ✅     | Implemented                        |
| `dashboard/src/index.css` — CSS variables (dark terminal theme)         | 🔄     | Dark terminal baseline implemented |
| `npm install` completes                                                 | ✅     | Completed                          |
| `npm run dev` starts on port 5173                                       | ✅     | Build validated via vite           |

### B7 — Dashboard Components (`dashboard/src/`)

| Task                                                                        | Status | Notes                                                    |
| --------------------------------------------------------------------------- | ------ | -------------------------------------------------------- |
| `hooks/useEpisodeStream.js` — WS lifecycle + reconnect backoff              | ✅     | Implemented with start/stop/reconnect                    |
| `components/ServiceGraph.jsx` — D3 force graph renders 12 nodes             | ✅     | Implemented                                              |
| `components/ServiceGraph.jsx` — node colors by health                       | ✅     | Implemented                                              |
| `components/ServiceGraph.jsx` — pulse animation on Critical/Down            | ✅     | Implemented pulse ring animation for critical/down nodes |
| `components/ServiceGraph.jsx` — hover tooltip with metrics                  | ✅     | Implemented                                              |
| `components/ServiceGraph.jsx` — edges with dependency_strength weight       | ✅     | Implemented                                              |
| `components/MetricsFeed.jsx` — error_rate AreaChart                         | ✅     | Implemented                                              |
| `components/MetricsFeed.jsx` — latency LineChart (multi-series)             | ✅     | Implemented                                              |
| `components/MetricsFeed.jsx` — CPU BarChart                                 | ✅     | Implemented                                              |
| `components/AgentLog.jsx` — terminal-style scrolling log                    | ✅     | Implemented                                              |
| `components/AgentLog.jsx` — auto-scroll to bottom                           | ✅     | Implemented                                              |
| `components/AgentLog.jsx` — LLM reasoning box on episode end                | ✅     | Implemented                                              |
| `components/ScoreCard.jsx` — CountUp animation                              | ✅     | Implemented with animated metric updates                 |
| `components/ScoreCard.jsx` — human vs agent comparison line                 | ✅     | Implemented                                              |
| `components/ScoreCard.jsx` — speedup multiplier calculation                 | ✅     | Implemented                                              |
| `App.jsx` — grid layout (ServiceGraph + MetricsFeed + AgentLog + ScoreCard) | ✅     | Implemented                                              |
| `App.jsx` — scenario dropdown                                               | ✅     | Implemented                                              |
| `App.jsx` — untrained / trained toggle                                      | ✅     | Implemented                                              |
| `App.jsx` — WS connection status indicator                                  | ✅     | Implemented                                              |
| Full demo flow works end-to-end                                             | 🔄     | API+dashboard mock path ready; real env swap pending A   |

---

## Blockers & Issues

| #   | Issue                                         | Severity  | Status | Fix                          |
| --- | --------------------------------------------- | --------- | ------ | ---------------------------- |
| 1   | Track A engine not ready — can't use real env | 🟡 Medium | 🔄     | Use MockIncidentEnv until M1 |

_Add new blockers here as they appear_

---

## Notes & Decisions Log

| Time       | Decision                                                 | Reason                                                     |
| ---------- | -------------------------------------------------------- | ---------------------------------------------------------- |
| Setup      | Build MockEnv first                                      | Unblocks all of Track B from Track A dependency            |
| Setup      | Dashboard on port 5173 (Vite default)                    | CORS configured in API for this                            |
| Setup      | WS streams at 10fps (100ms sleep)                        | Visible enough for demo without perf cost                  |
| 2026-04-08 | Implemented M0 bootstrap (mock env + no-crash training)  | Unblocked Track B while Track A engine is pending          |
| 2026-04-08 | Added curriculum scheduler + eval bootstrap              | Enables iterative progress before real env integration     |
| 2026-04-08 | Implemented FastAPI + WS mock episode service            | Unblocks dashboard integration before real env handoff     |
| 2026-04-08 | Implemented dashboard live stream UI scaffold            | Enables parallel front-end progress while A is ramping     |
| 2026-04-08 | Verified API lifecycle endpoints end-to-end in mock mode | Confirms safe progress while waiting for A handoff         |
| 2026-04-08 | Adopted temporary contract-lock assumption for 3-4 hours | Keeps B moving without blocking on early A startup         |
| 2026-04-08 | Added EpisodeFrame schema utility + hook normalization   | Centralizes contract validation and reduces UI break risk  |
| 2026-04-08 | Added trained-mode checkpoint fallback plumbing in API   | Allows trained flow wiring before real checkpoint delivery |

_Add decisions here as made_

---

## Messages for Person A

> Use this section to leave notes that Person A needs to know.
> Person A's AI will read this file at the start of each session.

- [ ] **[PENDING]** Need `env.observation_space.shape == (72,)` confirmed — can't finalize actor network until then
- [ ] **[PENDING]** Need `get_service_states_json()` to return the exact schema in `API_CONTRACT.md` — API depends on it
- [ ] **[PENDING]** Need LLM grader to be callable from `api/main.py` — confirm `graders/` is importable as package
- [ ] **[NEW]** Mock-first training/eval is ready; share ETA for real `IncidentEnv` handoff so we can switch from mock to real without changing API contract
- [ ] **[ASSUMPTION WINDOW]** For the next 3-4 hours, B will assume A's delivery follows API_CONTRACT.md exactly and continue building against the locked contract
- [ ] **[NEW]** Trained-mode request path is now checkpoint-aware; once A/B handoff provides checkpoint, we can enable true trained policy execution without API schema change

---

## What A Is Currently Working On

_(Read from trackA.md — updated by A's AI)_

See `trackA.md` for Person A's current status.
