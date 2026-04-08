from __future__ import annotations

import asyncio
import json
import random
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from envs import ActionModel, IncidentEnv, ObservationModel, OpenIncidentEnv, RewardModel
from tasks import TASKS, TASKS_BY_ID

CHECKPOINT_DIR = PROJECT_ROOT / "checkpoints"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
DEFAULT_SCENARIO = "bad_deploy"
VALID_SCENARIOS = {
    "bad_deploy",
    "memory_leak",
    "cascade_timeout",
    "thundering_herd",
    "split_brain",
    "multi_fault",
}


def _resolve_trained_checkpoint() -> Path | None:
    candidates = [CHECKPOINT_DIR / "latest.pt", CHECKPOINT_DIR / "policy_latest.pt"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _load_trained_model(checkpoint_path: Path) -> Any:
    from training.train import ActorCritic

    checkpoint = torch.load(checkpoint_path, map_location=DEVICE)
    model = ActorCritic().to(DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


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


@dataclass
class EpisodeState:
    env: IncidentEnv
    scenario: str
    mode: str
    checkpoint_path: str | None = None
    trained_ready: bool = False
    trained_model: Any | None = None
    cumulative_reward: float = 0.0
    done: bool = False
    stopped: bool = False
    tick: int = 0
    final_result: dict[str, Any] | None = None


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
    app.mount("/dashboard", StaticFiles(directory=dashboard_dist, html=True), name="dashboard")

EPISODES: dict[str, EpisodeState] = {}
OPENENV_SESSION: OpenIncidentEnv | None = None


def _openenv_session() -> OpenIncidentEnv:
    global OPENENV_SESSION
    if OPENENV_SESSION is None:
        OPENENV_SESSION = OpenIncidentEnv(scenario="bad_deploy", max_steps=50)
    return OPENENV_SESSION


def _status_from_health(health: float) -> str:
    if health >= 0.9:
        return "healthy"
    if health >= 0.7:
        return "degraded"
    if health >= 0.4:
        return "critical"
    return "down"


def _build_services_from_obs(obs: list[float] | Any) -> list[ServiceState]:
    services: list[ServiceState] = []
    for index in range(12):
        offset = index * 6
        cpu = float(obs[offset + 0])
        memory = float(obs[offset + 1])
        error_rate = float(obs[offset + 2])
        latency_p99 = float(obs[offset + 4])
        health = float(max(0.0, min(1.0, 1.0 - (0.4 * error_rate + 0.3 * cpu + 0.3 * memory))))
        services.append(
            ServiceState(
                id=f"service_{index}",
                health=health,
                cpu=cpu,
                memory=memory,
                error_rate=error_rate,
                latency_p99=latency_p99,
                status=_status_from_health(health),
            )
        )
    return services


def _build_connections() -> list[Connection]:
    return [
        Connection(
            source=f"service_{index}",
            target=f"service_{index + 1}",
            strength=round(random.uniform(0.3, 0.9), 2),
        )
        for index in range(11)
    ]


def _resolve_reset_scenario(raw_scenario: Any, raw_task: Any) -> str:
    if isinstance(raw_task, str):
        task_spec = TASKS_BY_ID.get(raw_task)
        if task_spec is not None:
            return task_spec.scenario

    if isinstance(raw_scenario, str):
        if raw_scenario in VALID_SCENARIOS:
            return raw_scenario
        task_spec = TASKS_BY_ID.get(raw_scenario)
        if task_spec is not None:
            return task_spec.scenario

    return DEFAULT_SCENARIO


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "status": "ok",
        "name": "IncidentEnv",
        "endpoints": ["/health", "/reset", "/step", "/state", "/scenarios"],
    }


@app.get("/health")
def health() -> dict[str, Any]:
    checkpoint = _resolve_trained_checkpoint()
    return {
        "status": "healthy",
        "model_loaded": checkpoint is not None,
        "checkpoint_path": str(checkpoint) if checkpoint else None,
    }


@app.get("/metadata")
def metadata() -> dict[str, Any]:
    return {
        "name": "IncidentEnv",
        "description": "Autonomous incident remediation environment for microservice failures.",
        "version": "0.1.0",
        "tasks": [
            {
                "id": task.task_id,
                "difficulty": task.difficulty,
                "scenario": task.scenario,
                "max_steps": task.max_steps,
                "description": task.description,
            }
            for task in TASKS
        ],
    }


@app.get("/schema")
def schema() -> dict[str, Any]:
    return {
        "action": ActionModel.model_json_schema(),
        "observation": ObservationModel.model_json_schema(),
        "reward": RewardModel.model_json_schema(),
        "state": {
            "type": "object",
            "description": "JSON-serializable state snapshot returned by GET /state",
        },
    }


@app.post("/mcp")
def mcp(payload: dict[str, Any]) -> dict[str, Any]:
    request_id = payload.get("id")
    method = payload.get("method")

    if method == "initialize":
        result: dict[str, Any] = {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "incidentenv", "version": "0.1.0"},
        }
    elif method == "tools/list":
        result = {"tools": []}
    else:
        result = {}

    return {"jsonrpc": "2.0", "id": request_id, "result": result}


