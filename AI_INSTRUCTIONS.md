# AI Session Instructions — IncidentEnv Hackathon
> READ THIS FILE AT THE START OF EVERY SESSION

---

## Step 1 — Identify the Person

**Ask the user this immediately:**

> "Which person are you — **Person A** (Simulation Engine, Environment, Graders) or **Person B** (Training, API, Dashboard)?"

Wait for their answer before doing anything else.

---

## Step 2 — Load Context Based on Person

### If Person A:
1. Read `trackA.md` fully — understand current task status and blockers
2. Read `trackB.md` — check the "Messages for Person A" section + what B is working on
3. Read `API_CONTRACT.md` — know the exact obs/action shapes B depends on
4. Read `IMPLEMENTATION_PLAN.md` Track A section for full task spec
5. Tell Person A: *"Here's where you left off: [summarise trackA status]. B needs [any pending items from B's messages]."*

### If Person B:
1. Read `trackB.md` fully — understand current task status and blockers
2. Read `trackA.md` — check the "Messages for Person B" section + what A is working on
3. Read `API_CONTRACT.md` — know what A will deliver and what format to expect
4. Read `IMPLEMENTATION_PLAN.md` Track B section for full task spec
5. Tell Person B: *"Here's where you left off: [summarise trackB status]. A has [any updates from A's messages]."*

---

## Step 3 — Session Rules

### Track Updates (CRITICAL)
After every meaningful task completion, update the relevant track file:
- Mark completed tasks as `✅`
- Update the progress bars at the top (estimate percentage)
- Update milestone status if reached
- Add any new blockers to the blockers table
- Log any important decisions in the decisions log
- If leaving a message for the other person, add it to the "Messages for Person X" section

### Integration Sync Points
When you see a task marked **[SYNC POINT]**, stop and flag it:
> "This task requires confirming with Person [X]. Have you synced with them yet? If not, what's the current assumption we're working with?"

### Blocker Handling
If a task is blocked, mark it `❌ Blocked` in the tracker, describe the blocker, and immediately suggest an alternative task to work on so momentum isn't lost.

### Cross-Track Awareness
Always remind the person what the other track is working on if it's relevant. Example: *"A is currently building the fault injector — you'll need this before connecting the real env. In the meantime, here's what you can do with MockEnv..."*

---

## Step 4 — Hackathon-Specific Rules

### Tech Stack — NON-NEGOTIABLE
| Rule | Reason |
|---|---|
| Use **TorchRL** not Stable Baselines or RLlib | Meta judges — using Meta's own library is a signal |
| Use **Llama 3** (`llama3:8b-instruct-q4_K_M`) not GPT/Claude | Meta hackathon — use Meta's model. Exact tag from `ollama list` |
| Use **PyTorch** not JAX | Meta's primary framework |
| Use **ollama.chat()** not API calls | Local inference — no internet dependency at venue |
| Use **FastAPI** not Flask/Django | Async-first, WebSocket native |
| Use **D3 v7** for ServiceGraph | Force-directed graph physics |
| Use **Recharts** for MetricsFeed | Not Chart.js or Victory |

### Windows-Specific Rules (VALORMUSK)
- Always use `.\.venv\Scripts\python.exe` not `python` directly
- Always use `.\.venv\Scripts\maturin.exe develop -m engine/Cargo.toml --release` (not root Cargo.toml)
- If `os error 32` appears — Windows Defender exclusion needed for `target/` folder (run as Admin)
- Use `python -m pytest` not bare `pytest`

### Reward Function Rule
Every reward function must return a `float` in `[-1.0, 1.0]`. Non-negotiable. Normalise before returning.

### Never During Demo
- Never call OpenAI/Anthropic API (only Ollama local)
- Never require internet connection
- Never use bare `python` — always venv python

---

## Step 5 — Quick Reference: File Ownership

```
engine/           → Person A
envs/             → Person A
rewards/          → Person A
graders/          → Person A
scenarios/        → Person A
tests/test_smoke  → Person A
tests/test_env    → Person A
tests/test_graders → Person A
tests/test_scenarios → Person A

training/         → Person B
api/              → Person B
dashboard/        → Person B
tests/mock_env    → Person B (builds this to unblock themselves)
```

---

## Step 6 — Critical Integration Points to Watch

### Observation Space
```python
env.observation_space.shape == (72,)   # 12 services × 6 metrics
# Metric order per service: [cpu, memory, error_rate, latency_p50, latency_p99, request_rate]
```
Person B's actor network input size depends entirely on this. If A changes it, B must update immediately.

### Action Space
```python
env.action_space == MultiDiscrete([12, 7])
# [target_service_id (0-11), action_type (0-6)]
```

### WebSocket Message Schema
Defined in `API_CONTRACT.md`. Both A and B depend on `EpisodeFrame` — do not change fields without updating both sides.

### Ollama Model Tag
```
llama3:8b-instruct-q4_K_M
```
This is the exact tag confirmed in `ollama list`. Use it everywhere. Do not use `llama3` or `llama3:latest`.

---

## Step 7 — End of Session Checklist

Before ending any session, remind the person to:
- [ ] Push to their branch (`feat/track-a` or `feat/track-b`)
- [ ] Update their track file with progress
- [ ] Leave messages for the other person if needed
- [ ] Note any blockers that the other person needs to know about

---

## Project Context Summary

**Project:** IncidentEnv — OpenEnv RL environment for autonomous incident remediation
**Hackathon:** Meta PyTorch OpenEnv Hackathon x SST 2026
**Finale:** April 25–26, 2026 | 48 hours | Scaler School of Technology, Bangalore
**Prize:** $30,000 + interview with Meta and Hugging Face AI teams
**Machine (Person A):** Windows (VALORMUSK) — Rust + Python + Ollama locally
**Venv location:** `incident-env/.venv/`
**Ollama models available:** `llama3:8b-instruct-q4_K_M`, `gemma3:1b`

**The demo moment that wins:**
> ScoreCard shows: "Human SRE average: 4.2 hours | Agent: 4.3 seconds | Speedup: 3,527x"
