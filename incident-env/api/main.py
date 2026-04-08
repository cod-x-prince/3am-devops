from __future__ import annotations

import asyncio
import json
import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.mock_env import MockIncidentEnv

CHECKPOINT_DIR = PROJECT_ROOT / "checkpoints"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ── Shared env state for /reset + /step ──────────────────────────────────────
_env: MockIncidentEnv | None = None
_current_task_id: str | None = None
_current_scenario: str | None = None

TASKS = [
    {"id": "bad_deploy_easy",        "scenario": "bad_deploy",       "difficulty": "easy",   "grader": "programmatic", "reward_range": [0.0, 1.0]},
    {"id": "cascade_timeout_medium", "scenario": "cascade_timeout",  "difficulty": "medium", "grader": "programmatic", "reward_range": [0.0, 1.0]},
    {"id": "multi_fault_hard",       "scenario": "multi_fault",      "difficulty": "hard",   "grader": "programmatic", "reward_range": [0.0, 1.0]},
]
SCENARIOS = ["bad_deploy", "memory_leak", "cascade_timeout", "thundering_herd", "split_brain", "multi_fault"]


def _resolve_trained_checkpoint() -> Path | None:
    for name in ("latest.pt", "policy_latest.pt"):
        p = CHECKPOINT_DIR / name
        if p.exists():
            return p
    return None


# ── Request / Response models ─────────────────────────────────────────────────

class ResetRequest(BaseModel):
    seed: int | None = None
    scenario: str | None = None
    task_id: str | None = None

class StepRequest(BaseModel):
    action: list[int]  # [service_idx, action_type]  MultiDiscrete [12, 7]

class StartEpisodeRequest(BaseModel):
    scenario: str = "bad_deploy"
    mode: str = "untrained"

class ServiceState(BaseModel):
    id: str
    health: float
    cpu: float
    memory: float
    error_rate: float
    latency_p99: float
    status: str

class Connection(BaseModel):
    source: str
    target: str
    strength: float

class EpisodeFrame(BaseModel):
    tick: int
    services: list[ServiceState]
    connections: list[Connection]
    last_action: str | None
    last_action_target: str | None
    cumulative_reward: float
    episode_done: bool
    resolution_status: str
    scores: dict[str, float]
    llm_reasoning: str | None


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="IncidentEnv API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

dashboard_dist = PROJECT_ROOT / "dashboard" / "dist"
if dashboard_dist.exists():
    app.mount("/ui", StaticFiles(directory=dashboard_dist, html=True), name="dashboard")

EPISODES: dict[str, object] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _status_from_health(h: float) -> str:
    if h >= 0.9: return "healthy"
    if h >= 0.7: return "degraded"
    if h >= 0.4: return "critical"
    return "down"

def _build_services(obs) -> list[ServiceState]:
    services = []
    for i in range(12):
        o = i * 6
        cpu        = float(obs[o + 0])
        memory     = float(obs[o + 1])
        error_rate = float(obs[o + 2])
        latency    = float(obs[o + 4])
        health     = float(max(0.0, min(1.0, 1.0 - (0.4*error_rate + 0.3*cpu + 0.3*memory))))
        services.append(ServiceState(
            id=f"service_{i}", health=health, cpu=cpu,
            memory=memory, error_rate=error_rate,
            latency_p99=latency, status=_status_from_health(health),
        ))
    return services

def _build_connections() -> list[Connection]:
    return [
        Connection(source=f"service_{i}", target=f"service_{i+1}",
                   strength=round(random.uniform(0.3, 0.9), 2))
        for i in range(11)
    ]

def _task_for_id(task_id: str) -> dict | None:
    return next((t for t in TASKS if t["id"] == task_id), None)

def _scenario_for_task(task_id: str) -> str | None:
    t = _task_for_id(task_id)
    return t["scenario"] if t else None


# ── OpenEnv Core Endpoints ────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "name": "IncidentEnv",
        "version": "0.1.0",
        "status": "ok",
        "endpoints": ["/reset", "/step", "/scenarios", "/tasks", "/health"]
    }

@app.post("/reset")
def reset(req: ResetRequest | None = None):
    """OpenEnv reset — returns initial observation."""
    global _env, _current_task_id, _current_scenario

    scenario = None
    task_id  = None

    if req:
        task_id  = req.task_id
        scenario = req.scenario

    # Resolve scenario from task_id if provided
    if task_id and not scenario:
        scenario = _scenario_for_task(task_id)

    # Fallback
    if not scenario:
        scenario = "bad_deploy"

    _current_task_id  = task_id
    _current_scenario = scenario

    seed = req.seed if req else None
    _env = MockIncidentEnv(max_steps=50)

    if seed is not None:
        obs, _ = _env.reset(seed=seed)
    else:
        obs, _ = _env.reset()

    return {"observation": obs.tolist()}


@app.post("/step")
def step(req: StepRequest):
    """OpenEnv step — takes action, returns (obs, reward, terminated, truncated, info)."""
    global _env
    if _env is None:
        raise HTTPException(status_code=400, detail="Call /reset before /step")

    action = req.action
    if len(action) != 2:
        raise HTTPException(status_code=422, detail="action must be [service_idx, action_type]")

    obs, reward, terminated, truncated, info = _env.step(action)

    return {
        "observation": obs.tolist(),
        "reward": float(reward),
        "terminated": bool(terminated),
        "truncated": bool(truncated),
        "info": {k: v for k, v in info.items() if isinstance(v, (int, float, str, bool))},
    }


