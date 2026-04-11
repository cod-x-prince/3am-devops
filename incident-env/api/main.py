from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import logging
from pydantic import BaseModel, Field, ValidationError
from envs import IncidentEnv
from envs.scenarios import list_trace_options
from tasks import TASKS as TASK_SPECS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_DIR = PROJECT_ROOT / "checkpoints"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
ENV_MAX_STEPS = 50
OPENENV_ENTRYPOINT = "envs.openenv_env:OpenIncidentEnv"
logger = logging.getLogger(__name__)

# Shared env state for /reset + /step + /state.
_env: IncidentEnv | None = None
_current_task_id: str | None = None
_current_scenario: str | None = None
_current_execution_mode: str = "benchmark"
_current_trace_id: str | None = None

TASKS = [
    {
        "id": spec.task_id,
        "scenario": spec.scenario,
        "difficulty": spec.difficulty,
        "grader": "programmatic",
        "reward_range": [0.0, 1.0],
    }
    for spec in TASK_SPECS
]
TASKS_BY_ID = {task["id"]: task for task in TASKS}
SCENARIOS = [
    "bad_deploy",
    "memory_leak",
    "cascade_timeout",
    "thundering_herd",
    "split_brain",
    "multi_fault",
]
ACTION_NAMES = [
    "RestartService",
    "ScaleUp",
    "RollbackDeploy",
    "RerouteTraffic",
    "ToggleFeatureFlag",
    "TriggerCircuitBreaker",
    "NoOp",
]
HIGH_RISK_ACTION_TYPES = {2, 4}
FAULT_ACTION_PRIORITY: dict[str, list[int]] = {
    "deploy": [2, 0, 4],  # RollbackDeploy, RestartService, ToggleFeatureFlag
    "memory": [1, 0, 5],  # ScaleUp, RestartService, TriggerCircuitBreaker
    "timeout": [3, 5, 1],  # RerouteTraffic, TriggerCircuitBreaker, ScaleUp
    "traffic": [3, 1, 5],  # RerouteTraffic, ScaleUp, TriggerCircuitBreaker
    "split": [4, 3, 0],  # ToggleFeatureFlag, RerouteTraffic, RestartService
}
AGENT_OPTIONS = [
    {
        "id": "random",
        "label": "Random Agent",
        "description": "Random policy baseline that samples valid actions.",
    },
    {
        "id": "greedy",
        "label": "Greedy Heuristic",
        "description": "Targets the highest-severity active fault with the best known action.",
    },
    {
        "id": "four_stage",
        "label": "4-Stage Agent",
        "description": "Detect -> prioritize -> shortlist -> act (heuristic stage policy).",
    },
    {
        "id": "trained",
        "label": "Trained PPO",
        "description": "Runs a checkpointed PPO policy from training outputs.",
    },
]
MODE_ALIASES = {
    "untrained": "random",
    "random": "random",
    "greedy": "greedy",
    "four-stage": "four_stage",
    "four_stage": "four_stage",
    "fourstage": "four_stage",
    "trained": "trained",
}
EXECUTION_MODE_ALIASES = {
    "benchmark": "benchmark",
    "synthetic": "benchmark",
    "default": "benchmark",
    "reality": "reality",
    "trace": "reality",
}
REQUIRED_RUNTIME_ENDPOINTS = [
    "/",
    "/health",
    "/reset",
    "/step",
    "/state",
    "/metadata",
    "/schema",
    "/mcp",
]
SUPPLEMENTAL_RUNTIME_ENDPOINTS = [
    "/tasks",
    "/scenarios",
    "/models",
    "/episode/options",
    "/backtest/run",
]
PUBLIC_RUNTIME_ENDPOINTS = REQUIRED_RUNTIME_ENDPOINTS + SUPPLEMENTAL_RUNTIME_ENDPOINTS
MCP_METHODS = [
    "ping",
    "health",
    "metadata",
    "schema",
    "tasks",
    "scenarios",
    "models",
    "state",
    "episode_options",
    "backtest",
    "reset",
    "step",
]


def _request_wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept


