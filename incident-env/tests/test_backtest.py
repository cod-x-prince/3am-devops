from __future__ import annotations

from training.backtest import run_historical_backtest


def test_historical_backtest_smoke() -> None:
    report = run_historical_backtest(
        agent_mode="greedy",
        scenario="bad_deploy",
        max_incidents=3,
        seed=17,
    )

    assert report["agent_mode"] == "greedy"
    assert report["scenario_filter"] == "bad_deploy"
    assert report["incident_count"] == 3
    assert report["mean_agent_mttr_minutes"] >= 0.0
    assert report["mean_human_mttr_minutes"] >= 0.0
    assert 0.0 <= report["resolution_rate"] <= 1.0
    assert len(report["incidents"]) == 3
