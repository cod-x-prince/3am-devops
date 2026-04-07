from __future__ import annotations


def compute(steps_taken: int, resolved: bool, max_steps: int) -> float:
    if max_steps <= 0:
        return 0.0
    if not resolved:
        return 0.0
    normalized = 1.0 - max(0, steps_taken - 1) / float(max_steps)
    bonus = 0.3 if steps_taken <= 5 else 0.0
    return float(max(-1.0, min(1.0, normalized + bonus)))