@app.get("/scenarios")
def scenarios():
    """List available scenarios with metadata."""
    return [
        {"id": s, "name": s.replace("_", " ").title()}
        for s in SCENARIOS
    ]


@app.get("/tasks")
def tasks():
    """List available tasks."""
    return TASKS


@app.get("/health")
def health():
    checkpoint = _resolve_trained_checkpoint()
    return {
        "status": "ok",
        "model_loaded": checkpoint is not None,
        "checkpoint_path": str(checkpoint) if checkpoint else None,
        "env_ready": _env is not None,
        "current_scenario": _current_scenario,
        "current_task_id": _current_task_id,
    }


# ── Dashboard Episode Endpoints (unchanged) ───────────────────────────────────

@dataclass
class EpisodeState:
    env: MockIncidentEnv
    scenario: str
    mode: str
    checkpoint_path: str | None = None
    trained_ready: bool = False
    trained_model: object = None
    cumulative_reward: float = 0.0
    done: bool = False
    stopped: bool = False
    tick: int = 0
    final_result: dict | None = None


def _load_trained_model(checkpoint_path: Path):
    from training.train import ActorCritic
    checkpoint = torch.load(checkpoint_path, map_location=DEVICE)
    model = ActorCritic().to(DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


@app.post("/episode/start")
def start_episode(req: StartEpisodeRequest):
    episode_id = str(uuid.uuid4())
    checkpoint = _resolve_trained_checkpoint()
    trained_ready = checkpoint is not None
    mode = req.mode if req.mode in ("untrained", "trained") else "untrained"
    env = MockIncidentEnv(max_steps=50)
    env.reset()

    trained_model = None
    if mode == "trained" and trained_ready:
        try:
            trained_model = _load_trained_model(checkpoint)
        except Exception as e:
            print(f"Failed to load trained model: {e}")
            trained_ready = False

    EPISODES[episode_id] = EpisodeState(
        env=env, scenario=req.scenario, mode=mode,
        checkpoint_path=str(checkpoint) if checkpoint else None,
        trained_ready=trained_ready, trained_model=trained_model,
    )

    payload = {
        "episode_id": episode_id,
        "scenario": req.scenario,
        "mode": mode,
        "trained_ready": trained_ready,
        "checkpoint_path": str(checkpoint) if checkpoint else None,
    }
    if mode == "trained" and not trained_ready:
        payload["warning"] = "trained mode requested but checkpoint not found; falling back to random policy"
    return payload


@app.post("/episode/stop/{episode_id}")
def stop_episode(episode_id: str):
    state = EPISODES.get(episode_id)
    if not state:
        raise HTTPException(status_code=404, detail="episode not found")
    state.stopped = True
    return {"episode_id": episode_id, "stopped": True}


@app.get("/episode/result/{episode_id}")
def episode_result(episode_id: str):
    state = EPISODES.get(episode_id)
    if not state:
        raise HTTPException(status_code=404, detail="episode not found")
    if state.final_result is None:
        raise HTTPException(status_code=409, detail="episode not completed")
    return state.final_result


@app.websocket("/episode/stream/{episode_id}")
async def episode_stream(websocket: WebSocket, episode_id: str):
    state = EPISODES.get(episode_id)
    if not state:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    try:
        obs, _ = state.env.reset()
        while not state.done and not state.stopped:
            if state.trained_model is not None:
                with torch.no_grad():
                    obs_tensor = torch.tensor(obs, dtype=torch.float32, device=DEVICE).unsqueeze(0)
                    svc_logits, act_logits, _ = state.trained_model(obs_tensor)
                    action = [torch.argmax(svc_logits, dim=-1).item(),
                              torch.argmax(act_logits, dim=-1).item()]
            else:
                action = state.env.action_space.sample()

            obs, reward, terminated, truncated, info = state.env.step(action)
            state.tick += 1
            state.cumulative_reward += float(reward)
            state.done = bool(terminated or truncated)

            services = _build_services(obs)
            connections = _build_connections()

            try:
                parsed = json.loads(info.get("services_json", "{}"))
                if isinstance(parsed, dict) and parsed.get("services"):
                    services = [ServiceState(**s) for s in parsed["services"]]
                if isinstance(parsed, dict) and parsed.get("connections"):
                    connections = [Connection(**c) for c in parsed["connections"]]
            except json.JSONDecodeError:
                pass

            frame = EpisodeFrame(
                tick=state.tick, services=services, connections=connections,
                last_action=f"action_{int(action[1])}",
                last_action_target=f"service_{int(action[0])}",
                cumulative_reward=state.cumulative_reward,
                episode_done=state.done,
                resolution_status="resolved" if state.done else "in_progress",
                scores={
                    "mttr": float(max(0.0, 1.0 - state.tick / 50.0)),
                    "blast_radius": float(max(0.0, 1.0 - info.get("newly_degraded", 0) / 12.0)),
                    "false_alarm_count": 0.0,
                },
                llm_reasoning="Mock run completed" if state.done else None,
            )
            await websocket.send_json(frame.model_dump())

            if state.done:
                state.final_result = {
                    "episode_id": episode_id,
                    "scenario": state.scenario,
                    "mode": state.mode,
                    "ticks": state.tick,
                    "cumulative_reward": state.cumulative_reward,
                    "resolution_status": "resolved",
                }
                break

            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        return