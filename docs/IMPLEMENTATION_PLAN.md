# IncidentEnv — Full Implementation Plan
> Meta PyTorch OpenEnv Hackathon x SST 2026
> Team: cod-x-prince + [Person B]
> Finale: April 25–26, 2026 | 48 hours | Scaler School of Technology, Bangalore

---

## Project Overview

**IncidentEnv** is an OpenEnv-compatible reinforcement learning environment where agents learn to autonomously diagnose and remediate production infrastructure incidents — solving the 3AM DevOps problem without waking a human.

### The Pitch
> *"We built a limit order book-style RL environment for production infrastructure. An agent observes real-time telemetry across a microservice graph, traces root causes, and applies remediations — fully autonomously. Human SRE average MTTR: 4.2 hours. Our trained agent: under 10 seconds."*

### Stack Summary
| Layer | Technology | Owner |
|---|---|---|
| Simulation Engine | Rust + PyO3 | Person A |
| OpenEnv Interface | Python + gymnasium | Person A |
| Reward Functions | Python | Person A |
| LLM Grader | Llama 3 + Ollama | Person A |
| Scenario Configs | JSON | Person A |
| RL Training | PyTorch + TorchRL | Person B |
| Curriculum Scheduler | Python | Person B |
| Evaluation Runner | Python | Person B |
| API Server | FastAPI + WebSockets | Person B |
| Dashboard | React + D3 + Recharts | Person B |

---

## Integration Boundary

The **critical handoff point** between Track A and Track B is:

```
envs/incident_env.py  ←→  training/train.py
```

Person A owns everything that produces the env. Person B owns everything that consumes it.

**Contract:** `IncidentEnv` must expose a standard gymnasium API:
```python
env = IncidentEnv(scenario="bad_deploy", curriculum_level=1)
obs, info = env.reset()
obs, reward, terminated, truncated, info = env.step(action)
```

Both people should agree on `obs.shape` and `action_space` before splitting — see `API_CONTRACT.md`.

---

## Timeline (48 Hours)

```
Hour 00–08  [A] Rust engine core + PyO3 bindings compiling
Hour 00–08  [B] Training scaffold + TorchRL boilerplate + Dashboard skeleton

Hour 08–16  [A] OpenEnv wrapper + 3 scenarios + reward functions
Hour 08–16  [B] PPO agent + curriculum scheduler + FastAPI WebSocket

Hour 16–24  [A] All 6 scenarios + graders (programmatic + LLM)
Hour 16–24  [B] Full dashboard (ServiceGraph + MetricsFeed + AgentLog + ScoreCard)

Hour 24–32  [A] Tests + bug fixes + obs space tuning
Hour 24–32  [B] First training runs + tensorboard analysis + eval script

Hour 32–40  [A] Performance optimization + edge case handling
Hour 32–40  [B] Dashboard polish + trained agent integration + demo mode

Hour 40–44  [BOTH] Integration testing — env + trained agent + dashboard end-to-end
Hour 44–48  [BOTH] Demo rehearsal + README + submission
```

---

# TRACK A — Simulation Engine, Environment & Graders

**Owner:** Person A
**Core Responsibility:** Everything from raw simulation up to and including the OpenEnv-compliant Python interface, rewards, graders, and scenario configs.

## A1 — Rust Simulation Engine

**Directory:** `engine/src/`
**Priority:** CRITICAL — nothing else works without this

### A1.1 — `engine/Cargo.toml`
```toml
[package]
name = "incident_core"
version = "0.1.0"
edition = "2021"

[lib]
name = "incident_core"
crate-type = ["cdylib", "rlib"]

[dependencies]
pyo3 = { version = "0.21", features = ["extension-module"] }
petgraph = "0.6"
rand = "0.8"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
```

### A1.2 — `engine/src/service_graph.rs`
Core data structure: petgraph `Graph<ServiceNode, f32>` where:
- **ServiceNode fields:** `id: String`, `health: f32` (0.0–1.0), `cpu_usage: f32`, `memory_usage: f32`, `error_rate: f32`, `latency_p99: f32`, `status: ServiceStatus`
- **ServiceStatus enum:** `Healthy`, `Degraded`, `Critical`, `Down`
- **Edge weight:** `dependency_strength: f32` (how much a failing upstream hurts this node)