def _resolve_trained_checkpoint() -> Path | None:
    candidates: list[Path] = []
    if CHECKPOINT_DIR.exists():
        candidates.extend(sorted(CHECKPOINT_DIR.glob("*.pt")))

    for name in ("latest.pt", "policy_latest.pt"):
        for path in candidates:
            if path.name == name:
                return path

    if candidates:
        return candidates[-1]
    return None


def _available_checkpoints() -> list[dict[str, Any]]:
    if not CHECKPOINT_DIR.exists():
        return []

    models: list[dict[str, Any]] = []
    for path in sorted(CHECKPOINT_DIR.glob("*.pt")):
        stat_result = path.stat()
        models.append(
            {
                "name": path.stem,
                "filename": path.name,
                "path": str(path),
                "size_bytes": stat_result.st_size,
                "modified_time": stat_result.st_mtime,
            }
        )
    return models


def _resolve_checkpoint_by_name(checkpoint_name: str | None) -> Path | None:
    if checkpoint_name is None:
        return _resolve_trained_checkpoint()

    if not CHECKPOINT_DIR.exists():
        return None

    requested = checkpoint_name.strip()
    if not requested:
        return None

    for path in CHECKPOINT_DIR.glob("*.pt"):
        if requested in {path.name, path.stem}:
            return path

    return None


class ResetRequest(BaseModel):
    seed: int | None = None
    scenario: str | None = None
    task_id: str | None = None
    execution_mode: str = "benchmark"
    trace_id: str | None = None


class StepRequest(BaseModel):
    action: list[int] = Field(min_length=2, max_length=2)
    justification: str | None = None
    approval_token: str | None = None
    operator_id: str | None = None


class MCPRequest(BaseModel):
    method: str = "ping"
    params: dict[str, Any] = Field(default_factory=dict)
    id: str | int | None = None


class StartEpisodeRequest(BaseModel):
    scenario: str = "bad_deploy"
    mode: str = "random"
    checkpoint_name: str | None = None
    execution_mode: str = "benchmark"
    trace_id: str | None = None


class BacktestRequest(BaseModel):
    agent_mode: str = "greedy"
    scenario: str | None = None
    max_incidents: int = Field(default=50, ge=1, le=200)
    seed: int = 7
    checkpoint: str | None = None


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
    agent_mode: str
    last_action: str | None
    last_action_target: str | None
    cumulative_reward: float
    episode_done: bool
    resolution_status: str
    scores: dict[str, float]
    llm_reasoning: str | None


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


@app.middleware("http")
async def log_requests(request: Request, call_next: Any) -> Any:
    request_id = uuid.uuid4().hex[:8]
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed method=%s path=%s request_id=%s",
            request.method,
            request.url.path,
            request_id,
        )
        raise

    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_complete method=%s path=%s status=%s request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        request_id,
    )
    return response


def _status_from_health(health: float) -> str:
    if health >= 0.9:
        return "healthy"
    if health >= 0.7:
        return "degraded"
    if health >= 0.4:
        return "critical"
    return "down"


def _build_services(observation: list[float]) -> list[ServiceState]:
    services: list[ServiceState] = []
    for service_idx in range(12):
        offset = service_idx * 6
        cpu = float(observation[offset + 0])
        memory = float(observation[offset + 1])
        error_rate = float(observation[offset + 2])
        latency = float(observation[offset + 4])
        health = float(
            max(0.0, min(1.0, 1.0 - (0.4 * error_rate + 0.3 * cpu + 0.3 * memory)))
        )
        services.append(
            ServiceState(
                id=f"service_{service_idx}",
                health=health,
                cpu=cpu,
                memory=memory,
                error_rate=error_rate,
                latency_p99=latency,
                status=_status_from_health(health),
            )
        )
    return services


def _build_connections() -> list[Connection]:
    return [
        Connection(
            source=f"service_{index}", target=f"service_{index + 1}", strength=0.5
        )
        for index in range(11)
    ]


def _task_for_id(task_id: str) -> dict[str, Any] | None:
    return TASKS_BY_ID.get(task_id)


def _scenario_for_task(task_id: str) -> str | None:
    task = _task_for_id(task_id)
    return str(task["scenario"]) if task is not None else None


def _validate_scenario(scenario: str) -> str:
    if scenario not in SCENARIOS:
        raise HTTPException(
            status_code=422,
            detail=f"unknown scenario '{scenario}', expected one of {SCENARIOS}",
        )
    return scenario


