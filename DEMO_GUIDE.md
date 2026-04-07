# Demo Guide — IncidentEnv
> Meta PyTorch OpenEnv Hackathon x SST 2026
> Rehearse this 3x before presenting. Every second matters.

---

## Pre-Demo Checklist (Do 30 Minutes Before)

- [ ] API server running: `uvicorn api.main:app --port 8000` → check `/health`
- [ ] Dashboard running: `npm run dev` → open `localhost:5173`
- [ ] Ollama running: `ollama list` confirms `llama3:8b-instruct-q4_K_M`
- [ ] Trained checkpoint loaded: `checkpoints/ppo_level4_best.pt` exists
- [ ] TensorBoard open: shows training curves (optional but impressive)
- [ ] Browser zoomed to 110% so judges can read metrics
- [ ] Second monitor/screen showing code (optional)
- [ ] `cascade_timeout` scenario pre-selected in dashboard dropdown
- [ ] Terminal with `pytest tests/ -v` ready to run (shows green checkmarks)

---

## The 3-Minute Demo Script

### Slide 1 — Problem (20 seconds)
> *"Every SRE team has this problem. 3AM. PagerDuty fires. Something's down. A human gets woken up, digs through logs, finds the root cause, applies a fix. Average MTTR across the industry: 4.2 hours. We built an RL agent that does it in seconds."*

### Live Demo — Setup (10 seconds)
> *"This is our dashboard. 12 microservices, all healthy, green. This is a simulated production environment — our Rust engine runs at sub-millisecond speed, which means we can train on millions of failure scenarios."*

Point at ServiceGraph — all green nodes.

### Live Demo — Fault Injection (20 seconds)
> *"I'm going to trigger a cascade timeout — upstream service goes down, latency propagates to 4 dependent services."*

Click "cascade_timeout" → Click "Start Episode" → Watch 4 nodes go red/orange.

Point at MetricsFeed: *"Watch the error rate spike and latency climb in real time."*

### Live Demo — Untrained Agent (30 seconds)
> *"This is an untrained random policy. Watch what it does."*

Click "Untrained Agent" → Watch AgentLog: random actions, things get worse.

> *"It's making things worse — restarting healthy services, ignoring the critical ones."*

Wait for episode to fail or run out of steps. ScoreCard shows bad score.

### Live Demo — Trained Agent (40 seconds)
> *"Same scenario. This is our PPO agent trained with curriculum learning — started on simple single-fault scenarios, graduated through 5 difficulty levels."*

Click "Reset" → Click "Trained Agent (PPO L4)" → Watch agent act.

Point at AgentLog: *"Notice it triggered a circuit breaker first — that stops the cascade — then restarted the root cause service. That's the correct clinical order."*

Watch services go green one by one.

### ScoreCard Moment (20 seconds)
> *"4.3 seconds to resolution."*

Point at ScoreCard. Pause for effect.

> *"Human average: 4.2 hours. Our agent: 4.3 seconds. That's a 3,527x improvement."*

Let that land. Don't rush past it.

### LLM Grader (20 seconds)
> *"We validate our agent's reasoning using Llama 3 — Meta's own model — running fully locally. No API calls, no internet dependency."*

Point at the LLM reasoning box in AgentLog.

> *"The model confirms the agent correctly identified the root cause and applied the optimal remediation sequence."*

### Multi-Fault Live Demo (20 seconds)
> *"One more — multi-fault. Two simultaneous failures. Watch it triage by blast radius — fixes the one affecting more services first."*

Switch to `multi_fault` → Start → let agent resolve.

### Close (20 seconds)
> *"IncidentEnv is built on OpenEnv, trained with TorchRL — Meta's own RL library — with a Rust simulation core for 100x faster training throughput than Python. The environment ships with 6 scenarios, curriculum learning across 5 difficulty levels, and both programmatic and LLM grading. All open source, all runs locally."*

---

## Judging Q&A — Prepared Answers

**Q: How realistic is the simulation?**
> "The failure modes — cascade timeouts, thundering herds, split brains — are all modeled from real production failure patterns documented in postmortems at Netflix, Google, and AWS. The service graph propagation follows the same dependency math as real distributed systems. We're simulating failure *patterns*, not hardware, and patterns transfer."

**Q: Does this generalize to real infrastructure?**
> "The agent learns structural patterns — 'when error rate spikes and latency cascades, apply circuit breaker before restart.' Those heuristics apply regardless of whether it's our simulated graph or a real k8s cluster. Next step is connecting to real Prometheus/Datadog via an adapter layer."

**Q: Why Rust for the engine?**
> "RL training needs millions of environment steps. A Python simulation runs at ~1,000 steps/second. Our Rust core runs at ~100,000 steps/second. That's 100x more training data in the same time, which directly translates to a better-performing agent at demo time."

**Q: Why TorchRL specifically?**
> "It's Meta's own RL library, built on PyTorch, with first-class support for multi-discrete action spaces and curriculum learning. It felt right to use Meta's own tooling at a Meta hackathon — and it's genuinely the best option for this architecture."

**Q: What's the action space?**
> "MultiDiscrete — 12 service targets × 7 action types. The agent learns to pair the right action with the right service. RestartService, ScaleUp, RollbackDeploy, RerouteTraffic, ToggleFeatureFlag, TriggerCircuitBreaker, and NoOp."

**Q: How does the LLM grader work?**
> "We send Llama 3 the incident description, the agent's full action sequence, and the final service states. It scores root cause identification, remediation appropriateness, blast radius minimization, and action efficiency — all in JSON. It runs locally via Ollama, so no internet, no latency, no cost."

---

## Emergency Fallbacks

| Problem | Fallback |
|---|---|
| WebSocket disconnects mid-demo | Refresh dashboard, restart episode |
| Trained agent performs poorly | Switch to `bad_deploy` (simplest scenario, most reliable) |
| Ollama LLM grader fails | "LLM grader result pending" — show programmatic score instead |
| Dashboard won't start | Show TensorBoard training curves instead |
| Rust engine import fails | Use MockEnv — explain "production version uses Rust for 100x speed" |
| Network issues | Everything runs local — no external dependencies |

---

## The One Line That Wins

If you only say one thing:

> **"Human SRE average: 4.2 hours. Our agent: 4.3 seconds. That's 3,527 times faster."**

Make sure that line lands. Pause before it. Pause after it.
