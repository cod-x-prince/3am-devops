from __future__ import annotations

from dataclasses import dataclass

from rewards import composite_reward


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    difficulty: str
    scenario: str
    max_steps: int
    description: str


TASKS: tuple[TaskSpec, ...] = (
    TaskSpec(
        task_id="bad_deploy_easy",
        difficulty="easy",
        scenario="bad_deploy",
        max_steps=20,
        description="Resolve a single faulty deploy quickly and with no unnecessary actions.",
    ),
    TaskSpec(
        task_id="cascade_timeout_medium",
        difficulty="medium",
        scenario="cascade_timeout",
        max_steps=30,
        description="Stop downstream propagation before the incident spreads too far.",
    ),
    TaskSpec(
        task_id="multi_fault_hard",
        difficulty="hard",
        scenario="multi_fault",
        max_steps=40,
        description="Resolve multiple simultaneous failures while minimizing blast radius.",
    ),
)

TASKS_BY_ID: dict[str, TaskSpec] = {task.task_id: task for task in TASKS}


def get_task_spec(task_id: str) -> TaskSpec:
    spec = TASKS_BY_ID.get(task_id)
    if spec is None:
        raise KeyError(f"Unknown task_id: {task_id}")
    return spec


def default_task_ids() -> list[str]:
    return [task.task_id for task in TASKS]


def score_task(
    *,
    task_id: str,
    steps_to_resolution: int,
    previous_unhealthy: int,
    current_unhealthy: int,
    false_positives: int,
    total_actions: int,
) -> float:
    """Return a normalized score in [0.0, 1.0] for OpenEnv-style grading."""
    spec = get_task_spec(task_id)

    composite = composite_reward(
        steps_to_resolution=steps_to_resolution,
        previous_unhealthy=previous_unhealthy,
        current_unhealthy=current_unhealthy,
        false_positives=false_positives,
        total_actions=total_actions,
        max_steps=spec.max_steps,
    )
    return max(0.0, min(1.0, (composite + 1.0) / 2.0))
