from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

TRACE_ROOT = Path(__file__).resolve().parents[1] / "scenarios" / "traces"
CONFIG_ROOT = Path(__file__).resolve().parents[1] / "scenarios" / "configs"

FAULT_KIND_MAP: dict[str, str] = {
    "baddeploy": "deploy",
    "memoryleak": "memory",
    "cascadetimeout": "timeout",
    "thunderingherd": "traffic",
    "splitbrain": "split",
}


@dataclass(frozen=True)
class TraceEvent:
    step: int
    service_id: int
    kind: str
    severity: float
    log_excerpt: str
    metric_signal: str
    ticket_id: str
    customer_impact_minutes: float = 0.0
    escalation_risk: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "service_id": self.service_id,
            "kind": self.kind,
            "severity": self.severity,
            "log_excerpt": self.log_excerpt,
            "metric_signal": self.metric_signal,
            "ticket_id": self.ticket_id,
            "customer_impact_minutes": self.customer_impact_minutes,
            "escalation_risk": self.escalation_risk,
        }


@dataclass(frozen=True)
class IncidentTrace:
    trace_id: str
    scenario: str
    started_at: str
    step_minutes: float
    human_runbook_mttr_minutes: float
    human_wrong_actions: int
    human_escalation_rate: float
    sources: dict[str, list[str]]
    events: tuple[TraceEvent, ...]

    def event_index(self) -> dict[int, list[TraceEvent]]:
        index: dict[int, list[TraceEvent]] = {}
        for event in self.events:
            index.setdefault(event.step, []).append(event)
        return index


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalize_kind(kind: str) -> str:
    cleaned = kind.strip().lower().replace("_", "").replace("-", "")
    if cleaned in FAULT_KIND_MAP:
        return FAULT_KIND_MAP[cleaned]
    if kind.strip().lower() in {"deploy", "memory", "timeout", "traffic", "split"}:
        return kind.strip().lower()
    return "deploy"


def _scenario_config_path(scenario: str) -> Path:
    return CONFIG_ROOT / f"{scenario}.json"


def _load_scenario_config(scenario: str) -> dict[str, Any] | None:
    config_path = _scenario_config_path(scenario)
    if not config_path.exists():
        return None
    return json.loads(config_path.read_text(encoding="utf-8"))


def _configured_trace_path(scenario: str) -> Path | None:
    config = _load_scenario_config(scenario)
    if config is None:
        return None
    trace_file = config.get("trace_file")
    if trace_file is None:
        return None
    path = TRACE_ROOT / str(trace_file)
    if not path.exists():
        raise ValueError(
            f"Configured trace file '{trace_file}' not found for scenario '{scenario}'"
        )
    return path


def _parse_event(raw: dict[str, Any], index: int) -> TraceEvent:
    step = int(raw.get("step", index))
    service_id = int(raw.get("service_id", 0))
    kind = _normalize_kind(str(raw.get("kind", "deploy")))
    severity = _clamp(float(raw.get("severity", 0.6)), 0.0, 1.0)
    log_excerpt = str(raw.get("log_excerpt", f"trace-event-{index}"))
    metric_signal = str(raw.get("metric_signal", "error_rate"))
    ticket_id = str(raw.get("ticket_id", f"TICKET-{index:03d}"))
    customer_impact_minutes = max(0.0, float(raw.get("customer_impact_minutes", 0.0)))
    escalation_risk = _clamp(float(raw.get("escalation_risk", 0.0)), 0.0, 1.0)

    return TraceEvent(
        step=step,
        service_id=service_id,
        kind=kind,
        severity=severity,
        log_excerpt=log_excerpt,
        metric_signal=metric_signal,
        ticket_id=ticket_id,
        customer_impact_minutes=customer_impact_minutes,
        escalation_risk=escalation_risk,
    )


