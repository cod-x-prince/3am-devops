from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from typing import Any

from envs import ActionModel, OpenIncidentEnv
from tasks import default_task_ids, get_task_spec, score_task

try:
    from openai import APIConnectionError, APIError, APITimeoutError, OpenAI
except ImportError:  # pragma: no cover - optional runtime dependency in CI
    APIConnectionError = RuntimeError
    APIError = RuntimeError
    APITimeoutError = RuntimeError
    OpenAI = None

API_KEY = os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME_DEFAULT = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
BENCHMARK = "incidentenv"
AGENT_CHOICES = ("llm", "greedy", "random", "four-stage")

ACTION_NAMES = [
    "RestartService",
    "ScaleUp",
    "RollbackDeploy",
    "RerouteTraffic",
    "ToggleFeatureFlag",
    "TriggerCircuitBreaker",
    "NoOp",
]


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _error_text(error: str | None) -> str:
    return "null" if error is None or error == "" else error


def _action_text(action: ActionModel) -> str:
    return f"{ACTION_NAMES[action.action_type]}(service_{action.service_id})"


def _rewards_text(rewards: list[float]) -> str:
    return ",".join(f"{reward:.2f}" for reward in rewards)


def log_start(*, task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(
    *, step: int, action: str, reward: float, done: bool, error: str | None
) -> None:
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={_bool_text(done)} "
        f"error={_error_text(error)}",
        flush=True,
    )


def log_end(*, success: bool, steps: int, score: float, rewards: list[float]) -> None:
    print(
        f"[END] success={_bool_text(success)} steps={steps} score={score:.2f} rewards={_rewards_text(rewards)}",
        flush=True,
    )


def _extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None

    candidates = [text.strip()]
    candidates.extend(re.findall(r"\{.*?\}", text, flags=re.DOTALL))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


FAULT_ACTION_PRIORITY: dict[str, list[int]] = {
    "deploy": [2, 0, 4],  # RollbackDeploy, RestartService, ToggleFeatureFlag
    "memory": [1, 0, 5],  # ScaleUp, RestartService, TriggerCircuitBreaker
    "timeout": [3, 5, 1],  # RerouteTraffic, TriggerCircuitBreaker, ScaleUp
    "traffic": [3, 1, 5],  # RerouteTraffic, ScaleUp, TriggerCircuitBreaker
    "split": [4, 3, 0],  # ToggleFeatureFlag, RerouteTraffic, RestartService
}


def _active_faults_from_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    engine_state = state.get("engine_state", {})
    if not isinstance(engine_state, dict):
        return []

    raw_faults = engine_state.get("active_faults", [])
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


def _fallback_action() -> ActionModel:
    return ActionModel(service_id=0, action_type=6)


def _action_candidates_for_fault(fault: dict[str, Any]) -> list[ActionModel]:
    service_id = int(fault["service_id"])
    action_priority = FAULT_ACTION_PRIORITY.get(str(fault["kind"]), [0, 1, 3])
    return [
        ActionModel(service_id=service_id, action_type=action_type)
        for action_type in action_priority
    ]


def _greedy_action_from_state(state: dict[str, Any]) -> ActionModel:
    faults = _active_faults_from_state(state)
    if not faults:
        return _fallback_action()

    sorted_faults = sorted(
        faults,
        key=lambda fault: (-float(fault["severity"]), int(fault["service_id"])),
    )
    candidates = _action_candidates_for_fault(sorted_faults[0])
    return candidates[0] if candidates else _fallback_action()


def _random_action(rng: random.Random) -> ActionModel:
    return ActionModel(service_id=rng.randint(0, 11), action_type=rng.randint(0, 6))


def _four_stage_action(
    client: Any | None,
    model_name: str,
    task_id: str,
    state: dict[str, Any],
    history: list[str],
) -> ActionModel:
    # Stage 1: detect current incident set.
    faults = _active_faults_from_state(state)
    if not faults:
        return _fallback_action()

    # Stage 2: prioritize by severity.
    prioritized_faults = sorted(
        faults,
        key=lambda fault: (-float(fault["severity"]), int(fault["service_id"])),
    )

    # Stage 3: build a shortlist of strong heuristic actions.
    shortlist: list[ActionModel] = []
    for fault in prioritized_faults[:2]:
        shortlist.extend(_action_candidates_for_fault(fault)[:2])
    if not shortlist:
        return _fallback_action()

    # Stage 4: optional LLM arbitration among shortlist candidates.
    if client is None:
        return shortlist[0]

    prompt = {
        "task": task_id,
        "instruction": (
            "Pick ONE action from shortlist only. "
            "Return JSON with keys service_id and action_type."
        ),
        "shortlist": [candidate.model_dump() for candidate in shortlist],
        "state": state,
        "history": history[-6:],
    }
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": "You are an SRE policy selector. Choose from shortlist only and respond JSON.",
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            temperature=0.0,
            max_tokens=120,
        )
    except (APIConnectionError, APIError, APITimeoutError, TypeError, ValueError):
        return shortlist[0]

    content = response.choices[0].message.content or ""
    parsed = _extract_json_object(content)
    if parsed is None:
        return shortlist[0]

    try:
        return ActionModel.model_validate(
            {
                "service_id": int(parsed.get("service_id", shortlist[0].service_id)),
                "action_type": int(parsed.get("action_type", shortlist[0].action_type)),
            }
        )
    except (TypeError, ValueError):
        return shortlist[0]