def _normalize_episode_mode(mode: str | None) -> str:
    normalized = MODE_ALIASES.get((mode or "random").strip().lower())
    if normalized is None:
        raise HTTPException(
            status_code=422,
            detail=f"unknown mode '{mode}', expected one of {sorted(MODE_ALIASES.keys())}",
        )
    return normalized


def _normalize_execution_mode(mode: str | None) -> str:
    normalized = EXECUTION_MODE_ALIASES.get((mode or "benchmark").strip().lower())
    if normalized is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"unknown execution_mode '{mode}', expected one of "
                f"{sorted(EXECUTION_MODE_ALIASES.keys())}"
            ),
        )
    return normalized


def _trace_catalog_payload() -> dict[str, list[dict[str, Any]]]:
    return {scenario: list_trace_options(scenario=scenario) for scenario in SCENARIOS}


def _active_faults_from_info(info: dict[str, Any]) -> list[dict[str, Any]]:
    raw_faults = info.get("active_faults", [])
    if not isinstance(raw_faults, list):
        return []

    faults: list[dict[str, Any]] = []
    for payload in raw_faults:
        if not isinstance(payload, dict):
            continue

        try:
            service_id = int(payload.get("service_id", 0))
            severity = float(payload.get("severity", 0.0))
        except (TypeError, ValueError):
            continue

        kind = str(payload.get("kind", "unknown")).strip().lower()
        if service_id < 0 or service_id > 11:
            continue

        faults.append(
            {
                "service_id": service_id,
                "kind": kind,
                "severity": max(0.0, min(1.0, severity)),
            }
        )
    return faults


def _action_candidates_for_fault(fault: dict[str, Any]) -> list[list[int]]:
    service_id = int(fault["service_id"])
    action_priority = FAULT_ACTION_PRIORITY.get(str(fault["kind"]), [0, 1, 3])
    return [[service_id, action_type] for action_type in action_priority]


def _greedy_action(info: dict[str, Any]) -> list[int]:
    faults = _active_faults_from_info(info)
    if not faults:
        return [0, 6]

    top_fault = max(
        faults,
        key=lambda fault: (float(fault["severity"]), -int(fault["service_id"])),
    )
    candidates = _action_candidates_for_fault(top_fault)
    return candidates[0] if candidates else [0, 6]


def _four_stage_action(info: dict[str, Any], tick: int) -> list[int]:
    # Stage 1: detect faults from current env info.
    faults = _active_faults_from_info(info)
    if not faults:
        return [0, 6]

    # Stage 2: prioritize by severity.
    prioritized = sorted(
        faults,
        key=lambda fault: (-float(fault["severity"]), int(fault["service_id"])),
    )

    # Stage 3: build shortlist from top two faults.
    shortlist: list[list[int]] = []
    for fault in prioritized[:2]:
        shortlist.extend(_action_candidates_for_fault(fault)[:2])
    if not shortlist:
        return [0, 6]

    # Stage 4: choose action from shortlist based on step parity and recent errors.
    recent_errors = int(info.get("false_positives", 0))
    if recent_errors > 2 and len(shortlist) > 1:
        return shortlist[1]
    return shortlist[tick % len(shortlist)]


def _select_episode_action(
    state: "EpisodeState", observation: Any, info: dict[str, Any]
) -> list[int]:
    if state.mode == "trained" and state.trained_model is not None:
        with torch.no_grad():
            obs_tensor = torch.tensor(
                observation, dtype=torch.float32, device=DEVICE
            ).unsqueeze(0)
            service_logits, action_logits, _ = state.trained_model(obs_tensor)
            return [
                int(torch.argmax(service_logits, dim=-1).item()),
                int(torch.argmax(action_logits, dim=-1).item()),
            ]

    if state.mode == "greedy":
        return _greedy_action(info)
    if state.mode == "four_stage":
        return _four_stage_action(info, state.tick)

    sampled = state.env.action_space.sample()
    return [int(sampled[0]), int(sampled[1])]


