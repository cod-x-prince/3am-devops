from __future__ import annotations

from envs import IncidentEnv


def test_reality_mode_reset_exposes_trace_context() -> None:
    env = IncidentEnv(
        scenario="bad_deploy",
        max_steps=10,
        execution_mode="reality",
        trace_id="bad_deploy_trace_001",
    )
    observation, info = env.reset(seed=9)

    assert observation.shape == (72,)
    assert info["execution_mode"] == "reality"
    assert info["trace_id"] == "bad_deploy_trace_001"
    assert isinstance(info["trace_started_at"], str)
    assert "operational_scores" in info
    assert len(info["active_faults"]) >= 1
    env.close()


def test_reality_mode_enforces_safety_rails() -> None:
    env = IncidentEnv(
        scenario="bad_deploy",
        max_steps=10,
        execution_mode="reality",
        trace_id="bad_deploy_trace_001",
    )
    env.reset(seed=9)

    _, _, _, _, blocked_info = env.step([3, 2])
    assert "approval_required_for_high_risk_action" in str(
        blocked_info["last_action_error"]
    )

    _, _, _, _, allowed_info = env.step(
        [3, 2],
        action_context={
            "justification": (
                "Rollback deploy to address active deploy and error_rate symptoms "
                "before escalation risk grows."
            ),
            "approval_token": "INC-2026-1001-APPROVED",
            "operator_id": "test-oncall",
        },
    )
    assert allowed_info["execution_mode"] == "reality"
    assert allowed_info["last_action_error"] != "approval_required_for_high_risk_action"
    env.close()
