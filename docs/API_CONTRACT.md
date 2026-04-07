# API Contract — IncidentEnv
> The binding agreement between Track A (env) and Track B (training + API)
> **Both people must agree before changing anything in this file**

---

## Observation Space

```python
shape: (72,)          # 12 services × 6 metrics
dtype: np.float32
low:   0.0
high:  1.0            # all metrics normalised to [0, 1]
```

**Metric order per service (6 values each):**
```
index 0:  cpu_usage       (0.0 = idle, 1.0 = maxed)
index 1:  memory_usage    (0.0 = empty, 1.0 = OOM)
index 2:  error_rate      (0.0 = no errors, 1.0 = 100% errors)
index 3:  latency_p50     (0.0 = 0ms, 1.0 = 10,000ms)
index 4:  latency_p99     (0.0 = 0ms, 1.0 = 10,000ms)
index 5:  request_rate    (0.0 = 0 rps, 1.0 = max_rps)
```

**Service ordering in obs vector:**
```
obs[0:6]   → service_0 metrics
obs[6:12]  → service_1 metrics
obs[12:18] → service_2 metrics
...
obs[66:72] → service_11 metrics
```

---

## Action Space

```python
gym.spaces.MultiDiscrete([12, 7])
action[0]: target_service_id  (int, 0–11)
action[1]: action_type        (int, 0–6)
```

**Action type enum:**
```
0 → RestartService
1 → ScaleUp
2 → RollbackDeploy
3 → RerouteTraffic
4 → ToggleFeatureFlag
5 → TriggerCircuitBreaker
6 → NoOp
```

---

## `env.step()` Return Contract

```python
obs, reward, terminated, truncated, info = env.step(action)

# obs:        np.ndarray shape (72,) float32
# reward:     float in [-1.0, 1.0]
# terminated: bool — True if all services healthy (success) or max_steps exceeded (fail)
# truncated:  bool — always False (we use terminated only)
# info:       dict — see below
```

**`info` dict schema:**
```python
{
    "tick": int,
    "action_taken": str,              # e.g. "RestartService(service_3)"
    "newly_degraded": int,            # services that got worse this step
    "services_healthy": int,          # count of healthy services
    "services_critical": int,
    "services_down": int,
    "cumulative_reward": float,
    "curriculum_level": int,
    "scenario": str,
    "services_json": str,             # JSON string of full service states for API
}
```

---

## `env.reset()` Return Contract

```python
obs, info = env.reset(seed=None, options=None)

# obs:  np.ndarray shape (72,) float32 — initial state
# info: dict with "scenario", "curriculum_level", "num_services", "services_json"
```

---

## `services_json` Schema (used by Track B's API)

This is the JSON string inside `info["services_json"]` — Track B's API parses this for WebSocket streaming.

```json
{
  "services": [
    {
      "id": "service_0",
      "health": 0.95,
      "cpu": 0.23,
      "memory": 0.41,
      "error_rate": 0.01,
      "latency_p50": 0.05,
      "latency_p99": 0.12,
      "request_rate": 0.60,
      "status": "healthy"
    }
  ],
  "connections": [
    { "source": "service_0", "target": "service_3", "strength": 0.8 },
    { "source": "service_1", "target": "service_3", "strength": 0.5 }
  ],
  "tick": 12,
  "active_faults": ["BadDeploy(service_3)"]
}
```

**`status` values:** `"healthy"` | `"degraded"` | `"critical"` | `"down"`

---

## WebSocket EpisodeFrame Schema (Track B → Dashboard)

```typescript
interface EpisodeFrame {
  tick: number;
  services: ServiceState[];
  connections: Connection[];
  last_action: string | null;
  last_action_target: string | null;
  cumulative_reward: number;
  episode_done: boolean;
  resolution_status: "in_progress" | "resolved" | "failed";
  scores: {
    mttr: number;
    blast_radius: number;
    false_alarm_count: number;
  };
  llm_reasoning: string | null;  // only when episode_done=true
}

interface ServiceState {
  id: string;
  health: number;
  cpu: number;
  memory: number;
  error_rate: number;
  latency_p99: number;
  status: "healthy" | "degraded" | "critical" | "down";
}

interface Connection {
  source: string;
  target: string;
  strength: number;
}
```

---

## Grader Interface (Track A → Track B)

Track B's `eval.py` calls Track A's graders:

```python
# Programmatic grader
from graders.programmatic import ProgrammaticGrader, GraderResult

grader = ProgrammaticGrader()
result: GraderResult = grader.grade(
    episode_history=list_of_info_dicts,
    final_obs=obs,
    resolved=terminated
)

# LLM grader
from graders.llm_grader import LLMGrader, LLMGraderResult

llm = LLMGrader()
result: LLMGraderResult = llm.grade(
    incident_description="BadDeploy on service_3 at tick 0",
    action_sequence=["RestartService(service_1)", "RollbackDeploy(service_3)"],
    final_service_states=services_json_dict,
    resolved=True
)
```

**`GraderResult` dataclass:**
```python
@dataclass
class GraderResult:
    all_healthy: bool
    resolution_steps: int
    blast_radius_score: float    # 0.0–1.0 (1.0 = no spread)
    false_positive_count: int
    curriculum_level_passed: bool
    overall_score: float         # 0–100
    passed: bool
```

**`LLMGraderResult` dataclass:**
```python
@dataclass
class LLMGraderResult:
    root_cause_identification: int   # 0–10
    remediation_appropriateness: int # 0–10
    blast_radius_minimization: int   # 0–10
    action_efficiency: int           # 0–10
    reasoning: str
    overall: float                   # weighted average 0–10

    @classmethod
    def fallback(cls) -> "LLMGraderResult":
        """Returns a neutral result when Ollama is unavailable."""
        ...
```

---

## Change Protocol

> If either person needs to change anything in this contract:
> 1. Announce the change in your track file's "Messages for Person X" section
> 2. Do NOT change your code until the other person confirms
> 3. Both make the change in the same git commit if possible
> 4. Update this file after both sides are synced

**Known stable:** obs shape `(72,)`, action space `MultiDiscrete([12, 7])` — these were set at project start and should NOT change.