@app.get("/scenarios")
def scenarios() -> list[dict[str, str]]:
    return [
        {"id": "bad_deploy", "label": "Bad Deploy"},
        {"id": "memory_leak", "label": "Memory Leak"},
        {"id": "cascade_timeout", "label": "Cascade Timeout"},
        {"id": "thundering_herd", "label": "Thundering Herd"},
        {"id": "split_brain", "label": "Split Brain"},
        {"id": "multi_fault", "label": "Multi Fault"},
    ]


def _reset_openenv_session(scenario: str) -> dict[str, Any]:
    global OPENENV_SESSION
    if OPENENV_SESSION is not None:
        OPENENV_SESSION.close()
    OPENENV_SESSION = OpenIncidentEnv(scenario=scenario, max_steps=50)
    observation = OPENENV_SESSION.reset()
    return {
        "observation": observation.values,
        "scenario": scenario,
        "state": OPENENV_SESSION.state(),
    }


@app.post("/reset")
async def openenv_reset(request: Request) -> dict[str, Any]:
    scenario = _resolve_reset_scenario(
        request.query_params.get("scenario"),
        request.query_params.get("task") or request.query_params.get("task_id"),
    )

    body: Any = None
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        body = None

    if isinstance(body, dict):
        scenario = _resolve_reset_scenario(
            body.get("scenario"),
            body.get("task") or body.get("task_id"),
        )

    return _reset_openenv_session(scenario)


@app.post("/reset/")
async def openenv_reset_slash(request: Request) -> dict[str, Any]:
    return await openenv_reset(request)


@app.get("/reset")
def openenv_reset_get(scenario: str = DEFAULT_SCENARIO, task: str | None = None) -> dict[str, Any]:
    resolved_scenario = _resolve_reset_scenario(scenario, task)
    return _reset_openenv_session(resolved_scenario)


@app.get("/reset/")
def openenv_reset_get_slash(
    scenario: str = DEFAULT_SCENARIO, task: str | None = None
) -> dict[str, Any]:
    return openenv_reset_get(scenario=scenario, task=task)


@app.post("/step")
def openenv_step(action: ActionModel) -> dict[str, Any]:
    observation, reward, done, info = _openenv_session().step(action)
    return {
        "observation": observation.values,
        "reward": reward.value,
        "done": done,
        "info": info,
    }


@app.post("/step/")
def openenv_step_slash(action: ActionModel) -> dict[str, Any]:
    return openenv_step(action)


@app.get("/state")
def openenv_state() -> dict[str, Any]:
    return _openenv_session().state()


@app.get("/state/")
def openenv_state_slash() -> dict[str, Any]:
    return openenv_state()