**Key methods to implement:**
```rust
pub fn new(num_services: usize, topology: &str) -> Self
pub fn step(&mut self, action: u32) -> (Vec<f32>, f32, bool)
pub fn reset(&mut self) -> Vec<f32>
pub fn inject_fault(&mut self, fault_type: &str, target: usize)
pub fn propagate_failure(&mut self, source: usize)
pub fn get_observation_vector(&self) -> Vec<f32>  // shape: [num_services * 6]
pub fn is_resolved(&self) -> bool
pub fn get_service_states_json(&self) -> String   // for API streaming
```

**Failure propagation logic:**
```
for each edge (source → dependent):
    if source.health < 0.5:
        dependent.latency_p99 += edge_weight * source_degradation * 50ms
        dependent.error_rate += edge_weight * source_degradation * 0.1
        dependent.health = f(latency, error_rate, cpu, memory)
```

### A1.3 — `engine/src/fault_injector.rs`
```rust
pub enum FaultType {
    CpuSpike { severity: f32, duration_ticks: u32 },
    MemoryLeak { leak_rate: f32 },
    NetworkPartition { affected_edges: Vec<(usize, usize)> },
    DbDeadlock { service_id: usize },
    BadDeploy { service_id: usize, error_rate_spike: f32 },
    ThunderingHerd { origin: usize, retry_multiplier: f32 },
    CascadeTimeout { chain: Vec<usize> },
    SplitBrain { db_service: usize },
}
```

Each fault variant modifies the service graph state at each tick according to its own decay/growth function. Use seeded RNG for reproducible eval runs.

### A1.4 — `engine/src/metrics_engine.rs`
- Maintains rolling window (60 ticks) per service for all 6 metrics
- Adds configurable Gaussian noise (`sigma = 0.02` default)
- `get_observation_vector()` returns flat `Vec<f32>` of shape `[num_services * 6]`
- Metric order per service: `[cpu, memory, error_rate, latency_p50, latency_p99, request_rate]`

### A1.5 — `engine/src/lib.rs`
```rust
#[pymodule]
fn incident_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<RustServiceGraph>()?;
    m.add_class::<FaultInjector>()?;
    Ok(())
}
```

**Smoke test after building:**
```bash
.\.venv\Scripts\python.exe -c "
import incident_core
g = incident_core.RustServiceGraph('bad_deploy', 1)
obs = g.reset()
print('obs shape:', len(obs))  # should be num_services * 6
obs2, reward, done = g.step(0)
print('step works, reward:', reward)
"
```

---

## A2 — OpenEnv Python Interface

**Directory:** `envs/`

### A2.1 — `envs/incident_env.py`
```python
import gymnasium as gym
import numpy as np
from incident_core import RustServiceGraph

class IncidentEnv(gym.Env):
    NUM_SERVICES = 12
    NUM_METRICS = 6
    NUM_ACTION_TYPES = 7

    def __init__(self, scenario: str = "bad_deploy", curriculum_level: int = 1):
        super().__init__()
        self.scenario = scenario
        self.curriculum_level = curriculum_level
        self.graph = RustServiceGraph(scenario, curriculum_level)

        # Observation: all service metrics flattened
        self.observation_space = gym.spaces.Box(
            low=0.0, high=1.0,
            shape=(self.NUM_SERVICES * self.NUM_METRICS,),
            dtype=np.float32
        )

        # Action: [target_service_id (0-11), action_type (0-6)]
        self.action_space = gym.spaces.MultiDiscrete([
            self.NUM_SERVICES,
            self.NUM_ACTION_TYPES
        ])

    def step(self, action):
        ...

    def reset(self, seed=None, options=None):
        ...

    def render(self):
        ...
```

**Action types enum:**
```python
class ActionType(IntEnum):
    RESTART_SERVICE = 0
    SCALE_UP = 1
    ROLLBACK_DEPLOY = 2
    REROUTE_TRAFFIC = 3
    TOGGLE_FEATURE_FLAG = 4
    TRIGGER_CIRCUIT_BREAKER = 5
    NO_OP = 6
```

### A2.2 — `envs/scenarios.py`
Registry mapping scenario names to configs. Must support:
```python
scenario = get_scenario("bad_deploy")
env = IncidentEnv(**scenario.env_kwargs)
```

---

## A3 — Reward Functions

**Directory:** `rewards/`
**Contract:** Every reward function returns `float` in `[-1.0, 1.0]`