def _episode_action_context(
    state: "EpisodeState", action: list[int], info: dict[str, Any]
) -> dict[str, Any] | None:
    if state.execution_mode != "reality":
        return None

    faults = _active_faults_from_info(info)
    if faults:
        top_fault = max(faults, key=lambda fault: float(fault["severity"]))
        symptom = f"{top_fault['kind']} on service_{top_fault['service_id']}"
    else:
        symptom = "observed incident symptoms"

    context: dict[str, Any] = {
        "operator_id": f"episode-agent-{state.mode}",
        "justification": (
            f"Applying {ACTION_NAMES[action[1]]} on service_{action[0]} to mitigate "
            f"{symptom} while reducing escalation risk."
        ),
    }
    if action[1] in HIGH_RISK_ACTION_TYPES:
        context["approval_token"] = (
            f"AUTO-APPROVAL-{state.mode.upper()}-{state.tick + 1}"
        )
    return context


def _ensure_env_initialized() -> IncidentEnv:
    global _env, _current_scenario, _current_task_id, _current_execution_mode, _current_trace_id
    if _env is None:
        _current_scenario = "bad_deploy"
        _current_task_id = None
        _current_execution_mode = "benchmark"
        _current_trace_id = None
        _env = IncidentEnv(
            scenario=_current_scenario,
            max_steps=ENV_MAX_STEPS,
            execution_mode=_current_execution_mode,
            trace_id=_current_trace_id,
        )
        _env.reset()
    return _env


def _metadata_payload() -> dict[str, Any]:
    return {
        "name": "IncidentEnv",
        "version": "0.1.0",
        "entrypoint": OPENENV_ENTRYPOINT,
        "description": "OpenEnv-compatible environment for autonomous incident remediation.",
        "observation_space": {
            "type": "Box",
            "shape": [72],
            "dtype": "float32",
            "low": 0.0,
            "high": 1.0,
        },
        "action_space": {
            "type": "MultiDiscrete",
            "nvec": [12, 7],
        },
        "reward_range": [-1.0, 1.0],
        "max_episode_steps": ENV_MAX_STEPS,
        "tasks": TASKS,
        "scenarios": SCENARIOS,
        "episode_agents": [option["id"] for option in AGENT_OPTIONS],
        "execution_modes": sorted(set(EXECUTION_MODE_ALIASES.values())),
        "trace_catalog": _trace_catalog_payload(),
        "required_endpoints": REQUIRED_RUNTIME_ENDPOINTS,
        "available_models": _available_checkpoints(),
    }


def _schema_payload() -> dict[str, Any]:
    return {
        "observation": {
            "type": "array",
            "length": 72,
            "items": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        "action": {
            "type": "array",
            "length": 2,
            "items": [
                {"name": "service_id", "type": "integer", "minimum": 0, "maximum": 11},
                {"name": "action_type", "type": "integer", "minimum": 0, "maximum": 6},
            ],
        },
        "reward": {"type": "number", "minimum": -1.0, "maximum": 1.0},
        "requests": {
            "reset": ResetRequest.model_json_schema(),
            "step": StepRequest.model_json_schema(),
            "backtest": BacktestRequest.model_json_schema(),
            "mcp": MCPRequest.model_json_schema(),
        },
        "responses": {
            "step": {
                "type": "object",
                "required": [
                    "observation",
                    "reward",
                    "terminated",
                    "truncated",
                    "info",
                ],
            },
            "state": {
                "type": "object",
                "required": [
                    "scenario",
                    "curriculum_level",
                    "step_count",
                    "max_steps",
                    "observation",
                    "last_reward",
                    "terminated",
                    "truncated",
                    "info",
                    "engine_state",
                ],
            },
        },
    }


@app.api_route("/", methods=["GET", "HEAD"], response_model=None)
async def root(request: Request) -> Any:
    if request.method == "GET" and dashboard_dist.exists() and _request_wants_html(request):
        return RedirectResponse(url="/ui", status_code=307)
    return {
        "name": "IncidentEnv",
        "version": "0.1.0",
        "status": "ok",
        "endpoints": PUBLIC_RUNTIME_ENDPOINTS,
    }


@app.post("/reset")
def reset(req: ResetRequest | None = None) -> dict[str, Any]:
    """OpenEnv reset: returns initial observation and reset info."""
    global _env, _current_task_id, _current_scenario, _current_execution_mode, _current_trace_id

    scenario = req.scenario if req else None
    task_id = req.task_id if req else None
    seed = req.seed if req else None
    execution_mode = _normalize_execution_mode(
        req.execution_mode if req else "benchmark"
    )
    trace_id = req.trace_id if req else None

    if task_id and not scenario:
        scenario = _scenario_for_task(task_id)
        if scenario is None:
            raise HTTPException(status_code=422, detail=f"unknown task_id '{task_id}'")
    if not scenario:
        scenario = "bad_deploy"

    scenario = _validate_scenario(scenario)
    _current_task_id = task_id
    _current_scenario = scenario
    _current_execution_mode = execution_mode
    _current_trace_id = trace_id

    _env = IncidentEnv(
        scenario=scenario,
        max_steps=ENV_MAX_STEPS,
        execution_mode=execution_mode,
        trace_id=trace_id,
    )
    try:
        observation, info = _env.reset(seed=seed)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "reset_failed scenario=%s task_id=%s execution_mode=%s trace_id=%s",
            scenario,
            task_id,
            execution_mode,
            trace_id,
        )
        raise HTTPException(status_code=500, detail="environment reset failed") from exc

    _current_trace_id = info.get("trace_id")

    logger.info(
        "environment_reset scenario=%s task_id=%s seed=%s execution_mode=%s trace_id=%s",
        scenario,
        task_id,
        seed,
        execution_mode,
        _current_trace_id,
    )
    return {"observation": observation.tolist(), "info": info}


