from __future__ import annotations

import asyncio
import json
import random
import uuid
from dataclasses import dataclass
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

from tests.mock_env import MockIncidentEnv


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
	env: MockIncidentEnv
	scenario: str
	mode: str
	cumulative_reward: float = 0.0
	done: bool = False
	stopped: bool = False
	tick: int = 0
	final_result: dict | None = None


app = FastAPI(title="IncidentEnv API", version="0.1.0")
app.add_middleware(
	CORSMiddleware,
	allow_origins=["http://localhost:5173"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

EPISODES: dict[str, EpisodeState] = {}


def _status_from_health(health: float) -> str:
	if health >= 0.9:
		return "healthy"
	if health >= 0.7:
		return "degraded"
	if health >= 0.4:
		return "critical"
	return "down"


def _build_services_from_obs(obs):
	services = []
	for i in range(12):
		offset = i * 6
		cpu = float(obs[offset + 0])
		memory = float(obs[offset + 1])
		error_rate = float(obs[offset + 2])
		latency_p99 = float(obs[offset + 4])
		health = float(max(0.0, min(1.0, 1.0 - (0.4 * error_rate + 0.3 * cpu + 0.3 * memory))))
		services.append(
			ServiceState(
				id=f"service_{i}",
				health=health,
				cpu=cpu,
				memory=memory,
				error_rate=error_rate,
				latency_p99=latency_p99,
				status=_status_from_health(health),
			)
		)
	return services


def _build_connections():
	connections = []
	for i in range(11):
		connections.append(
			Connection(
				source=f"service_{i}",
				target=f"service_{i + 1}",
				strength=round(random.uniform(0.3, 0.9), 2),
			)
		)
	return connections


@app.get("/health")
def health():
	return {"status": "ok", "ollama": False, "model_loaded": False}


@app.get("/scenarios")
def scenarios():
	return [
		{"id": "bad_deploy", "label": "Bad Deploy"},
		{"id": "memory_leak", "label": "Memory Leak"},
		{"id": "cascade_timeout", "label": "Cascade Timeout"},
	]


@app.post("/episode/start")
def start_episode(req: StartEpisodeRequest):
	episode_id = str(uuid.uuid4())
	env = MockIncidentEnv(max_steps=50)
	env.reset()
	EPISODES[episode_id] = EpisodeState(env=env, scenario=req.scenario, mode=req.mode)
	return {"episode_id": episode_id, "scenario": req.scenario, "mode": req.mode}


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
			action = state.env.action_space.sample()
			obs, reward, terminated, truncated, info = state.env.step(action)
			state.tick += 1
			state.cumulative_reward += float(reward)
			state.done = bool(terminated or truncated)

			services = _build_services_from_obs(obs)
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
				tick=state.tick,
				services=services,
				connections=connections,
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
