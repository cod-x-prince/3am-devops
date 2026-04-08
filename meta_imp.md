# Meta Implementation Plan (meta_imp)

## Purpose

This file is the consolidated source of truth after analyzing Track A and Track B trackers and validating current code status in the workspace.

Goals:

- Align tracker documents with actual implementation state.
- Remove contradictory handoff notes between Track A and Track B.
- Define a safe execution path that does not break existing flows or pipelines.

## What Was Analyzed

- `trackA.md`
- `trackB.md`
- Dashboard implementation files in `incident-env/dashboard/src/`
- Grader files in `incident-env/graders/`

## Reality Check (Code vs Tracker)

### Confirmed Implemented

- Track A engine and env wrapper are functionally present.
- Track B dashboard app structure is implemented:
  - `App.jsx`
  - `hooks/useEpisodeStream.js`
  - `components/ServiceGraph.jsx`
  - `components/MetricsFeed.jsx`
  - `components/AgentLog.jsx`
  - `components/ScoreCard.jsx`

### Confirmed Missing / Stubbed

- `incident-env/graders/programmatic.py` is still a stub.
- `incident-env/graders/llm_grader.py` is still a stub.

## Fixes Applied In This Pass

### Tracker Consistency Fixes

1. Updated `trackA.md` messages for B:
   - Marked observation shape confirmation as done.
   - Marked action space confirmation as done.
   - Marked `ServiceState` field order sharing as done.

2. Updated `trackB.md` dashboard component table:
   - Changed B7 component tasks from not started to done where code exists.
   - Kept full e2e demo flow as in progress until live API+dashboard verification is completed.

These changes are documentation-only and do not affect runtime behavior.

## Current Status Snapshot

### Track A

- Engine: largely implemented.
- Env wrapper: implemented.
- Rewards: partial/stub-heavy.
- Graders: not implemented (critical remaining gap).
- Tests: partial; smoke is passing, full suite not complete.

### Track B

- Training/API: implemented.
- Dashboard components: implemented.
- End-to-end demo reliability: pending full live verification run.

## Pipeline-Safe Implementation Plan

## Phase 1: Stabilize Existing Green Paths

- Do not modify existing API response schema used by dashboard.
- Do not change observation shape `(72,)` or action space `MultiDiscrete([12, 7])`.
- Keep current trained/untrained API behavior unchanged.

Exit criteria:

- Existing smoke tests remain green.
- API and dashboard start commands run without schema regressions.

## Phase 2: Implement Programmatic Grader First

- Implement `incident-env/graders/programmatic.py` with deterministic scoring.
- Keep grader pure and independent of external services.
- Add tests in `incident-env/tests/test_graders.py` for score bounds and deterministic behavior.

Exit criteria:

- Programmatic grader returns valid scores consistently.
- Grader tests pass locally.

## Phase 3: Implement LLM Grader with Safe Fallback

- Implement `incident-env/graders/llm_grader.py` using the exact model tag `llama3:8b-instruct-q4_K_M`.
- Add strict JSON parsing and schema validation.
- Add graceful fallback when Ollama is unavailable so demo path does not fail.

Exit criteria:

- LLM grader works when Ollama is available.
- Fallback returns valid neutral result when Ollama is unavailable.

## Phase 4: Complete Scenario and Test Coverage

- Expand scenario coverage and validate loading behavior.
- Add/complete tests for env compliance, reward bounds, and scenario validity.

Exit criteria:

- `pytest tests/` passes fully.

## Phase 5: End-to-End Demo Reliability Lock

- Run API + dashboard together and verify live WebSocket updates.
- Run full demo flow three consecutive times without intervention.

Exit criteria:

- 3/3 successful end-to-end runs.
- Trackers updated with final completion states.

## Validation Commands (Windows-safe)

From `incident-env/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\
```

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000
```

From `incident-env/dashboard/`:

```powershell
npm install
npm run dev
```

## Risk Register

1. Graders remain stubbed:
   - Impact: judging and evaluation completeness risk.
   - Mitigation: implement programmatic grader before LLM grader.

2. Dashboard startup instability (`npm run dev` previously exited with code 1):
   - Impact: demo reliability risk.
   - Mitigation: run install/clean start and verify with live API session.

3. Cross-track drift:
   - Impact: integration breakage.
   - Mitigation: keep contract fields frozen and track updates in both files.

## Immediate Next Actions

1. Implement `programmatic.py` and its tests.
2. Implement `llm_grader.py` with fallback and parsing tests.
3. Run full local test suite.
4. Validate API + dashboard live run and mark final demo readiness.
