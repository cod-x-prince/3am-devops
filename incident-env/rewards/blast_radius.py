from __future__ import annotations


def compute(newly_degraded: int, total_services: int) -> float:
    total = max(1, int(total_services))
    per_step = -0.1 * max(0, int(newly_degraded))
    normalized = per_step / float(total)
    return float(max(-1.0, min(1.0, normalized)))