@app.post("/step")
def step(req: StepRequest) -> dict[str, Any]:
    """OpenEnv step: returns (observation, reward, terminated, truncated, info)."""
    global _env
    if _env is None:
        raise HTTPException(status_code=400, detail="Call /reset before /step")

    action_context = {
        key: value
        for key, value in {
            "justification": req.justification,
            "approval_token": req.approval_token,
            "operator_id": req.operator_id,
        }.items()
        if value is not None
    }

    try:
        observation, reward, terminated, truncated, info = _env.step(
            req.action, action_context=action_context
        )
    except ValueError as exc:
        logger.warning("step_rejected action=%s error=%s", req.action, exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("step_failed action=%s", req.action)
        raise HTTPException(status_code=500, detail="environment step failed") from exc

    return {
        "observation": observation.tolist(),
        "reward": float(reward),
        "terminated": bool(terminated),
        "truncated": bool(truncated),
        "info": info,
    }


@app.get("/state")
def state() -> dict[str, Any]:
    env = _ensure_env_initialized()
    return env.state()


@app.get("/metadata")
def metadata() -> dict[str, Any]:
    return _metadata_payload()


@app.get("/models")
def models() -> dict[str, Any]:
    checkpoint = _resolve_trained_checkpoint()
    return {
        "active_checkpoint": str(checkpoint) if checkpoint else None,
        "available_models": _available_checkpoints(),
    }


@app.post("/backtest/run")
def run_backtest(req: BacktestRequest) -> dict[str, Any]:
    from training.backtest import run_historical_backtest

    agent_mode = _normalize_episode_mode(req.agent_mode)
    try:
        return run_historical_backtest(
            agent_mode=agent_mode,
            scenario=req.scenario,
            max_incidents=req.max_incidents,
            seed=req.seed,
            checkpoint=req.checkpoint,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "backtest_failed agent_mode=%s scenario=%s max_incidents=%s",
            agent_mode,
            req.scenario,
            req.max_incidents,
        )
        raise HTTPException(
            status_code=500, detail="historical backtest failed"
        ) from exc


@app.get("/episode/options")
def episode_options() -> dict[str, Any]:
    checkpoint = _resolve_trained_checkpoint()
    return {
        "scenarios": scenarios(),
        "agents": AGENT_OPTIONS,
        "default_agent": "random",
        "execution_modes": [
            {"id": "benchmark", "label": "Benchmark Mode"},
            {"id": "reality", "label": "Reality Mode"},
        ],
        "default_execution_mode": "benchmark",
        "traces": _trace_catalog_payload(),
        "active_checkpoint": str(checkpoint) if checkpoint else None,
        "available_models": _available_checkpoints(),
    }


@app.get("/schema")
def schema() -> dict[str, Any]:
    return _schema_payload()


@app.get("/scenarios")
def scenarios() -> list[dict[str, str]]:
    return [
        {"id": scenario, "name": scenario.replace("_", " ").title()}
        for scenario in SCENARIOS
    ]


@app.get("/tasks")
def tasks() -> list[dict[str, Any]]:
    return TASKS


@app.get("/health")
def health() -> dict[str, Any]:
    checkpoint = _resolve_trained_checkpoint()
    return {
        "status": "ok",
        "model_loaded": checkpoint is not None,
        "checkpoint_path": str(checkpoint) if checkpoint else None,
        "available_models": _available_checkpoints(),
        "env_ready": _env is not None,
        "current_scenario": _current_scenario,
        "current_task_id": _current_task_id,
        "current_execution_mode": _current_execution_mode,
        "current_trace_id": _current_trace_id,
    }


@app.post("/mcp")
def mcp(req: MCPRequest) -> dict[str, Any]:
    method = req.method.strip().lower()
    static_handlers: dict[str, Any] = {
        "health": health,
        "metadata": metadata,
        "schema": schema,
        "tasks": tasks,
        "scenarios": scenarios,
        "models": models,
        "state": state,
        "episode_options": episode_options,
    }

    try:
        if method == "ping":
            result: Any = health()
        elif method in static_handlers:
            result = static_handlers[method]()
        elif method == "backtest":
            result = run_backtest(BacktestRequest.model_validate(req.params))
        elif method == "reset":
            result = reset(ResetRequest.model_validate(req.params))
        elif method == "step":
            result = step(StepRequest.model_validate(req.params))
        else:
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown method: {req.method}",
                    "available_methods": MCP_METHODS,
                },
            }
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    return {"jsonrpc": "2.0", "id": req.id, "result": result}


