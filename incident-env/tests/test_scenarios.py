from __future__ import annotations

import json
from pathlib import Path

from envs.scenarios import load_incident_trace


def test_scenarios_valid() -> None:
    project_root = Path(__file__).resolve().parents[1]
    config_paths = sorted((project_root / "scenarios" / "configs").glob("*.json"))
    trace_root = project_root / "scenarios" / "traces"

    assert len(config_paths) >= 5
    for path in config_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "name" in data
        assert "fault_sequence" in data
        assert "max_steps" in data
        if "trace_file" in data:
            trace_path = trace_root / str(data["trace_file"])
            assert trace_path.exists(), f"Missing trace file referenced by {path.name}"


def test_load_incident_trace_honors_config_mapping() -> None:
    project_root = Path(__file__).resolve().parents[1]
    config_paths = sorted((project_root / "scenarios" / "configs").glob("*.json"))

    for path in config_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        scenario = str(data["name"])
        trace = load_incident_trace(scenario)
        assert trace.scenario == scenario
        assert len(trace.events) >= 1
