from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch

from envs import IncidentEnv
from envs.scenarios import IncidentTrace, list_incident_traces

FAULT_ACTION_PRIORITY: dict[str, list[int]] = {
    "deploy": [2, 0, 4],
    "memory": [1, 0, 5],
    "timeout": [3, 5, 1],
    "traffic": [3, 1, 5],
    "split": [4, 3, 0],
}
AGENT_MODES = {"random", "greedy", "four_stage", "trained"}


def _active_faults(info: dict[str, Any]) -> list[dict[str, Any]]:
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
        if service_id < 0 or service_id > 11:
            continue
        faults.append(
            {
                "service_id": service_id,
                "kind": str(payload.get("kind", "deploy")).strip().lower(),
                "severity": max(0.0, min(1.0, severity)),
            }
        )
    return faults


def _greedy_action(info: dict[str, Any]) -> list[int]:
    faults = _active_faults(info)
    if not faults:
        return [0, 6]
    target = max(
        faults,
        key=lambda payload: (float(payload["severity"]), -int(payload["service_id"])),
    )
    service_id = int(target["service_id"])
    candidates = FAULT_ACTION_PRIORITY.get(str(target["kind"]), [0, 1, 3])
    return [service_id, candidates[0]]


def _four_stage_action(info: dict[str, Any], tick: int) -> list[int]:
    faults = sorted(
        _active_faults(info),
        key=lambda payload: (-float(payload["severity"]), int(payload["service_id"])),
    )
    if not faults:
        return [0, 6]

    shortlist: list[list[int]] = []
    for fault in faults[:2]:
        service_id = int(fault["service_id"])
        for action_type in FAULT_ACTION_PRIORITY.get(str(fault["kind"]), [0, 1, 3])[:2]:
            shortlist.append([service_id, action_type])
    if not shortlist:
        return [0, 6]
    return shortlist[tick % len(shortlist)]


def _build_action_context(
    action: list[int],
    info: dict[str, Any],
    *,
    agent_mode: str,
    tick: int,
) -> dict[str, Any]:
    faults = _active_faults(info)
    if faults:
        top = max(faults, key=lambda payload: float(payload["severity"]))
        symptom = f"{top['kind']} on service_{top['service_id']}"
    else:
        symptom = "active incident symptoms"

    context = {
        "operator_id": f"backtest-{agent_mode}",
        "justification": (
            f"Step {tick}: apply action {action[1]} on service_{action[0]} to mitigate "
            f"{symptom} and reduce escalation risk."
        ),
    }
    if int(action[1]) in {2, 4}:
        context["approval_token"] = f"BACKTEST-APPROVAL-{tick}"
    return context


def _load_trained_model(checkpoint: Path) -> Any:
    from training.train import ActorCritic

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint_payload = torch.load(checkpoint, map_location=device)
    model = ActorCritic().to(device)
    model.load_state_dict(checkpoint_payload["model_state_dict"])
    model.eval()
    return model