@dataclass
class EpisodeState:
    env: IncidentEnv
    scenario: str
    mode: str
    execution_mode: str
    trace_id: str | None = None
    checkpoint_name: str | None = None
    checkpoint_path: str | None = None
    trained_ready: bool = False
    trained_model: object = None
    cumulative_reward: float = 0.0
    done: bool = False
    stopped: bool = False
    tick: int = 0
    final_result: dict[str, Any] | None = None


def _load_trained_model(checkpoint_path: Path) -> object:
    from training.train import ActorCritic

    checkpoint = torch.load(checkpoint_path, map_location=DEVICE)
    model = ActorCritic().to(DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


EPISODES: dict[str, EpisodeState] = {}


@app.post("/episode/start")
def start_episode(req: StartEpisodeRequest) -> dict[str, Any]:
    episode_id = str(uuid.uuid4())
    requested_mode = _normalize_episode_mode(req.mode)
    runtime_mode = requested_mode
    checkpoint = _resolve_checkpoint_by_name(req.checkpoint_name)
    trained_ready = checkpoint is not None
    scenario = _validate_scenario(req.scenario)
    execution_mode = _normalize_execution_mode(req.execution_mode)
    trace_id = req.trace_id

    if req.checkpoint_name is not None and checkpoint is None:
        raise HTTPException(
            status_code=422, detail=f"unknown checkpoint '{req.checkpoint_name}'"
        )

    env = IncidentEnv(
        scenario=scenario,
        max_steps=ENV_MAX_STEPS,
        execution_mode=execution_mode,
        trace_id=trace_id,
    )
    try:
        _, reset_info = env.reset()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "episode_start_failed scenario=%s execution_mode=%s trace_id=%s",
            scenario,
            execution_mode,
            trace_id,
        )
        raise HTTPException(status_code=500, detail="episode start failed") from exc

    warning: str | None = None
    trained_model = None
    if requested_mode == "trained" and trained_ready:
        try:
            trained_model = _load_trained_model(checkpoint)
        except Exception:  # pragma: no cover - runtime fallback path
            logger.exception("failed_to_load_trained_model checkpoint=%s", checkpoint)
            trained_ready = False

    if requested_mode == "trained" and not trained_ready:
        runtime_mode = "random"
        warning = (
            "trained mode requested but no checkpoint is available; using random agent"
        )

    EPISODES[episode_id] = EpisodeState(
        env=env,
        scenario=scenario,
        mode=runtime_mode,
        execution_mode=execution_mode,
        trace_id=reset_info.get("trace_id"),
        checkpoint_name=req.checkpoint_name,
        checkpoint_path=str(checkpoint) if checkpoint else None,
        trained_ready=trained_ready,
        trained_model=trained_model,
    )

    payload: dict[str, Any] = {
        "episode_id": episode_id,
        "scenario": scenario,
        "mode": runtime_mode,
        "requested_mode": requested_mode,
        "execution_mode": execution_mode,
        "trace_id": reset_info.get("trace_id"),
        "trained_ready": trained_ready,
        "checkpoint_path": str(checkpoint) if checkpoint else None,
        "checkpoint_name": req.checkpoint_name,
    }
    if warning is not None:
        payload["warning"] = warning
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
        observation, reset_info = state.env.reset()
        current_info = dict(reset_info)
        while not state.done and not state.stopped:
            action = _select_episode_action(state, observation, current_info)
            action_context = _episode_action_context(state, action, current_info)

            observation, reward, terminated, truncated, info = state.env.step(
                action, action_context=action_context
            )
            current_info = dict(info)
            state.tick += 1
            state.cumulative_reward += float(reward)
            state.done = bool(terminated or truncated)

            services = _build_services(observation.tolist())
            connections = _build_connections()
            try:
                parsed = json.loads(str(info.get("services_json", "{}")))
                if isinstance(parsed, dict) and parsed.get("services"):
                    services = [
                        ServiceState(**service) for service in parsed["services"]
                    ]
                if isinstance(parsed, dict) and parsed.get("connections"):
                    connections = [
                        Connection(**connection) for connection in parsed["connections"]
                    ]
            except json.JSONDecodeError:
                pass

            if terminated:
                resolution_status = "resolved"
            elif truncated:
                resolution_status = "failed"
            else:
                resolution_status = "in_progress"

            operational = info.get("operational_scores", {})
            mttr_score = float(max(0.0, 1.0 - state.tick / ENV_MAX_STEPS))
            blast_score = float(
                max(0.0, 1.0 - float(info.get("current_unhealthy", 0)) / 12.0)
            )
            false_alarm = float(info.get("false_positives", 0.0))
            if isinstance(operational, dict) and operational:
                mttr_minutes = float(operational.get("mttr_minutes", 0.0))
                human_mttr = float(operational.get("human_mttr_minutes", ENV_MAX_STEPS))
                mttr_score = max(0.0, 1.0 - mttr_minutes / max(1.0, human_mttr))
                blast_score = float(operational.get("slo_recovery", blast_score))
                false_alarm = float(
                    operational.get("false_positive_rate", false_alarm)
                    * max(1, state.tick)
                )

            frame = EpisodeFrame(
                tick=state.tick,
                services=services,
                connections=connections,
                agent_mode=state.mode,
                last_action=ACTION_NAMES[action[1]],
                last_action_target=f"service_{action[0]}",
                cumulative_reward=state.cumulative_reward,
                episode_done=state.done,
                resolution_status=resolution_status,
                scores={
                    "mttr": mttr_score,
                    "blast_radius": blast_score,
                    "false_alarm_count": false_alarm,
                    "mttr_minutes": (
                        float(operational.get("mttr_minutes", 0.0))
                        if isinstance(operational, dict)
                        else 0.0
                    ),
                    "customer_impact_minutes": (
                        float(operational.get("customer_impact_minutes", 0.0))
                        if isinstance(operational, dict)
                        else 0.0
                    ),
                },
                llm_reasoning="Episode completed" if state.done else None,
            )
            await websocket.send_json(frame.model_dump())

            if state.done:
                state.final_result = {
                    "episode_id": episode_id,
                    "scenario": state.scenario,
                    "mode": state.mode,
                    "execution_mode": state.execution_mode,
                    "trace_id": state.trace_id,
                    "ticks": state.tick,
                    "cumulative_reward": state.cumulative_reward,
                    "resolution_status": resolution_status,
                    "operational_scores": (
                        operational if isinstance(operational, dict) else {}
                    ),
                }
                break

            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("episode_stream_failed episode_id=%s", episode_id)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
