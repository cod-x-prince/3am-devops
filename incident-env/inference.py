from __future__ import annotations

import argparse
import json
import os
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

API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME_DEFAULT = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME", "incidentenv")
BENCHMARK = os.getenv("INCIDENTENV_BENCHMARK", "incidentenv")

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


def _heuristic_action(state: dict[str, Any]) -> ActionModel:
    services = state.get("engine_state", {}).get("services", [])
    if not services:
        return ActionModel(service_id=0, action_type=6)

    ranked = sorted(
        enumerate(services),
        key=lambda item: (
            float(item[1].get("error_rate", 0.0)),
            float(item[1].get("latency_p99", 0.0)),
            float(item[1].get("memory", 0.0)),
        ),
        reverse=True,
    )
    service_id, service = ranked[0]
    error_rate = float(service.get("error_rate", 0.0))
    latency_p99 = float(service.get("latency_p99", 0.0))
    memory = float(service.get("memory", 0.0))

    if error_rate >= 0.65:
        action_type = 2
    elif latency_p99 >= 0.65:
        action_type = 5
    elif memory >= 0.7:
        action_type = 1
    else:
        action_type = 0

    return ActionModel(service_id=int(service_id), action_type=action_type)


def _ask_model(
    client: Any, model_name: str, task_id: str, state: dict[str, Any], history: list[str]
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
            {"role": "system", "content": "You are an SRE incident agent. Respond with JSON only."},
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
    if OpenAI is None or API_KEY is None:
        return None
    return OpenAI(base_url=API_BASE_URL, api_key=API_KEY)


def run_task(task_id: str, model_name: str, client: Any, max_steps_override: int | None) -> float:
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

    log_start(task=task_id, env=BENCHMARK, model=model_name)

    try:
        observation = env.reset()
        _ = observation
        state = env.state()
        initial_unhealthy = int(state.get("info", {}).get("current_unhealthy", 0))
        current_unhealthy = initial_unhealthy

        for step in range(1, max_steps + 1):
            state = env.state()
            step_error: str | None = None

            if client is None:
                action = _heuristic_action(state)
            else:
                try:
                    action = _ask_model(client, model_name, task_id, state, history)
                except (APIConnectionError, APIError, APITimeoutError, ValueError, TypeError) as exc:
                    action = _heuristic_action(state)
                    step_error = str(exc)

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
    parser = argparse.ArgumentParser(description="IncidentEnv baseline inference runner")
    parser.add_argument("--tasks", nargs="*", default=default_task_ids())
    parser.add_argument("--model", default=MODEL_NAME_DEFAULT)
    parser.add_argument("--max-steps", type=int, default=None)
    args = parser.parse_args()

    for task_id in args.tasks:
        get_task_spec(task_id)

    client = _build_client()
    for task_id in args.tasks:
        run_task(task_id, args.model, client, args.max_steps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
