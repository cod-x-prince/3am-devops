from __future__ import annotations

import json
from pathlib import Path

SCENARIO_DIR = Path(__file__).resolve().parents[1] / "scenarios" / "configs"


def list_scenarios() -> list[str]:
    return sorted(p.stem for p in SCENARIO_DIR.glob("*.json"))


def get_scenario_config(name: str) -> dict:
    path = SCENARIO_DIR / f"{name}.json"
    if not path.exists():
        raise ValueError(f"Unknown scenario: {name}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def scenario_env_kwargs(name: str) -> dict:
    cfg = get_scenario_config(name)
    return {
        "scenario": cfg["name"],
        "curriculum_level": int(cfg.get("curriculum_level", 1)),
    }