@app.post("/episode/start")
def start_episode(req: StartEpisodeRequest) -> dict[str, Any]:
    episode_id = str(uuid.uuid4())
    checkpoint = _resolve_trained_checkpoint()
    trained_ready = checkpoint is not None
    mode = req.mode if req.mode in ("untrained", "trained") else "untrained"
    env = IncidentEnv(scenario=req.scenario, max_steps=50)
    env.reset()

    trained_model: Any | None = None
    if mode == "trained" and checkpoint is not None:
        try:
            trained_model = _load_trained_model(checkpoint)
        except (RuntimeError, KeyError, OSError):
            trained_ready = False

    EPISODES[episode_id] = EpisodeState(
        env=env,
        scenario=req.scenario,
        mode=mode,
        checkpoint_path=str(checkpoint) if checkpoint else None,
        trained_ready=trained_ready,
        trained_model=trained_model,
    )

    payload = {
        "episode_id": episode_id,
        "scenario": req.scenario,
        "mode": mode,
        "trained_ready": trained_ready,
        "checkpoint_path": str(checkpoint) if checkpoint else None,
    }
    if mode == "trained" and not trained_ready:
        payload["warning"] = "trained mode requested but checkpoint loading failed; using random policy"
    return payload


@app.post("/episode/stop/{episode_id}")
def stop_episode(episode_id: str) -> dict[str, Any]:
    state = EPISODES.get(episode_id)
    if state is None:
        raise HTTPException(status_code=404, detail="episode not found")
    state.stopped = True
    return {"episode_id": episode_id, "stopped": True}


@app.get("/episode/result/{episode_id}")
def episode_result(episode_id: str) -> dict[str, Any]:
    state = EPISODES.get(episode_id)
    if state is None:
        raise HTTPException(status_code=404, detail="episode not found")
    if state.final_result is None:
        raise HTTPException(status_code=409, detail="episode not completed")
    return state.final_result


@app.websocket("/episode/stream/{episode_id}")
async def episode_stream(websocket: WebSocket, episode_id: str) -> None:
    state = EPISODES.get(episode_id)
    if state is None:
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
                    svc_action = int(torch.argmax(svc_logits, dim=-1).item())
                    act_action = int(torch.argmax(act_logits, dim=-1).item())
                    action = [svc_action, act_action]
            else:
                sampled = state.env.action_space.sample()
                action = [int(sampled[0]), int(sampled[1])]

            obs, reward, terminated, truncated, info = state.env.step(action)
            state.tick += 1
            state.cumulative_reward += float(reward)
            state.done = bool(terminated or truncated)

            services = _build_services_from_obs(obs)
            connections = _build_connections()

            raw_services = info.get("services_json")
            if isinstance(raw_services, str):
                try:
                    parsed = json.loads(raw_services)
                except json.JSONDecodeError:
                    parsed = {}
                if isinstance(parsed, dict) and isinstance(parsed.get("services"), list):
                    services = [ServiceState(**item) for item in parsed["services"]]
                if isinstance(parsed, dict) and isinstance(parsed.get("connections"), list):
                    connections = [Connection(**item) for item in parsed["connections"]]

            frame = EpisodeFrame(
                tick=state.tick,
                services=services,
                connections=connections,
                last_action=f"action_{action[1]}",
                last_action_target=f"service_{action[0]}",
                cumulative_reward=state.cumulative_reward,
                episode_done=state.done,
                resolution_status="resolved" if state.done else "in_progress",
                scores={
                    "mttr": float(max(0.0, 1.0 - state.tick / 50.0)),
                    "blast_radius": float(max(0.0, 1.0 - info.get("current_unhealthy", 0) / 12.0)),
                    "false_alarm_count": float(info.get("false_positives", 0)),
                },
                llm_reasoning=None,
            )
            await websocket.send_json(frame.model_dump())

            if state.done:
                state.final_result = {
                    "episode_id": episode_id,
                    "scenario": state.scenario,
                    "mode": state.mode,
                    "trained_ready": state.trained_ready,
                    "checkpoint_path": state.checkpoint_path,
                    "ticks": state.tick,
                    "cumulative_reward": state.cumulative_reward,
                    "resolution_status": "resolved",
                }
                break

            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        return
