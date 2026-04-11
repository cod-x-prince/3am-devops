"""IncidentEnv - OpenEnv-compatible environment for incident remediation tasks."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

import incident_core
from .scenarios import IncidentTrace, TraceEvent, load_incident_trace
from rewards import composite_reward

NUM_SERVICES = 12
METRICS_PER_SERVICE = 6
CPU_IDX = 0
MEMORY_IDX = 1
ERROR_RATE_IDX = 2
LATENCY_P50_IDX = 3
LATENCY_P99_IDX = 4
REQUEST_RATE_IDX = 5
EXECUTION_MODES = {"benchmark", "reality"}
HIGH_RISK_ACTION_TYPES = {2, 4}  # RollbackDeploy, ToggleFeatureFlag
ACTION_COOLDOWN_STEPS: dict[int, int] = {
    0: 1,  # RestartService
    1: 2,  # ScaleUp
    2: 3,  # RollbackDeploy
    3: 2,  # RerouteTraffic
    4: 3,  # ToggleFeatureFlag
    5: 2,  # TriggerCircuitBreaker
}


class IncidentEnv(gym.Env):
    """Incident remediation environment with 12 microservices."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        scenario: str = "bad_deploy",
        curriculum_level: int = 1,
        max_steps: int = 50,
        execution_mode: str = "benchmark",
        trace_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__()

        self.scenario = scenario
        self.curriculum_level = curriculum_level
        self.max_steps = max_steps
        self.execution_mode = self._validate_execution_mode(execution_mode)
        self.trace_id = trace_id
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

        self._trace: IncidentTrace | None = None
        self._trace_events_by_step: dict[int, list[TraceEvent]] = {}
        self._trace_events_applied: list[dict[str, Any]] = []
        self._incident_started_at: datetime | None = None
        self._current_timestamp: datetime | None = None
        self._resolved_at: datetime | None = None
        self._customer_impact_minutes = 0.0
        self._action_cooldowns: dict[tuple[int, int], int] = {}
        self._audit_log: list[dict[str, Any]] = []

    @staticmethod
    def _validate_execution_mode(mode: str) -> str:
        normalized = mode.strip().lower()
        if normalized not in EXECUTION_MODES:
            raise ValueError(
                f"execution_mode must be one of {sorted(EXECUTION_MODES)}, got '{mode}'"
            )
        return normalized

    @staticmethod
    def _parse_utc_timestamp(raw: str) -> datetime:
        normalized = raw.strip()
        if normalized.endswith("Z"):
            normalized = normalized.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _utc_iso(dt: datetime | None) -> str | None:
        if dt is None:
            return None
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

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

    def _seed_active_faults_for_mode(self) -> None:
        self._trace = None
        self._trace_events_by_step = {}
        self._trace_events_applied = []
        self._incident_started_at = None
        self._current_timestamp = None
        self._resolved_at = None

        if self.execution_mode != "reality":
            self._active_faults = self._initial_faults()
            return

        trace = load_incident_trace(self.scenario, self.trace_id)
        self._trace = trace
        self.trace_id = trace.trace_id
        self._trace_events_by_step = trace.event_index()
        self._incident_started_at = self._parse_utc_timestamp(trace.started_at)
        self._current_timestamp = self._incident_started_at
        self._active_faults = {}
        self._apply_trace_events_for_step(0)

    def _apply_trace_events_for_step(self, step: int) -> list[dict[str, Any]]:
        if self.execution_mode != "reality" or self._trace is None:
            return []

        applied: list[dict[str, Any]] = []
        for event in self._trace_events_by_step.get(step, []):
            payload = {
                "kind": event.kind,
                "severity": event.severity,
                "ticket_id": event.ticket_id,
                "metric_signal": event.metric_signal,
                "customer_impact_minutes": event.customer_impact_minutes,
                "escalation_risk": event.escalation_risk,
                "log_excerpt": event.log_excerpt,
            }
            existing = self._active_faults.get(event.service_id)
            if existing is None:
                self._active_faults[event.service_id] = payload
            else:
                existing["severity"] = max(float(existing["severity"]), event.severity)
                existing["customer_impact_minutes"] = max(
                    float(existing.get("customer_impact_minutes", 0.0)),
                    event.customer_impact_minutes,
                )
                existing["escalation_risk"] = max(
                    float(existing.get("escalation_risk", 0.0)),
                    event.escalation_risk,
                )
                existing["ticket_id"] = event.ticket_id
                existing["metric_signal"] = event.metric_signal
                existing["log_excerpt"] = event.log_excerpt

            event_payload = event.as_dict()
            applied.append(event_payload)
            self._trace_events_applied.append(event_payload)
        return applied

    def _total_fault_severity(self) -> float:
        return sum(
            float(payload.get("severity", 0.0))
            for payload in self._active_faults.values()
        )

    def _dependency_signal_present(self, service_id: int) -> bool:
        if service_id <= 0 or self._last_obs is None:
            return False
        upstream_id = service_id - 1
        if upstream_id in self._active_faults:
            return True
        return not self._is_service_healthy(self._last_obs, upstream_id)

    def _justification_matches_symptoms(self, justification: str) -> bool:
        text = justification.lower()
        tokens: set[str] = set()
        for payload in self._active_faults.values():
            kind = str(payload.get("kind", "")).strip().lower()
            if kind:
                tokens.add(kind)

            metric = str(payload.get("metric_signal", "")).strip().lower()
            if metric:
                tokens.add(metric)
                tokens.update(segment for segment in metric.split("_") if segment)

        if not tokens:
            return True
        return any(token in text for token in tokens)

    def _validate_reality_action(
        self, service_id: int, action_type: int, action_context: dict[str, Any] | None
    ) -> str | None:
        if self.execution_mode != "reality" or action_type == 6:
            return None

        cooldown = self._action_cooldowns.get((service_id, action_type), 0)
        if cooldown > 0:
            return f"cooldown_active_{cooldown}_step"

        context = action_context or {}
        approval_token = str(context.get("approval_token", "")).strip()
        justification = str(context.get("justification", "")).strip()

        if action_type in HIGH_RISK_ACTION_TYPES and not approval_token:
            return "approval_required_for_high_risk_action"
        if not justification:
            return "justification_required_in_reality_mode"
        if len(justification) < 16:
            return "justification_too_short"
        if not self._justification_matches_symptoms(justification):
            return "justification_not_aligned_with_symptoms"

        if action_type in {3, 5} and not self._dependency_signal_present(service_id):
            return "dependency_check_failed_no_upstream_signal"

        current_unhealthy = (
            self._count_unhealthy(self._last_obs) if self._last_obs is not None else 0
        )
        if action_type in HIGH_RISK_ACTION_TYPES and current_unhealthy >= 8:
            return "blast_radius_gate_denied_action"

        return None

    def _decrement_cooldowns(self) -> None:
        next_state: dict[tuple[int, int], int] = {}
        for key, value in self._action_cooldowns.items():
            if value > 1:
                next_state[key] = value - 1
        self._action_cooldowns = next_state

    def _active_customer_impact_per_step(self) -> float:
        if self.execution_mode != "reality" or self._trace is None:
            return 0.0
        impact_signal = sum(
            float(payload.get("customer_impact_minutes", 0.0))
            for payload in self._active_faults.values()
        )
        return (impact_signal / 10.0) * self._trace.step_minutes

    def _current_mttr_minutes(self) -> float:
        if self.execution_mode != "reality" or self._trace is None:
            return float(self._step_count)
        if self._incident_started_at is None:
            return float(self._step_count) * self._trace.step_minutes

        end_time = (
            self._resolved_at or self._current_timestamp or self._incident_started_at
        )
        elapsed = end_time - self._incident_started_at
        return max(0.0, elapsed.total_seconds() / 60.0)

    def _operational_scores(self, current_unhealthy: int) -> dict[str, float]:
        false_positive_rate = float(self._false_positives) / float(
            max(1, self._total_actions)
        )
        slo_recovery = max(0.0, 1.0 - float(current_unhealthy) / float(NUM_SERVICES))
        mttr_minutes = self._current_mttr_minutes()

        if self.execution_mode == "reality" and self._trace is not None:
            human_mttr = float(self._trace.human_runbook_mttr_minutes)
            human_wrong_actions = float(self._trace.human_wrong_actions)
            human_escalation_rate = float(self._trace.human_escalation_rate)
        else:
            human_mttr = float(self.max_steps)
            human_wrong_actions = 0.0
            human_escalation_rate = 0.0

        return {
            "mttr_minutes": mttr_minutes,
            "false_positive_rate": false_positive_rate,
            "slo_recovery": slo_recovery,
            "customer_impact_minutes": float(self._customer_impact_minutes),
            "human_mttr_minutes": human_mttr,
            "mttr_delta_vs_human_minutes": human_mttr - mttr_minutes,
            "human_wrong_actions": human_wrong_actions,
            "wrong_action_delta_vs_human": human_wrong_actions
            - float(self._false_positives),
            "human_escalation_rate": human_escalation_rate,
        }

    def _reality_reward(
        self,
        current_unhealthy: int,
        action_effective: bool,
        action_type: int,
        terminated: bool,
    ) -> float:
        scores = self._operational_scores(current_unhealthy)
        human_mttr = max(1.0, float(scores["human_mttr_minutes"]))
        mttr_component = max(0.0, 1.0 - float(scores["mttr_minutes"]) / human_mttr)

        impact_budget = max(1.0, human_mttr * 0.75)
        impact_component = max(
            0.0,
            1.0 - float(scores["customer_impact_minutes"]) / impact_budget,
        )
        false_component = max(0.0, 1.0 - float(scores["false_positive_rate"]))
        slo_component = float(scores["slo_recovery"])

        composite = (
            0.35 * mttr_component
            + 0.25 * slo_component
            + 0.2 * false_component
            + 0.2 * impact_component
        )
        reward = 2.0 * composite - 1.0
        if not action_effective and action_type != 6:
            reward -= 0.08
        if terminated:
            reward += 0.15
        return float(max(-1.0, min(1.0, reward)))

    def _append_audit_entry(
        self,
        *,
        service_id: int,
        action_type: int,
        action_effective: bool,
        false_positive: bool,
        action_error: str | None,
        action_context: dict[str, Any] | None,
        current_unhealthy: int,
        measured_recovery: float,
        trace_events: list[dict[str, Any]],
    ) -> None:
        context = action_context or {}
        entry = {
            "step": self._step_count,
            "timestamp": self._utc_iso(self._current_timestamp),
            "service_id": service_id,
            "action_type": action_type,
            "action_effective": action_effective,
            "false_positive": false_positive,
            "action_error": action_error,
            "current_unhealthy": current_unhealthy,
            "active_faults": self._list_active_faults(),
            "measured_recovery": measured_recovery,
            "execution_mode": self.execution_mode,
            "approval_token_present": bool(
                str(context.get("approval_token", "")).strip()
            ),
            "justification": str(context.get("justification", "")),
            "operator_id": str(context.get("operator_id", "")),
            "trace_events": trace_events,
        }
        self._audit_log.append(entry)
        if len(self._audit_log) > 500:
            self._audit_log = self._audit_log[-500:]

    def _list_active_faults(self) -> list[dict[str, Any]]:
        faults: list[dict[str, Any]] = []
        for service_id, payload in sorted(
            self._active_faults.items(), key=lambda item: item[0]
        ):
            fault_payload: dict[str, Any] = {
                "service_id": service_id,
                "kind": str(payload["kind"]),
                "severity": round(float(payload["severity"]), 4),
            }
            for optional_key in (
                "ticket_id",
                "metric_signal",
                "customer_impact_minutes",
                "escalation_risk",
                "log_excerpt",
            ):
                if optional_key in payload:
                    fault_payload[optional_key] = payload[optional_key]
            faults.append(fault_payload)
        return faults

    def _service_health(self, obs: np.ndarray, service_id: int) -> float:
        cpu = self._metric(obs, service_id, CPU_IDX)
        memory = self._metric(obs, service_id, MEMORY_IDX)
        error_rate = self._metric(obs, service_id, ERROR_RATE_IDX)
        return float(
            max(0.0, min(1.0, 1.0 - (0.4 * error_rate + 0.3 * cpu + 0.3 * memory)))
        )

    def _count_unhealthy(self, obs: np.ndarray) -> int:
        return sum(
            1
            for service_id in range(NUM_SERVICES)
            if self._service_health(obs, service_id) < 0.85
        )

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
                self._set_metric(
                    adjusted, service_id, ERROR_RATE_IDX, 0.2 + 0.7 * severity
                )
                self._set_metric(adjusted, service_id, CPU_IDX, 0.35 + 0.5 * severity)
                self._set_metric(
                    adjusted, service_id, MEMORY_IDX, 0.35 + 0.35 * severity
                )
                self._set_metric(
                    adjusted, service_id, LATENCY_P99_IDX, 0.2 + 0.65 * severity
                )
            elif kind == "memory":
                self._set_metric(
                    adjusted, service_id, MEMORY_IDX, 0.45 + 0.5 * severity
                )
                self._set_metric(adjusted, service_id, CPU_IDX, 0.2 + 0.45 * severity)
                self._set_metric(
                    adjusted, service_id, ERROR_RATE_IDX, 0.05 + 0.45 * severity
                )
                self._set_metric(
                    adjusted, service_id, LATENCY_P99_IDX, 0.15 + 0.4 * severity
                )
            elif kind == "timeout":
                self._set_metric(
                    adjusted, service_id, LATENCY_P50_IDX, 0.25 + 0.6 * severity
                )
                self._set_metric(
                    adjusted, service_id, LATENCY_P99_IDX, 0.35 + 0.6 * severity
                )
                self._set_metric(
                    adjusted, service_id, ERROR_RATE_IDX, 0.08 + 0.5 * severity
                )
                self._set_metric(adjusted, service_id, CPU_IDX, 0.25 + 0.25 * severity)
            elif kind == "traffic":
                self._set_metric(
                    adjusted, service_id, REQUEST_RATE_IDX, 0.6 + 0.4 * severity
                )
                self._set_metric(adjusted, service_id, CPU_IDX, 0.3 + 0.5 * severity)
                self._set_metric(
                    adjusted, service_id, LATENCY_P99_IDX, 0.2 + 0.45 * severity
                )
                self._set_metric(
                    adjusted, service_id, ERROR_RATE_IDX, 0.05 + 0.35 * severity
                )
            elif kind == "split":
                self._set_metric(
                    adjusted, service_id, ERROR_RATE_IDX, 0.2 + 0.6 * severity
                )
                self._set_metric(
                    adjusted, service_id, LATENCY_P50_IDX, 0.2 + 0.5 * severity
                )
                self._set_metric(
                    adjusted, service_id, LATENCY_P99_IDX, 0.35 + 0.5 * severity
                )
                self._set_metric(
                    adjusted, service_id, REQUEST_RATE_IDX, 0.15 + 0.45 * severity
                )

        return adjusted

    def _apply_action_to_faults(
        self,
        service_id: int,
        action_type: int,
        action_context: dict[str, Any] | None = None,
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

        reality_guard_error = self._validate_reality_action(
            service_id, action_type, action_context
        )
        if reality_guard_error is not None:
            return False, True, reality_guard_error

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

        self._action_cooldowns[(service_id, action_type)] = ACTION_COOLDOWN_STEPS.get(
            action_type, 1
        )
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

            if (
                kind == "timeout"
                and self.scenario in {"cascade_timeout", "multi_fault"}
                and next_severity >= 0.55
            ):
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
                        existing["severity"] = max(
                            float(existing["severity"]), round(propagated, 4)
                        )

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
            health = float(
                max(0.0, min(1.0, 1.0 - (0.4 * error_rate + 0.3 * cpu + 0.3 * memory)))
            )
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

        if options is not None and "execution_mode" in options:
            self.execution_mode = self._validate_execution_mode(
                str(options["execution_mode"])
            )
        if options is not None and "trace_id" in options:
            raw_trace = options["trace_id"]
            self.trace_id = str(raw_trace) if raw_trace else None

        base_obs = np.array(self.engine.reset(), dtype=np.float32)
        self._step_count = 0
        self._seed_active_faults_for_mode()
        self._false_positives = 0
        self._total_actions = 0
        self._last_action_error = None
        self._last_reward = 0.0
        self._last_terminated = False
        self._last_truncated = False
        self._customer_impact_minutes = 0.0
        self._action_cooldowns = {}
        self._audit_log = []

        self._last_obs = self._apply_fault_overlay(base_obs)
        self._previous_unhealthy = self._count_unhealthy(self._last_obs)
        operational_scores = self._operational_scores(self._previous_unhealthy)

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
            "execution_mode": self.execution_mode,
            "trace_id": self._trace.trace_id if self._trace is not None else None,
            "trace_started_at": (
                self._trace.started_at if self._trace is not None else None
            ),
            "trace_sources": self._trace.sources if self._trace is not None else {},
            "operational_scores": operational_scores,
            "audit_log_size": 0,
            "services_json": self._make_services_json(self._last_obs),
        }
        self._last_info = dict(info)
        return self._last_obs.copy(), info

    def step(
        self,
        action: np.ndarray | list[int],
        action_context: dict[str, Any] | None = None,
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
        if (
            self.execution_mode == "reality"
            and self._trace is not None
            and self._incident_started_at is not None
        ):
            self._current_timestamp = self._incident_started_at + timedelta(
                minutes=self._step_count * self._trace.step_minutes
            )

        severity_before_action = self._total_fault_severity()

        action_effective, false_positive, action_error = self._apply_action_to_faults(
            service_id, action_type, action_context
        )

        if self._active_faults:
            self._advance_faults()
        self._decrement_cooldowns()
        applied_trace_events = self._apply_trace_events_for_step(self._step_count)

        obs = self._apply_fault_overlay(np.array(base_obs, dtype=np.float32))
        current_unhealthy = self._count_unhealthy(obs)
        severity_after_action = self._total_fault_severity()
        measurable_recovery = max(0.0, severity_before_action - severity_after_action)

        if (
            self.execution_mode == "reality"
            and action_type != 6
            and action_effective
            and measurable_recovery <= 1e-6
            and current_unhealthy >= self._previous_unhealthy
        ):
            action_effective = False
            false_positive = True
            action_error = "action_without_measurable_recovery"

        if false_positive:
            self._false_positives += 1
            if action_error is None and self._is_service_healthy(
                self._last_obs, service_id
            ):
                action_error = "action_on_healthy_service"
        self._last_action_error = action_error
        self._customer_impact_minutes += self._active_customer_impact_per_step()

        terminated = len(self._active_faults) == 0
        truncated = self._step_count >= self.max_steps and not terminated
        if (
            self.execution_mode == "reality"
            and terminated
            and self._resolved_at is None
            and self._current_timestamp is not None
        ):
            self._resolved_at = self._current_timestamp

        if self.execution_mode == "reality":
            reward = self._reality_reward(
                current_unhealthy=current_unhealthy,
                action_effective=action_effective,
                action_type=action_type,
                terminated=terminated,
            )
            if truncated:
                reward = min(reward, -0.6)
        else:
            reward_steps = (
                self._step_count if not self._active_faults else self.max_steps
            )
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
            if truncated:
                reward = min(reward, -0.5)
            reward = float(max(-1.0, min(1.0, reward)))

        operational_scores = self._operational_scores(current_unhealthy)
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
                "execution_mode": self.execution_mode,
                "trace_id": self._trace.trace_id if self._trace is not None else None,
                "trace_started_at": (
                    self._trace.started_at if self._trace is not None else None
                ),
                "current_timestamp": self._utc_iso(self._current_timestamp),
                "trace_events_applied": applied_trace_events,
                "operational_scores": operational_scores,
                "measured_recovery": measurable_recovery,
                "audit_log_size": len(self._audit_log) + 1,
                "services_json": self._make_services_json(obs),
            }
        )

        self._append_audit_entry(
            service_id=service_id,
            action_type=action_type,
            action_effective=action_effective,
            false_positive=false_positive,
            action_error=action_error,
            action_context=action_context,
            current_unhealthy=current_unhealthy,
            measured_recovery=measurable_recovery,
            trace_events=applied_trace_events,
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
            "execution_mode": self.execution_mode,
            "trace_id": (
                self._trace.trace_id if self._trace is not None else self.trace_id
            ),
            "trace_started_at": (
                self._trace.started_at if self._trace is not None else None
            ),
            "current_timestamp": self._utc_iso(self._current_timestamp),
            "observation": self._last_obs.tolist(),
            "last_reward": self._last_reward,
            "terminated": self._last_terminated,
            "truncated": self._last_truncated,
            "info": dict(self._last_info),
            "operational_scores": self._last_info.get("operational_scores", {}),
            "audit_log": list(self._audit_log),
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