### A3.1 — `rewards/mttr.py`
```python
def compute(steps_taken: int, resolved: bool, max_steps: int) -> float:
    if not resolved:
        return 0.0
    # Normalize: perfect = 1.0 (1 step), worst passing = 0.1 (max_steps)
    normalized = 1.0 - (steps_taken - 1) / max_steps
    bonus = 0.3 if steps_taken <= 5 else 0.0  # elite bonus
    return min(1.0, normalized + bonus)
```

### A3.2 — `rewards/blast_radius.py`
```python
def compute(newly_degraded: int, total_services: int) -> float:
    # Per-step penalty for spreading failure
    per_step = -0.1 * newly_degraded
    normalized = per_step / total_services
    return max(-1.0, normalized)
```

### A3.3 — `rewards/false_alarm.py`
```python
def compute(action_target_health: float, action_type: int, critical_exists: bool) -> float:
    if action_target_health > 0.9:      # acted on healthy service
        return -0.2
    if action_type == ActionType.NO_OP and critical_exists:
        return -0.05                     # did nothing while something is critical
    return 0.0
```

### A3.4 — `rewards/composite.py`
```python
WEIGHTS = {"mttr": 0.5, "blast_radius": 0.25, "false_alarm": 0.15, "efficiency": 0.10}

def compute(mttr_r, blast_r, false_alarm_r, efficiency_r) -> float:
    raw = (WEIGHTS["mttr"] * mttr_r +
           WEIGHTS["blast_radius"] * blast_r +
           WEIGHTS["false_alarm"] * false_alarm_r +
           WEIGHTS["efficiency"] * efficiency_r)
    return float(np.clip(raw, -1.0, 1.0))
```

---

## A4 — Graders

**Directory:** `graders/`

### A4.1 — `graders/programmatic.py`
```python
@dataclass
class GraderResult:
    all_healthy: bool
    resolution_steps: int
    blast_radius_score: float  # 0-1, higher = less spread
    false_positive_count: int
    overall_score: float        # weighted 0-100
    passed: bool
```

### A4.2 — `graders/llm_grader.py`
Uses `ollama.chat(model="llama3:8b-instruct-q4_K_M", ...)`.

**Important:** Use `llama3:8b-instruct-q4_K_M` — this is the exact tag in the `ollama list` output from Prince's machine. Don't use `llama3` (no tag) as it may not resolve.

```python
SYSTEM_PROMPT = """You are a Senior SRE evaluating an AI agent's incident response.
You must respond ONLY with valid JSON. No markdown. No explanation. No backticks."""

def grade(incident: str, actions: list[str], final_states: dict, resolved: bool) -> LLMGraderResult:
    try:
        response = ollama.chat(
            model="llama3:8b-instruct-q4_K_M",
            messages=[{"role": "user", "content": GRADER_PROMPT.format(...)}]
        )
        return LLMGraderResult(**json.loads(response["message"]["content"]))
    except Exception:
        return LLMGraderResult.fallback()  # never crash during demo
```

---

## A5 — Scenario Configs

**Directory:** `scenarios/configs/`

All 6 scenarios must have these fields:
```json
{
  "name": "bad_deploy",
  "description": "...",
  "curriculum_level": 1,
  "topology": "mesh",
  "num_services": 12,
  "fault_sequence": [
    { "tick": 0, "fault_type": "BadDeploy", "target": 3, "params": { "error_rate_spike": 0.6 } }
  ],
  "max_steps": 15,
  "success_condition": "all_services_healthy",
  "expected_actions": ["RollbackDeploy"]
}
```

Scenarios: `bad_deploy`, `memory_leak`, `cascade_timeout`, `thundering_herd`, `split_brain`, `multi_fault`

---

## A6 — Tests

**Directory:** `tests/`

| File | Tests |
|---|---|
| `test_smoke.py` | PyO3 import + instantiation + obs shape |
| `test_env.py` | gymnasium API compliance, reward bounds, episode termination |
| `test_graders.py` | programmatic score in [0,100], LLM grader JSON schema (mock ollama) |
| `test_scenarios.py` | all JSON configs have required fields |

---

## Track A Deliverables Checklist

