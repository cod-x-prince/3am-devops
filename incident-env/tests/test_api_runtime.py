from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_required_runtime_endpoints_are_available() -> None:
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/state").status_code == 200
    assert client.get("/metadata").status_code == 200
    assert client.get("/schema").status_code == 200
    assert (
        client.post("/mcp", json={"id": "ping-1", "method": "ping"}).status_code == 200
    )


def test_reset_step_and_state_use_real_environment() -> None:
    reset_response = client.post("/reset", json={"scenario": "bad_deploy", "seed": 7})
    assert reset_response.status_code == 200
    reset_payload = reset_response.json()
    assert len(reset_payload["observation"]) == 72
    assert reset_payload["info"]["scenario"] == "bad_deploy"
    assert len(reset_payload["info"]["active_faults"]) >= 1

    state_before = client.get("/state")
    assert state_before.status_code == 200
    state_before_payload = state_before.json()
    assert state_before_payload["scenario"] == "bad_deploy"
    assert state_before_payload["step_count"] == 0

    step_response = client.post("/step", json={"action": [3, 2]})
    assert step_response.status_code == 200
    step_payload = step_response.json()
    assert len(step_payload["observation"]) == 72
    assert "active_faults" in step_payload["info"]
    assert "services_json" in step_payload["info"]

    state_after = client.get("/state")
    assert state_after.status_code == 200
    state_after_payload = state_after.json()
    assert state_after_payload["step_count"] == 1
    assert len(state_after_payload["engine_state"]["services"]) == 12

    health_payload = client.get("/health").json()
    assert health_payload["env_ready"] is True
    assert health_payload["current_scenario"] == "bad_deploy"


def test_mcp_dispatches_core_methods() -> None:
    reset_rpc = client.post(
        "/mcp",
        json={
            "id": "rpc-reset",
            "method": "reset",
            "params": {"scenario": "multi_fault"},
        },
    )
    assert reset_rpc.status_code == 200
    reset_result = reset_rpc.json()["result"]
    assert len(reset_result["observation"]) == 72

    state_rpc = client.post("/mcp", json={"id": "rpc-state", "method": "state"})
    assert state_rpc.status_code == 200
    assert state_rpc.json()["result"]["scenario"] == "multi_fault"

    step_rpc = client.post(
        "/mcp",
        json={"id": "rpc-step", "method": "step", "params": {"action": [2, 2]}},
    )
    assert step_rpc.status_code == 200
    assert "reward" in step_rpc.json()["result"]

    unknown_rpc = client.post("/mcp", json={"id": "rpc-unknown", "method": "unknown"})
    assert unknown_rpc.status_code == 200
    assert unknown_rpc.json()["error"]["code"] == -32601


def test_episode_options_exposes_all_scenarios_and_agents() -> None:
    response = client.get("/episode/options")
    assert response.status_code == 200
    payload = response.json()

    scenario_ids = [item["id"] for item in payload["scenarios"]]
    assert scenario_ids == [
        "bad_deploy",
        "memory_leak",
        "cascade_timeout",
        "thundering_herd",
        "split_brain",
        "multi_fault",
    ]

    agent_ids = [item["id"] for item in payload["agents"]]
    assert "random" in agent_ids
    assert "greedy" in agent_ids
    assert "four_stage" in agent_ids
    assert "trained" in agent_ids

    execution_mode_ids = [item["id"] for item in payload["execution_modes"]]
    assert execution_mode_ids == ["benchmark", "reality"]

    traces = payload["traces"]
    assert "bad_deploy" in traces
    assert any(
        item["trace_id"] == "bad_deploy_trace_001" for item in traces["bad_deploy"]
    )


def test_episode_start_supports_agent_modes() -> None:
    response = client.post(
        "/episode/start",
        json={
            "scenario": "split_brain",
            "mode": "four_stage",
            "execution_mode": "reality",
            "trace_id": "split_brain_trace_001",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario"] == "split_brain"
    assert payload["mode"] == "four_stage"
    assert payload["execution_mode"] == "reality"
    assert payload["trace_id"] == "split_brain_trace_001"


def test_reset_and_step_support_reality_mode_context() -> None:
    reset_response = client.post(
        "/reset",
        json={
            "scenario": "bad_deploy",
            "execution_mode": "reality",
            "trace_id": "bad_deploy_trace_001",
        },
    )
    assert reset_response.status_code == 200
    reset_payload = reset_response.json()
    assert reset_payload["info"]["execution_mode"] == "reality"
    assert reset_payload["info"]["trace_id"] == "bad_deploy_trace_001"

    blocked_step = client.post("/step", json={"action": [3, 2]})
    assert blocked_step.status_code == 200
    blocked_error = blocked_step.json()["info"]["last_action_error"]
    assert isinstance(blocked_error, str)
    assert "approval_required_for_high_risk_action" in blocked_error

    allowed_step = client.post(
        "/step",
        json={
            "action": [3, 2],
            "justification": (
                "Rollback deploy to reduce deploy and error_rate symptoms while "
                "containing escalation risk."
            ),
            "approval_token": "INC-2026-1001-APPROVED",
            "operator_id": "api-test",
        },
    )
    assert allowed_step.status_code == 200
    allowed_payload = allowed_step.json()
    assert allowed_payload["info"]["execution_mode"] == "reality"


def test_backtest_endpoint_smoke() -> None:
    response = client.post(
        "/backtest/run",
        json={"agent_mode": "greedy", "scenario": "bad_deploy", "max_incidents": 2},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["incident_count"] == 2
    assert payload["agent_mode"] == "greedy"