def _trained_action(model: Any, observation: Any) -> list[int]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    with torch.no_grad():
        obs_tensor = torch.tensor(
            observation, dtype=torch.float32, device=device
        ).unsqueeze(0)
        service_logits, action_logits, _ = model(obs_tensor)
        return [
            int(torch.argmax(service_logits, dim=-1).item()),
            int(torch.argmax(action_logits, dim=-1).item()),
        ]


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def run_historical_backtest(
    *,
    agent_mode: str = "greedy",
    scenario: str | None = None,
    max_incidents: int = 50,
    seed: int = 7,
    checkpoint: str | None = None,
) -> dict[str, Any]:
    normalized_mode = agent_mode.strip().lower()
    if normalized_mode not in AGENT_MODES:
        raise ValueError(
            f"agent_mode must be one of {sorted(AGENT_MODES)}, got '{agent_mode}'"
        )
    if max_incidents <= 0:
        raise ValueError("max_incidents must be > 0")

    traces = list_incident_traces(scenario=scenario)
    if not traces:
        if scenario is None:
            raise ValueError("no historical traces found")
        raise ValueError(f"no historical traces found for scenario '{scenario}'")

    selected: list[IncidentTrace] = [
        traces[index % len(traces)] for index in range(max_incidents)
    ]

    trained_model = None
    if normalized_mode == "trained":
        if checkpoint is None:
            raise ValueError("checkpoint is required when agent_mode='trained'")
        checkpoint_path = Path(checkpoint)
        if not checkpoint_path.exists():
            raise ValueError(f"checkpoint not found: {checkpoint}")
        trained_model = _load_trained_model(checkpoint_path)

    incident_results: list[dict[str, Any]] = []
    mttr_values: list[float] = []
    human_mttr_values: list[float] = []
    wrong_values: list[float] = []
    human_wrong_values: list[float] = []
    escalation_values: list[float] = []
    human_escalation_values: list[float] = []
    impact_values: list[float] = []
    resolutions: list[float] = []

    for index, trace in enumerate(selected):
        env = IncidentEnv(
            scenario=trace.scenario,
            max_steps=50,
            execution_mode="reality",
            trace_id=trace.trace_id,
        )
        observation, info = env.reset(seed=seed + index)
        done = False
        tick = 0
        cumulative_reward = 0.0

        while not done:
            if normalized_mode == "greedy":
                action = _greedy_action(info)
            elif normalized_mode == "four_stage":
                action = _four_stage_action(info, tick)
            elif normalized_mode == "trained" and trained_model is not None:
                action = _trained_action(trained_model, observation)
            else:
                sampled = env.action_space.sample()
                action = [int(sampled[0]), int(sampled[1])]

            context = _build_action_context(
                action,
                info,
                agent_mode=normalized_mode,
                tick=tick,
            )
            observation, reward, terminated, truncated, info = env.step(
                action, action_context=context
            )
            done = bool(terminated or truncated)
            cumulative_reward += float(reward)
            tick += 1

        final_scores = info.get("operational_scores", {})
        mttr = float(final_scores.get("mttr_minutes", 0.0))
        human_mttr = float(
            final_scores.get("human_mttr_minutes", trace.human_runbook_mttr_minutes)
        )
        wrong_actions = float(info.get("false_positives", 0.0))
        human_wrong = float(
            final_scores.get("human_wrong_actions", trace.human_wrong_actions)
        )
        escalation_rate = wrong_actions / float(max(1, info.get("total_actions", 1)))
        human_escalation = float(
            final_scores.get("human_escalation_rate", trace.human_escalation_rate)
        )
        impact = float(final_scores.get("customer_impact_minutes", 0.0))
        resolved = bool(info.get("active_faults") == [])

        incident_results.append(
            {
                "index": index,
                "trace_id": trace.trace_id,
                "scenario": trace.scenario,
                "ticks": tick,
                "cumulative_reward": cumulative_reward,
                "resolved": resolved,
                "agent_mttr_minutes": mttr,
                "human_mttr_minutes": human_mttr,
                "agent_wrong_actions": wrong_actions,
                "human_wrong_actions": human_wrong,
                "agent_escalation_rate": escalation_rate,
                "human_escalation_rate": human_escalation,
                "customer_impact_minutes": impact,
            }
        )

        mttr_values.append(mttr)
        human_mttr_values.append(human_mttr)
        wrong_values.append(wrong_actions)
        human_wrong_values.append(human_wrong)
        escalation_values.append(escalation_rate)
        human_escalation_values.append(human_escalation)
        impact_values.append(impact)
        resolutions.append(1.0 if resolved else 0.0)

    return {
        "agent_mode": normalized_mode,
        "scenario_filter": scenario,
        "incident_count": len(selected),
        "mean_agent_mttr_minutes": _mean(mttr_values),
        "mean_human_mttr_minutes": _mean(human_mttr_values),
        "mean_mttr_delta_minutes": _mean(human_mttr_values) - _mean(mttr_values),
        "mean_agent_wrong_actions": _mean(wrong_values),
        "mean_human_wrong_actions": _mean(human_wrong_values),
        "mean_agent_escalation_rate": _mean(escalation_values),
        "mean_human_escalation_rate": _mean(human_escalation_values),
        "resolution_rate": _mean(resolutions),
        "mean_customer_impact_minutes": _mean(impact_values),
        "incidents": incident_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run historical incident trace backtests."
    )
    parser.add_argument(
        "--agent-mode",
        type=str,
        default="greedy",
        choices=sorted(AGENT_MODES),
        help="Policy to evaluate in reality mode.",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Optional scenario filter.",
    )
    parser.add_argument(
        "--max-incidents",
        type=int,
        default=50,
        help="Number of incidents to replay (cycles traces if needed).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Seed for deterministic backtest rollouts.",
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default=None,
        help="Checkpoint path when using --agent-mode trained.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="backtest_report.json",
        help="Output path for the backtest JSON report.",
    )
    args = parser.parse_args()

    report = run_historical_backtest(
        agent_mode=args.agent_mode,
        scenario=args.scenario,
        max_incidents=args.max_incidents,
        seed=args.seed,
        checkpoint=args.checkpoint,
    )
    output_path = Path(args.output)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "incidents"}, indent=2))
    print(f"Saved backtest report to: {output_path}")


if __name__ == "__main__":
    main()