- [ ] Rust engine compiles via `maturin develop -m engine/Cargo.toml --release`
- [ ] `import incident_core` works in venv
- [ ] `IncidentEnv` passes gymnasium compliance check
- [ ] All 6 scenario JSON configs present and valid
- [ ] All reward functions return float in [-1, 1]
- [ ] Programmatic grader returns GraderResult
- [ ] LLM grader falls back gracefully if Ollama is down
- [ ] `pytest tests/` passes (all 4 test files)
- [ ] `env.observation_space.shape == (72,)` confirmed
- [ ] `env.action_space` is `MultiDiscrete([12, 7])` confirmed

---

---

# TRACK B — Training, API Server & Dashboard

**Owner:** Person B
**Core Responsibility:** Consuming the IncidentEnv from Track A, training an agent with TorchRL, building the FastAPI real-time streaming server, and the React + D3 visualization dashboard.

## B1 — TorchRL Training

**Directory:** `training/`
**Dependency:** Requires `IncidentEnv` from Track A to be importable

### B1.1 — `training/train.py`

```python
from torchrl.envs import GymWrapper, TransformedEnv, StepCounter
from torchrl.envs.transforms import RewardScaling, ObservationNorm
from torchrl.collectors import SyncDataCollector
from torchrl.objectives import ClipPPOLoss
from torchrl.objectives.value import GAE
from torchrl.modules import MLP, ProbabilisticActor, ValueOperator
from tensordict.nn import TensorDictModule
from torch.optim import Adam

HYPERPARAMS = {
    "lr": 3e-4,
    "gamma": 0.99,
    "lmbda": 0.95,
    "clip_epsilon": 0.2,
    "entropy_coef": 0.01,
    "value_loss_coef": 0.5,
    "max_grad_norm": 0.5,
    "frames_per_batch": 1000,
    "total_frames": 1_000_000,
    "num_epochs": 10,
    "batch_size": 64,
    "checkpoint_every": 100,
}
```

**Architecture:**
- Actor: `MLP(in_features=72, out_features=action_dim, depth=3, num_cells=256)` + tanh
- Critic: same architecture → scalar value head
- Use `ProbabilisticActor` with `OneHotCategorical` distribution for discrete actions

**Training loop structure:**
```python
for i, batch in enumerate(collector):
    # compute GAE
    # PPO update (num_epochs inner loops)
    # log to tensorboard
    # curriculum check
    # checkpoint save
```

### B1.2 — `training/curriculum.py`
```python
class CurriculumScheduler:
    THRESHOLDS = {1: 0.60, 2: 0.65, 3: 0.70, 4: 0.75, 5: 0.80}
    WINDOW = 50  # episodes

    def __init__(self):
        self.current_level = 1
        self.recent_rewards: deque = deque(maxlen=self.WINDOW)

    def update(self, episode_reward: float) -> bool:
        """Returns True if level advanced."""
        self.recent_rewards.append(episode_reward)
        if len(self.recent_rewards) >= self.WINDOW:
            mean = sum(self.recent_rewards) / len(self.recent_rewards)
            if mean > self.THRESHOLDS.get(self.current_level, 1.0):
                self.current_level = min(5, self.current_level + 1)
                self.recent_rewards.clear()
                return True
        return False
```

### B1.3 — `training/eval.py`
Run 100 episodes across all 6 scenarios with a trained checkpoint. Output:
```python
@dataclass
class EvalReport:
    scenario_results: dict[str, ScenarioMetrics]
    overall_score: float
    mean_mttr_steps: float
    mean_blast_radius: float
    false_positive_rate: float
    curriculum_level_reached: int
    vs_human_baseline: str  # e.g. "Agent: 4.3s | Human avg: 4.2hr"
```

---

## B2 — FastAPI Server

**Directory:** `api/`

### B2.1 — `api/main.py`

**Endpoints:**
```
GET  /health                     → {"status": "ok", "ollama": bool, "model_loaded": bool}
GET  /scenarios                  → List[ScenarioMeta]
POST /episode/start              → {"episode_id": str, "scenario": str}
WS   /episode/stream/{episode_id} → streams EpisodeFrame every tick
POST /episode/stop/{episode_id}  → stops episode
GET  /episode/result/{episode_id} → EvalReport (after done=True)
```

