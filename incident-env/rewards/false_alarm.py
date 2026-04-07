from __future__ import annotations


def compute(
    action_target_health: float, action_type: int, critical_exists: bool
) -> float:
    if action_target_health > 0.9:
        return -0.2
    if action_type == 6 and critical_exists:
        return -0.05
    return 0.0