def _select_action(
    *,
    agent_mode: str,
    client: Any | None,
    model_name: str,
    task_id: str,
    state: dict[str, Any],
    history: list[str],
    rng: random.Random,
) -> ActionModel:
    if agent_mode == "llm":
        if client is None:
            raise RuntimeError("LLM agent requires HF_TOKEN (or OPENAI_API_KEY)")
        return _ask_model(client, model_name, task_id, state, history)
    if agent_mode == "greedy":
        return _greedy_action_from_state(state)
    if agent_mode == "random":
        return _random_action(rng)
    if agent_mode == "four-stage":
        return _four_stage_action(client, model_name, task_id, state, history)
    raise ValueError(f"Unknown agent mode: {agent_mode}")


def _model_label(agent_mode: str, model_name: str, client: Any | None) -> str:
    if agent_mode == "llm":
        return model_name
    if agent_mode == "four-stage":
        if client is None:
            return "four-stage-heuristic"
        return f"four-stage-{model_name}"
    return agent_mode


def _ask_model(
    client: Any,
    model_name: str,
    task_id: str,
    state: dict[str, Any],
    history: list[str],
) -> ActionModel:
    prompt = {
        "task": task_id,
        "action_space": {"service_id": [0, 11], "action_type": [0, 6]},
        "action_names": ACTION_NAMES,
        "state": state,
        "history": history[-6:],
        "instruction": "Return JSON only with keys service_id and action_type.",
    }

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": "You are an SRE incident agent. Respond with JSON only.",
            },
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        temperature=0.0,
        max_tokens=120,
    )
    content = response.choices[0].message.content or ""
    parsed = _extract_json_object(content)
    if parsed is None:
        raise ValueError("model_response_not_json")

    return ActionModel.model_validate(
        {
            "service_id": int(parsed.get("service_id", 0)),
            "action_type": int(parsed.get("action_type", 6)),
        }
    )


def _build_client() -> Any:
    if OpenAI is None:
        raise RuntimeError("openai package is required for inference")
    if API_KEY is None:
        raise RuntimeError("HF_TOKEN (or OPENAI_API_KEY) is required for inference")
    return OpenAI(base_url=API_BASE_URL, api_key=API_KEY)


def run_task(
    task_id: str,
    model_name: str,
    client: Any | None,
    max_steps_override: int | None,
    agent_mode: str,
    rng: random.Random,
) -> float:
    spec = get_task_spec(task_id)
    max_steps = max_steps_override if max_steps_override is not None else spec.max_steps

    env = OpenIncidentEnv(scenario=spec.scenario, max_steps=max_steps)
    rewards: list[float] = []
    history: list[str] = []
    steps_taken = 0
    score = 0.0
    success = False
    done = False
    initial_unhealthy = 0
    current_unhealthy = 0
    false_positives = 0

    log_start(
        task=task_id, env=BENCHMARK, model=_model_label(agent_mode, model_name, client)
    )

    try:
        observation = env.reset()
        _ = observation
        state = env.state()
        initial_unhealthy = int(state.get("info", {}).get("current_unhealthy", 0))
        current_unhealthy = initial_unhealthy

        for step in range(1, max_steps + 1):
            state = env.state()
            step_error: str | None = None

            try:
                action = _select_action(
                    agent_mode=agent_mode,
                    client=client,
                    model_name=model_name,
                    task_id=task_id,
                    state=state,
                    history=history,
                    rng=rng,
                )
            except (
                APIConnectionError,
                APIError,
                APITimeoutError,
                ValueError,
                TypeError,
            ) as exc:
                step_error = str(exc)
                raise RuntimeError(step_error) from exc

            next_observation, reward_model, done, info = env.step(action)
            reward_value = float(reward_model.value)
            rewards.append(reward_value)
            steps_taken = step
            current_unhealthy = int(info.get("current_unhealthy", current_unhealthy))
            false_positives = int(info.get("false_positives", false_positives))

            if info.get("last_action_error") is not None:
                step_error = str(info["last_action_error"])

            log_step(
                step=step,
                action=_action_text(action),
                reward=reward_value,
                done=done,
                error=step_error,
            )
            history.append(
                f"step={step};action={action.service_id}:{action.action_type};reward={reward_value:.2f};done={done}"
            )
            _ = next_observation

            if done:
                break

        steps_to_resolution = steps_taken if done else max_steps
        score = score_task(
            task_id=task_id,
            steps_to_resolution=steps_to_resolution,
            previous_unhealthy=initial_unhealthy,
            current_unhealthy=current_unhealthy,
            false_positives=false_positives,
            total_actions=max(1, steps_taken),
        )
        success = done and score >= 0.6
    finally:
        env.close()
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return score


def main() -> int:
    parser = argparse.ArgumentParser(
        description="IncidentEnv baseline inference runner"
    )
    parser.add_argument("--tasks", nargs="*", default=default_task_ids())
    parser.add_argument("--model", default=MODEL_NAME_DEFAULT)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--agent", choices=AGENT_CHOICES, default="llm")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    for task_id in args.tasks:
        get_task_spec(task_id)

    client: Any | None = None
    if args.agent == "llm":
        client = _build_client()
    elif args.agent == "four-stage":
        try:
            client = _build_client()
        except RuntimeError:
            client = None

    rng = random.Random(args.seed)
    exit_code = 0
    for task_id in args.tasks:
        try:
            run_task(
                task_id=task_id,
                model_name=args.model,
                client=client,
                max_steps_override=args.max_steps,
                agent_mode=args.agent,
                rng=rng,
            )
        except Exception as exc:
            print(str(exc), file=sys.stderr, flush=True)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