**WebSocket message schema (EpisodeFrame):**
```python
class ServiceState(BaseModel):
    id: str
    health: float
    cpu: float
    memory: float
    error_rate: float
    latency_p99: float
    status: str  # "healthy" | "degraded" | "critical" | "down"

class EpisodeFrame(BaseModel):
    tick: int
    services: list[ServiceState]
    connections: list[tuple[str, str, float]]  # (source_id, target_id, strength)
    last_action: str | None
    last_action_target: str | None
    cumulative_reward: float
    episode_done: bool
    resolution_status: str  # "in_progress" | "resolved" | "failed"
    scores: dict  # {mttr, blast_radius, false_alarm_count}
    llm_reasoning: str | None  # populated when episode_done=True
```

**WebSocket implementation:**
```python
@app.websocket("/episode/stream/{episode_id}")
async def episode_stream(websocket: WebSocket, episode_id: str):
    await websocket.accept()
    episode = active_episodes[episode_id]
    try:
        while not episode.done:
            frame = episode.step()  # runs one env step
            await websocket.send_json(frame.model_dump())
            await asyncio.sleep(0.1)  # 10fps for demo visibility
        # send final frame with LLM grader result
        final_frame = episode.get_final_frame()
        await websocket.send_json(final_frame.model_dump())
    except WebSocketDisconnect:
        episode.cleanup()
```

**CORS config:** Allow `http://localhost:5173` (Vite dev server)

---

## B3 — React Dashboard

**Directory:** `dashboard/`

### B3.1 — Design Language
```css
/* dashboard/src/index.css */
:root {
  --bg-primary: #080810;
  --bg-secondary: #0d0d1a;
  --bg-card: #12121f;
  --border: #1e1e3a;
  --text-primary: #e8e8f0;
  --text-muted: #6b6b8a;
  --green: #00ff88;
  --yellow: #ffcc00;
  --orange: #ff8800;
  --red: #ff3333;
  --cyan: #00ccff;
  --font-mono: 'JetBrains Mono', monospace;
}
```

### B3.2 — `dashboard/src/components/ServiceGraph.jsx`
D3 force-directed graph. Each node:
- Circle, radius = `8 + (request_rate * 4)`
- Color by health: green → yellow → orange → red
- Pulsing animation on `status === "critical"` or `"down"` via CSS keyframes
- Edge thickness = `dependency_strength * 3`px
- Tooltip on hover: all 6 metrics

Use `useRef` for SVG, `useEffect` for D3 mutations. Re-run D3 simulation only when service count changes, not every frame (use `d3.simulation.alpha(0)` for position updates only).

### B3.3 — `dashboard/src/components/MetricsFeed.jsx`
Three Recharts panels updating every tick:
1. `AreaChart` — system-wide error rate (last 60 ticks)
2. `LineChart` — p99 latency per service (multi-line, max 12 lines)
3. `BarChart` — current CPU usage per service

Use `AnimatePresence` from framer-motion on metric value changes.

### B3.4 — `dashboard/src/components/AgentLog.jsx`
Scrolling terminal-style log. Each entry:
```
[tick 012] ROLLBACK_DEPLOY(service_3) → ✅ +0.34
[tick 015] CIRCUIT_BREAKER(service_7) → ⚠️  +0.12
[tick 023] NO_OP() → ❌ -0.05
```
Auto-scroll. Color-code by action type. Show LLM grader reasoning in a bordered box when `episode_done = true`.

### B3.5 — `dashboard/src/components/ScoreCard.jsx`
```
┌─────────────────────────────────────────┐
│  MTTR          BLAST RADIUS    SCORE    │
│  4.3 sec       8.3%            87/100   │
│  ─────────────────────────────────────  │
│  Human avg: 4.2 hr | Agent: 4.3 sec     │
│  Speedup: 3,527x                        │
└─────────────────────────────────────────┘
```
Use CountUp animation for numbers. Terminal green theme.

### B3.6 — `dashboard/src/App.jsx`
Grid layout:
```
┌──────────────────────┬──────────────┐
│   ServiceGraph       │ MetricsFeed  │
│   (D3 force graph)   │ (3 charts)   │
│                      │              │
├──────────────────────┼──────────────┤
│   AgentLog           │ ScoreCard    │
│   (terminal feed)    │ (counters)   │
└──────────────────────┴──────────────┘
```
Top bar: scenario selector + `[Start Episode]` + `[Untrained / Trained]` toggle + WS status dot.

