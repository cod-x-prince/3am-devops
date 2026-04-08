from __future__ import annotations

import json
from enum import IntEnum

import gymnasium as gym
import numpy as np

from incident_core import RustServiceGraph

from envs.scenarios import get_scenario_config


class ActionType(IntEnum):
    RESTART_SERVICE = 0
    SCALE_UP = 1
    ROLLBACK_DEPLOY = 2
    REROUTE_TRAFFIC = 3
    TOGGLE_FEATURE_FLAG = 4
    TRIGGER_CIRCUIT_BREAKER = 5
    NO_OP = 6


_ACTION_LABELS = {
    ActionType.RESTART_SERVICE: "RestartService",
    ActionType.SCALE_UP: "ScaleUp",
    ActionType.ROLLBACK_DEPLOY: "RollbackDeploy",
    ActionType.REROUTE_TRAFFIC: "RerouteTraffic",
    ActionType.TOGGLE_FEATURE_FLAG: "ToggleFeatureFlag",
    ActionType.TRIGGER_CIRCUIT_BREAKER: "TriggerCircuitBreaker",
    ActionType.NO_OP: "NoOp",
}


class IncidentEnv(gym.Env):
    metadata = {"render_modes": []}

    NUM_SERVICES = 12
    NUM_METRICS = 6
    NUM_ACTION_TYPES = 7

    def __init__(self, scenario: str = "bad_deploy", curriculum_level: int = 1):
        super().__init__()
        self.scenario_cfg = get_scenario_config(scenario)
        self.scenario = scenario
        self.curriculum_level = curriculum_level
        self.graph = RustServiceGraph(scenario, curriculum_level)
        self.max_steps = int(self.scenario_cfg.get("max_steps", 50))
        self.graph.set_max_steps(self.max_steps)

        self.observation_space = gym.spaces.Box(
            low=0.0,
            high=1.0,
            shape=(self.NUM_SERVICES * self.NUM_METRICS,),
            dtype=np.float32,
        )
        self.action_space = gym.spaces.MultiDiscrete(
            [self.NUM_SERVICES, self.NUM_ACTION_TYPES]
        )

        self._tick = 0
        self._cumulative_reward = 0.0
        self._previous_degraded: set[str] = set()
        self._applied_faults: set[int] = set()

    def _obs_to_np(self, obs: object) -> np.ndarray:
        return np.asarray(obs, dtype=np.float32).reshape((72,))

    def _services_payload(self) -> dict:
        payload_raw = self.graph.get_service_states_json()
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        return payload

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        self._tick = 0
        self._cumulative_reward = 0.0
        self._applied_faults.clear()

        self.graph.reset()
        self._apply_scenario_faults_for_tick(0)
        obs = self._obs_to_np(self.graph.get_observation_vector())
        payload = self._services_payload()
        services = payload.get("services", []) if isinstance(payload, dict) else []
        self._previous_degraded = {
            str(s.get("id"))
            for s in services
            if s.get("status") in {"degraded", "critical", "down"}
        }

        info = {
            "scenario": self.scenario,
            "curriculum_level": self.curriculum_level,
            "num_services": self.NUM_SERVICES,
            "services_json": json.dumps(payload),
        }
        return obs, info

    def _apply_scenario_faults_for_tick(self, tick: int) -> None:
        for idx, fault in enumerate(self.scenario_cfg.get("fault_sequence", [])):
            if idx in self._applied_faults:
                continue
            if int(fault.get("tick", 0)) != tick:
                continue
            fault_type = str(fault.get("fault_type", ""))
            target = int(fault.get("target", 0))
            self.graph.inject_fault(fault_type, target)
            self._applied_faults.add(idx)

    def step(self, action):
        target_service_id = int(action[0])
        action_type = int(action[1])

        _, reward, terminated = self.graph.step(target_service_id, action_type)
        reward = float(np.clip(float(reward), -1.0, 1.0))
        self._cumulative_reward += reward
        self._tick = int(self.graph.get_tick())
        self._apply_scenario_faults_for_tick(self._tick)
        obs = self._obs_to_np(self.graph.get_observation_vector())

        payload = self._services_payload()
        services = payload.get("services", []) if isinstance(payload, dict) else []
        degraded_now = {
            str(s.get("id"))
            for s in services
            if s.get("status") in {"degraded", "critical", "down"}
        }
        services_healthy = sum(1 for s in services if s.get("status") == "healthy")
        services_critical = sum(1 for s in services if s.get("status") == "critical")
        services_down = sum(1 for s in services if s.get("status") == "down")
        newly_degraded = len(degraded_now - self._previous_degraded)
        self._previous_degraded = degraded_now

        info = {
            "tick": self._tick,
            "action_taken": f"{_ACTION_LABELS.get(ActionType(action_type), 'NoOp')}(service_{target_service_id})",
            "newly_degraded": int(newly_degraded),
            "services_healthy": int(services_healthy),
            "services_critical": int(services_critical),
            "services_down": int(services_down),
            "cumulative_reward": float(self._cumulative_reward),
            "curriculum_level": self.curriculum_level,
            "scenario": self.scenario,
            "services_json": json.dumps(payload),
        }

        env_terminated = bool(terminated)
        truncated = False
        if self._tick >= self.max_steps and not self.graph.is_resolved():
            truncated = True
            env_terminated = False
        return obs, reward, env_terminated, truncated, info

    def render(self):
        return None

    def close(self):
        return None
