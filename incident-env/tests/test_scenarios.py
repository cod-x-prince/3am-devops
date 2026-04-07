import json
import glob
import os

def test_scenarios_valid():
    paths = glob.glob(os.path.join(os.path.dirname(__file__), "..", "scenarios", "configs", "*.json"))
    assert len(paths) >= 5, f"Expected at least 5 scenarios, found {len(paths)}"
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "name" in data, f"Missing name in {path}"
        assert "fault_sequence" in data, f"Missing fault_sequence in {path}"
        assert "max_steps" in data, f"Missing max_steps in {path}"