### B3.7 — `dashboard/src/hooks/useEpisodeStream.js`
```javascript
export function useEpisodeStream(scenario, agentMode) {
  const [services, setServices] = useState([]);
  const [agentLog, setAgentLog] = useState([]);
  const [scores, setScores] = useState({});
  const [isConnected, setIsConnected] = useState(false);
  const [episodeDone, setEpisodeDone] = useState(false);

  // Opens WS on start, parses EpisodeFrame JSON, updates all state
  // Reconnects with exponential backoff (100ms → 200ms → 400ms → max 5s)
  // Cleanup on unmount

  return { services, agentLog, scores, isConnected, episodeDone };
}
```

---

## Track B Deliverables Checklist

- [ ] `training/train.py` runs end-to-end with mock env (before Track A env is ready)
- [ ] PPO agent trains on `bad_deploy` (level 1) and achieves > 0.5 mean reward
- [ ] Curriculum advances from level 1 to level 2 automatically
- [ ] Checkpoint saves every 100 epochs to `checkpoints/`
- [ ] `eval.py` outputs EvalReport across all 6 scenarios
- [ ] FastAPI server starts: `uvicorn api.main:app --reload --port 8000`
- [ ] `/health` endpoint returns 200
- [ ] WebSocket streams EpisodeFrame at 10fps during episode
- [ ] Dashboard builds: `npm run build` (no errors)
- [ ] ServiceGraph renders 12 nodes with correct colors
- [ ] Metrics update in real time from WebSocket
- [ ] ScoreCard shows human vs agent comparison
- [ ] Demo mode works: click Scenario → Start → watch agent → see result

---

---

# Integration Milestones

## Milestone 1 — Hour 8: Engine Smoke Test
Person A confirms: `import incident_core` works, `env.reset()` returns `(72,)` obs.
Person B can start training with a mock/stub env until this is ready.

## Milestone 2 — Hour 16: First Training Run
Person B connects real `IncidentEnv` to TorchRL. First `python training/train.py` run starts without crashing. Even 100 steps is enough to confirm integration.

## Milestone 3 — Hour 24: Dashboard Connects to API
Person B's `npm run dev` dashboard successfully shows a service graph updating from WebSocket. Even random data is fine at this point.

## Milestone 4 — Hour 36: Trained Agent in Dashboard
A checkpoint from training is loaded in `api/main.py`. Dashboard shows trained agent resolving incidents visibly better than untrained.

## Milestone 5 — Hour 44: Full Demo Run
End-to-end: select scenario → untrained agent flails → trained agent resolves → LLM grader scores → ScoreCard shows speedup. Rehearse 3 times.

---

# Shared Conventions

## Branch Strategy
```
main          ← integration branch, always runnable
feat/track-a  ← Person A's work
feat/track-b  ← Person B's work
```
Merge to `main` at each milestone. Never merge broken code to `main`.

## Commit Message Format
```
[A] feat: Rust service graph propagation logic
[B] feat: PPO training loop with curriculum
[A] fix: PyO3 binding for step() return tuple
[BOTH] chore: integration milestone 2 complete
```

## Environment Variables (`.env` — never commit)
```
OLLAMA_MODEL=llama3:8b-instruct-q4_K_M
OLLAMA_HOST=http://localhost:11434
API_PORT=8000
DASHBOARD_PORT=5173
CHECKPOINT_DIR=./checkpoints
LOG_DIR=./logs
```

## Logging Standard
Both tracks use Python's `logging` module with format:
```python
logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO
)
```

---

# Demo Script (3 Minutes)

| Time | Action | Talking Point |
|---|---|---|
| 0:00 | Show healthy service graph | "12 microservices, all green, normal traffic" |
| 0:20 | Trigger `cascade_timeout` | "Upstream timeout cascades — 4 services degrading" |
| 0:40 | Run untrained agent | "Random policy — watch it make things worse" |
| 1:10 | Run trained agent (PPO L4) | "Same scenario, trained agent" |
| 1:30 | Point to AgentLog | "It triggered CircuitBreaker first, then Restart — correct triage order" |
| 1:50 | Point to ScoreCard | "MTTR: 4.3 seconds. Human average: 4.2 hours. 3,527x faster." |
| 2:10 | Show LLM grader output | "Llama 3 validates the root cause identification — running locally, no API" |
| 2:30 | Trigger `multi_fault` live | "Two simultaneous failures — agent triages by blast radius" |
| 2:50 | Final slide | "Built on OpenEnv. Rust core. Meta's own TorchRL. Llama 3." |
