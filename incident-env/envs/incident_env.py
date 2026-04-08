"""IncidentEnv - OpenEnv-compatible environment for incident remediation tasks."""

from __future__ import annotations

import json
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

import incident_core
from rewards import composite_reward

NUM_SERVICES = 12
METRICS_PER_SERVICE = 6
CPU_IDX = 0
MEMORY_IDX = 1
ERROR_RATE_IDX = 2
LATENCY_P50_IDX = 3
LATENCY_P99_IDX = 4
REQUEST_RATE_IDX = 5


class IncidentEnv(gym.Env):
    """Incident remediation environment with 12 microservices."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        scenario: str = "bad_deploy",
        curriculum_level: int = 1,
        max_steps: int = 50,
        **kwargs: Any,
    ) -> None:
        super().__init__()

        self.scenario = scenario
        self.curriculum_level = curriculum_level
        self.max_steps = max_steps
        self.engine = incident_core.RustServiceGraph(scenario, curriculum_level)

        self.observation_space = spaces.Box(
            low=0.0,
            high=1.0,
            shape=(NUM_SERVICES * METRICS_PER_SERVICE,),
            dtype=np.float32,
        )
        self.state_space = self.observation_space
        self.action_space = spaces.MultiDiscrete([NUM_SERVICES, 7])

        self._step_count = 0
        self._last_obs: np.ndarray | None = None
        self._last_reward = 0.0
        self._last_terminated = False
        self._last_truncated = False
        self._last_info: dict[str, Any] = {}
        self._active_faults: dict[int, dict[str, Any]] = {}
        self._false_positives = 0
        self._total_actions = 0
        self._previous_unhealthy = 0
        self._last_action_error: str | None = None

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, value))

    @staticmethod
    def _offset(service_id: int) -> int:
        return service_id * METRICS_PER_SERVICE

    def _metric(self, obs: np.ndarray, service_id: int, metric_index: int) -> float:
        return float(obs[self._offset(service_id) + metric_index])

    def _set_metric(
        self, obs: np.ndarray, service_id: int, metric_index: int, value: float
    ) -> None:
        obs[self._offset(service_id) + metric_index] = self._clamp01(value)

    def _initial_faults(self) -> dict[int, dict[str, Any]]:
        if self.scenario == "bad_deploy":
            return {3: {"kind": "deploy", "severity": 0.95}}
        if self.scenario == "memory_leak":
            return {6: {"kind": "memory", "severity": 0.8}}
        if self.scenario == "cascade_timeout":
            return {1: {"kind": "timeout", "severity": 0.85}}
        if self.scenario == "thundering_herd":
            return {
                0: {"kind": "traffic", "severity": 0.9},
                3: {"kind": "traffic", "severity": 0.65},
            }
        if self.scenario == "split_brain":
            return {
                5: {"kind": "split", "severity": 0.9},
                6: {"kind": "split", "severity": 0.75},
            }
        if self.scenario == "multi_fault":
            return {
                2: {"kind": "deploy", "severity": 0.85},
                8: {"kind": "memory", "severity": 0.85},
                10: {"kind": "timeout", "severity": 0.7},
            }
        return {3: {"kind": "deploy", "severity": 0.95}}

    def _list_active_faults(self) -> list[dict[str, Any]]:
        return [
            {
                "service_id": service_id,
                "kind": str(payload["kind"]),
                "severity": round(float(payload["severity"]), 4),
            }
            for service_id, payload in sorted(self._active_faults.items(), key=lambda item: item[0])
        ]

    def _service_health(self, obs: np.ndarray, service_id: int) -> float:
        cpu = self._metric(obs, service_id, CPU_IDX)
        memory = self._metric(obs, service_id, MEMORY_IDX)
        error_rate = self._metric(obs, service_id, ERROR_RATE_IDX)
        return float(max(0.0, min(1.0, 1.0 - (0.4 * error_rate + 0.3 * cpu + 0.3 * memory))))

    def _count_unhealthy(self, obs: np.ndarray) -> int:
        return sum(1 for service_id in range(NUM_SERVICES) if self._service_health(obs, service_id) < 0.85)

    def _is_service_healthy(self, obs: np.ndarray | None, service_id: int) -> bool:
        if obs is None:
            return False
        return self._service_health(obs, service_id) >= 0.85

    def _apply_fault_overlay(self, obs: np.ndarray) -> np.ndarray:
        adjusted = np.array(obs, dtype=np.float32, copy=True)
        for service_id, fault in self._active_faults.items():
            severity = float(fault["severity"])
            kind = str(fault["kind"])

            if kind == "deploy":
                self._set_metric(adjusted, service_id, ERROR_RATE_IDX, 0.2 + 0.7 * severity)
                self._set_metric(adjusted, service_id, CPU_IDX, 0.35 + 0.5 * severity)
                self._set_metric(adjusted, service_id, MEMORY_IDX, 0.35 + 0.35 * severity)
                self._set_metric(adjusted, service_id, LATENCY_P99_IDX, 0.2 + 0.65 * severity)
            elif kind == "memory":
                self._set_metric(adjusted, service_id, MEMORY_IDX, 0.45 + 0.5 * severity)
                self._set_metric(adjusted, service_id, CPU_IDX, 0.2 + 0.45 * severity)
                self._set_metric(adjusted, service_id, ERROR_RATE_IDX, 0.05 + 0.45 * severity)
                self._set_metric(adjusted, service_id, LATENCY_P99_IDX, 0.15 + 0.4 * severity)
            elif kind == "timeout":
                self._set_metric(adjusted, service_id, LATENCY_P50_IDX, 0.25 + 0.6 * severity)
                self._set_metric(adjusted, service_id, LATENCY_P99_IDX, 0.35 + 0.6 * severity)
                self._set_metric(adjusted, service_id, ERROR_RATE_IDX, 0.08 + 0.5 * severity)
                self._set_metric(adjusted, service_id, CPU_IDX, 0.25 + 0.25 * severity)
            elif kind == "traffic":
                self._set_metric(adjusted, service_id, REQUEST_RATE_IDX, 0.6 + 0.4 * severity)
                self._set_metric(adjusted, service_id, CPU_IDX, 0.3 + 0.5 * severity)
                self._set_metric(adjusted, service_id, LATENCY_P99_IDX, 0.2 + 0.45 * severity)
                self._set_metric(adjusted, service_id, ERROR_RATE_IDX, 0.05 + 0.35 * severity)
            elif kind == "split":
                self._set_metric(adjusted, service_id, ERROR_RATE_IDX, 0.2 + 0.6 * severity)
                self._set_metric(adjusted, service_id, LATENCY_P50_IDX, 0.2 + 0.5 * severity)
                self._set_metric(adjusted, service_id, LATENCY_P99_IDX, 0.35 + 0.5 * severity)
                self._set_metric(adjusted, service_id, REQUEST_RATE_IDX, 0.15 + 0.45 * severity)

        return adjusted

    def _apply_action_to_faults(
        self, service_id: int, action_type: int
    ) -> tuple[bool, bool, str | None]:
        action_effectiveness: dict[str, dict[int, float]] = {
            "deploy": {0: 0.45, 2: 0.7, 4: 0.3},
            "memory": {0: 0.35, 1: 0.55, 5: 0.2},
            "timeout": {1: 0.25, 3: 0.6, 5: 0.65},
            "traffic": {1: 0.25, 3: 0.55, 5: 0.55},
            "split": {0: 0.25, 3: 0.35, 4: 0.55},
        }

        if action_type == 6:
            if self._active_faults:
                return False, True, "noop_while_incident_active"
            return False, False, None

        payload = self._active_faults.get(service_id)
        if payload is None:
            return False, True, "target_service_not_faulty"

        kind = str(payload["kind"])
        reduction = action_effectiveness.get(kind, {}).get(action_type, 0.0)
        if reduction <= 0.0:
            return False, True, "action_not_effective_for_fault_type"

        current = float(payload["severity"])
        next_severity = max(0.0, current - reduction)
        if next_severity <= 0.1:
            del self._active_faults[service_id]
        else:
            self._active_faults[service_id]["severity"] = next_severity

        return True, False, None

    def _advance_faults(self) -> None:
        growth_by_kind = {
            "deploy": 0.01,
            "memory": 0.02,
            "timeout": 0.015,
            "traffic": 0.02,
            "split": 0.017,
        }

        for service_id, payload in list(self._active_faults.items()):
            kind = str(payload["kind"])
            growth = growth_by_kind.get(kind, 0.01)
            next_severity = min(1.0, float(payload["severity"]) + growth)
            self._active_faults[service_id]["severity"] = next_severity

            if kind == "timeout" and self.scenario in {"cascade_timeout", "multi_fault"} and next_severity >= 0.55:
                downstream_id = service_id + 1
                if downstream_id < NUM_SERVICES:
                    propagated = min(0.9, next_severity * 0.55)
                    existing = self._active_faults.get(downstream_id)
                    if existing is None:
                        self._active_faults[downstream_id] = {
                            "kind": "timeout",
                            "severity": round(propagated, 4),
                        }
                    elif str(existing["kind"]) == "timeout":
                        existing["severity"] = max(float(existing["severity"]), round(propagated, 4))

    def _build_connection_snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "source": f"service_{index}",
                "target": f"service_{index + 1}",
                "strength": 0.5,
            }
            for index in range(NUM_SERVICES - 1)
        ]

    def _build_service_snapshot(self, obs: np.ndarray) -> list[dict[str, Any]]:
        services: list[dict[str, Any]] = []
        for index in range(NUM_SERVICES):
            offset = self._offset(index)
            cpu = float(obs[offset + CPU_IDX])
            memory = float(obs[offset + MEMORY_IDX])
            error_rate = float(obs[offset + ERROR_RATE_IDX])
            latency_p99 = float(obs[offset + LATENCY_P99_IDX])
            health = float(max(0.0, min(1.0, 1.0 - (0.4 * error_rate + 0.3 * cpu + 0.3 * memory))))
            if health >= 0.9:
                status = "healthy"
            elif health >= 0.7:
                status = "degraded"
            elif health >= 0.4:
                status = "critical"
            else:
                status = "down"

            services.append(
                {
                    "id": f"service_{index}",
                    "health": health,
                    "cpu": cpu,
                    "memory": memory,
                    "error_rate": error_rate,
                    "latency_p99": latency_p99,
                    "status": status,
                }
            )

        return services

    def _make_services_json(self, obs: np.ndarray) -> str:
        return json.dumps(
            {
                "services": self._build_service_snapshot(obs),
                "connections": self._build_connection_snapshot(),
                "active_faults": self._list_active_faults(),
            }
        )

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Reset the environment to initial state."""
        super().reset(seed=seed)

        base_obs = np.array(self.engine.reset(), dtype=np.float32)
        self._step_count = 0
        self._active_faults = self._initial_faults()
        self._false_positives = 0
        self._total_actions = 0
        self._last_action_error = None
        self._last_reward = 0.0
        self._last_terminated = False
        self._last_truncated = False

        self._last_obs = self._apply_fault_overlay(base_obs)
        self._previous_unhealthy = self._count_unhealthy(self._last_obs)

        info = {
            "scenario": self.scenario,
            "curriculum_level": self.curriculum_level,
            "num_services": NUM_SERVICES,
            "step_count": self._step_count,
            "active_faults": self._list_active_faults(),
            "false_positives": self._false_positives,
            "total_actions": self._total_actions,
            "current_unhealthy": self._previous_unhealthy,
            "last_action_error": None,
            "services_json": self._make_services_json(self._last_obs),
        }
        self._last_info = dict(info)
        return self._last_obs.copy(), info

    def step(
        self, action: np.ndarray | list[int]
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """Execute one step in the environment."""
        if isinstance(action, np.ndarray):
            action = action.tolist()
        if not isinstance(action, list) or len(action) != 2:
            raise ValueError("action must be a list or numpy array with two integers")

        service_id = int(action[0])
        action_type = int(action[1])
        if service_id < 0 or service_id >= NUM_SERVICES:
            raise ValueError("service_id must be in [0, 11]")
        if action_type < 0 or action_type > 6:
            raise ValueError("action_type must be in [0, 6]")

        base_obs, _, _, _, base_info = self.engine.step([service_id, action_type])
        self._step_count += 1
        self._total_actions += 1

        action_effective, false_positive, action_error = self._apply_action_to_faults(
            service_id, action_type
        )
        if false_positive:
            self._false_positives += 1
            if action_error is None and self._is_service_healthy(self._last_obs, service_id):
                action_error = "action_on_healthy_service"
        self._last_action_error = action_error

        if self._active_faults:
            self._advance_faults()

        obs = self._apply_fault_overlay(np.array(base_obs, dtype=np.float32))
        current_unhealthy = self._count_unhealthy(obs)

        reward_steps = self._step_count if not self._active_faults else self.max_steps
        reward = composite_reward(
            steps_to_resolution=reward_steps,
            previous_unhealthy=self._previous_unhealthy,
            current_unhealthy=current_unhealthy,
            false_positives=self._false_positives,
            total_actions=self._total_actions,
            max_steps=self.max_steps,
        )
        if not action_effective and action_type != 6:
            reward = max(-1.0, reward - 0.05)

        terminated = len(self._active_faults) == 0
        truncated = self._step_count >= self.max_steps and not terminated
        if truncated:
            reward = min(reward, -0.5)

        reward = float(max(-1.0, min(1.0, reward)))
        self._previous_unhealthy = current_unhealthy

        info = dict(base_info)
        info.update(
            {
                "step_count": self._step_count,
                "active_faults": self._list_active_faults(),
                "false_positives": self._false_positives,
                "total_actions": self._total_actions,
                "current_unhealthy": current_unhealthy,
                "last_action_error": self._last_action_error,
                "services_json": self._make_services_json(obs),
            }
        )

        self._last_obs = obs
        self._last_reward = reward
        self._last_terminated = terminated
        self._last_truncated = truncated
        self._last_info = dict(info)
        return obs.copy(), reward, terminated, truncated, info

    def state(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the current environment state."""
        if self._last_obs is None:
            baseline = np.array(self.engine.reset(), dtype=np.float32)
            self._last_obs = self._apply_fault_overlay(baseline)

        return {
            "scenario": self.scenario,
            "curriculum_level": self.curriculum_level,
            "step_count": self._step_count,
            "max_steps": self.max_steps,
            "observation": self._last_obs.tolist(),
            "last_reward": self._last_reward,
            "terminated": self._last_terminated,
            "truncated": self._last_truncated,
            "info": dict(self._last_info),
            "engine_state": {
                "services": self._build_service_snapshot(self._last_obs),
                "connections": self._build_connection_snapshot(),
                "active_faults": self._list_active_faults(),
            },
        }

    def render(self) -> None:
        """Render the environment (no-op)."""
        return None

    def close(self) -> None:
        """Clean up resources."""
        return None
