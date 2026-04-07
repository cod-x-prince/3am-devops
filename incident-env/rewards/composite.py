from __future__ import annotations

WEIGHTS = {
    # Contract-aligned blend: prioritize fast resolution, then containment and action quality.
    "mttr": 0.5,
    "blast_radius": 0.25,
    "false_alarm": 0.15,
    "efficiency": 0.10,
}


def compute(
    mttr_r: float, blast_r: float, false_alarm_r: float, efficiency_r: float
) -> float:
    raw = (
        WEIGHTS["mttr"] * float(mttr_r)
        + WEIGHTS["blast_radius"] * float(blast_r)
        + WEIGHTS["false_alarm"] * float(false_alarm_r)
        + WEIGHTS["efficiency"] * float(efficiency_r)
    )
    return float(max(-1.0, min(1.0, raw)))
