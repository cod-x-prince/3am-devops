# Person B Implementation Plan

Owner: Person B
Track: Training, API, Dashboard
Date: 2026-04-08

## Current Context

- Track A is not yet ready with real environment bindings.
- Immediate unblock path is MockIncidentEnv, then swap to real IncidentEnv once A confirms contracts.
- Contract assumptions (must stay fixed unless both sides sync):
  - Observation shape: (72,)
  - Action space: MultiDiscrete([12, 7])
  - Episode stream payload: EpisodeFrame from API_CONTRACT.md

## Critical Sync Points
–
1. Sync Point: observation shape and metric order from A

- Required confirmation: env.observation_space.shape == (72,)
- Required confirmation: metric order [cpu, memory, error_rate, latency_p50, latency_p99, request_rate]

2. Sync Point: action space from A

- Required confirmation: env.action_space == MultiDiscrete([12, 7])

3. Sync Point: services_json and ServiceState field mapping

- Required confirmation: get_service_states_json output schema exactly matches API_CONTRACT.md

4. Sync Point: graders import path

- Required confirmation: graders package import works from api/main.py and training/eval.py

## Phase Plan

### Phase 0 (Hour 0-2): Unblock Foundation

Goals:

- Build tests/mock_env.py with contract-compatible observation and action spaces.
- Ensure one PPO collection/update cycle runs without crash.

Tasks:

- Implement MockIncidentEnv in tests/mock_env.py
- Add minimal smoke test for reset/step shapes and dtypes
- Wire temporary training entry point to use MockIncidentEnv

Definition of done:

- One short run completes with no exceptions.
- Logs show at least one batch collected and one optimization step.

### Phase 1 (Hour 2-8): TorchRL Training Core

Goals:

- Build production training loop in training/train.py.

Tasks:

- GymWrapper + transforms (reward scaling, observation normalization)
- Actor/Critic networks for 72-dim input
- ProbabilisticActor for multidiscrete action heads
- SyncDataCollector + GAE + ClipPPOLoss
- Optimizer, grad clipping, TensorBoard logs
- Checkpoint save every 100 epochs

Definition of done:

- train.py starts and runs stable on MockIncidentEnv.
- Checkpoints are written to checkpoints/.
- TensorBoard shows reward/value/loss curves.

### Phase 2 (Hour 8-12): Curriculum and Evaluation

Goals:

- Implement level progression and evaluation reporting.

Tasks:

- Implement CurriculumScheduler in training/curriculum.py
- Integrate scheduler into training loop
- Implement training/eval.py for scenario sweeps and grader calls
- Include human baseline comparison string

Definition of done:

- Curriculum can advance from level 1 to level 2 in controlled test.
- Eval produces JSON report with required metrics.

### Phase 3 (Hour 12-18): FastAPI Episode Service

Goals:

- Serve simulation frames over websocket.

Tasks:

- Build api/main.py endpoints:
  - GET /health
  - GET /scenarios
  - POST /episode/start
  - WS /episode/stream/{episode_id}
  - POST /episode/stop/{episode_id}
  - GET /episode/result/{episode_id}
- Add CORS for localhost:5173
- Implement untrained random-policy mode first

Definition of done:

- WebSocket emits valid EpisodeFrame objects at 10 fps.
- API works with mock env even if Track A is pending.

### Phase 4 (Hour 18-28): Dashboard Integration

Goals:

- Build a stable, demo-ready live dashboard.

Tasks:

- Build/useEpisodeStream hook with reconnect strategy
- ServiceGraph (D3 force): nodes, edges, health colors, pulse states
- MetricsFeed (Recharts): error, latency, cpu panels
- AgentLog: streaming actions and final reasoning block
- ScoreCard: MTTR, blast radius, false alarms, speedup
- App wiring: scenario selector, trained/untrained toggle, WS status

Definition of done:

- End-to-end mock flow runs continuously with no UI crashes.
- Visuals update smoothly and reflect incoming frame values.

### Phase 5 (Hour 28-36): Real Env Swap and Hardening

Goals:

- Replace mock env with real IncidentEnv and harden failure paths.

Tasks:

- Swap integration source from tests/mock_env.py to envs/incident_env.py
- Validate strict schema compatibility with API contract
- Handle disconnected WS clients and cancellation cleanly
- Add fallback handling when LLM grader is unavailable

Definition of done:

- Same API and dashboard work with real env without code changes in UI.
- No crash on env reset, episode timeout, or grader fallback.

### Phase 6 (Hour 36-44): Demo Lockdown

Goals:

- Produce deterministic demo script and run success repeatedly.

Tasks:

- Load trained checkpoint in API mode
- Validate final metrics and baseline comparison text
- Run full demo at least 3 consecutive times
- Capture backup script for untrained mode if checkpoint fails

Definition of done:

- Demo can be executed offline and repeatable.
- Final narrative numbers render in ScoreCard.

## Windows-First Command Set

Run from repository root unless noted.

1. Python tests and scripts

- .\incident-env\.venv\Scripts\python.exe -m pytest incident-env/tests
- .\incident-env\.venv\Scripts\python.exe incident-env/training/train.py
- .\incident-env\.venv\Scripts\python.exe incident-env/training/eval.py

2. API server

- .\incident-env\.venv\Scripts\python.exe -m uvicorn incident-env.api.main:app --reload --port 8000

3. Dashboard

- cd incident-env/dashboard
- npm install
- npm run dev

## Risks and Mitigations

1. Risk: Track A delivery delay blocks real integration.

- Mitigation: Keep full mock-first path and interface adapter layer.

2. Risk: Contract mismatch in services_json fields.

- Mitigation: Add schema validation before websocket emit.

3. Risk: PPO instability early in training.

- Mitigation: Start with conservative lr/entropy and clamp gradients.

4. Risk: Demo break if LLM grader unavailable.

- Mitigation: Always support fallback grading path.

## Daily Checkpoint Checklist

- Update trackB.md progress bars and completed tasks
- Log decisions and blockers
- Leave sync notes for Person A in Messages for Person A
- Push to feature branch when available