def _load_trace_file(path: Path) -> IncidentTrace:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_events = payload.get("events", [])
    events = tuple(
        _parse_event(raw_event, index) for index, raw_event in enumerate(raw_events)
    )

    sources = payload.get("sources", {})
    normalized_sources = {
        "logs": [str(item) for item in sources.get("logs", [])],
        "metrics": [str(item) for item in sources.get("metrics", [])],
        "tickets": [str(item) for item in sources.get("tickets", [])],
    }

    return IncidentTrace(
        trace_id=str(payload.get("trace_id", path.stem)),
        scenario=str(payload.get("scenario", "bad_deploy")),
        started_at=str(payload.get("started_at", "2026-01-01T00:00:00Z")),
        step_minutes=max(0.1, float(payload.get("step_minutes", 1.0))),
        human_runbook_mttr_minutes=max(
            1.0, float(payload.get("human_runbook_mttr_minutes", 60.0))
        ),
        human_wrong_actions=max(0, int(payload.get("human_wrong_actions", 2))),
        human_escalation_rate=_clamp(
            float(payload.get("human_escalation_rate", 0.2)),
            0.0,
            1.0,
        ),
        sources=normalized_sources,
        events=events,
    )


def list_incident_traces(scenario: str | None = None) -> list[IncidentTrace]:
    if not TRACE_ROOT.exists():
        return []

    traces = [_load_trace_file(path) for path in sorted(TRACE_ROOT.glob("*.json"))]
    if scenario is None:
        return traces
    return [trace for trace in traces if trace.scenario == scenario]


def list_trace_options(scenario: str | None = None) -> list[dict[str, Any]]:
    options = [
        {
            "trace_id": trace.trace_id,
            "scenario": trace.scenario,
            "started_at": trace.started_at,
            "event_count": len(trace.events),
            "human_runbook_mttr_minutes": trace.human_runbook_mttr_minutes,
            "human_wrong_actions": trace.human_wrong_actions,
            "human_escalation_rate": trace.human_escalation_rate,
        }
        for trace in list_incident_traces(scenario=scenario)
    ]
    return options


def _trace_from_config(scenario: str) -> IncidentTrace:
    config_payload = _load_scenario_config(scenario)
    if config_payload is None:
        raise ValueError(f"No trace or config found for scenario '{scenario}'")

    fault_sequence = config_payload.get("fault_sequence", [])
    events: list[TraceEvent] = []
    for index, fault in enumerate(fault_sequence):
        kind = _normalize_kind(str(fault.get("fault_type", "deploy")))
        service_id = int(fault.get("target", 0))
        events.append(
            TraceEvent(
                step=int(fault.get("tick", index)),
                service_id=service_id,
                kind=kind,
                severity=0.7,
                log_excerpt=f"{scenario}: {kind} detected at service_{service_id}",
                metric_signal="error_rate",
                ticket_id=f"CFG-{scenario.upper()}-{index:03d}",
                customer_impact_minutes=8.0,
                escalation_risk=0.25,
            )
        )

    if not events:
        events.append(
            TraceEvent(
                step=0,
                service_id=0,
                kind="deploy",
                severity=0.65,
                log_excerpt=f"{scenario}: default fault from config fallback",
                metric_signal="error_rate",
                ticket_id=f"CFG-{scenario.upper()}-DEFAULT",
                customer_impact_minutes=6.0,
                escalation_risk=0.2,
            )
        )

    return IncidentTrace(
        trace_id=f"{scenario}_config_trace",
        scenario=scenario,
        started_at="2026-01-01T00:00:00Z",
        step_minutes=1.0,
        human_runbook_mttr_minutes=75.0,
        human_wrong_actions=3,
        human_escalation_rate=0.25,
        sources={
            "logs": [f"config-derived logs for {scenario}"],
            "metrics": [f"config-derived metrics for {scenario}"],
            "tickets": [f"config-derived ticket for {scenario}"],
        },
        events=tuple(events),
    )


def load_incident_trace(scenario: str, trace_id: str | None = None) -> IncidentTrace:
    traces = list_incident_traces(scenario=scenario)
    if trace_id is not None:
        for trace in traces:
            if trace.trace_id == trace_id:
                return trace
        raise ValueError(f"Unknown trace_id '{trace_id}' for scenario '{scenario}'")

    configured_path = _configured_trace_path(scenario)
    if configured_path is not None:
        configured_trace = _load_trace_file(configured_path)
        if configured_trace.scenario != scenario:
            raise ValueError(
                f"Configured trace '{configured_path.name}' has scenario "
                f"'{configured_trace.scenario}' but expected '{scenario}'"
            )
        return configured_trace

    if traces:
        return traces[0]

    return _trace_from_config(scenario)
