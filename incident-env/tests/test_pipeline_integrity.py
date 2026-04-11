from __future__ import annotations

import json
import math

import torch

from envs import IncidentEnv
from tests.mock_env import MockIncidentEnv
from training.eval import run_random_policy_eval
from training.train import ActorCritic, HyperParams, collect_rollout, ppo_update


def test_services_json_data_handler_contract() -> None:
    env = IncidentEnv(scenario="bad_deploy", max_steps=10)
    observation, info = env.reset(seed=7)
    assert observation.shape == (72,)

    payload = json.loads(str(info["services_json"]))
    assert isinstance(payload, dict)
    assert "services" in payload
    assert "connections" in payload
    assert "active_faults" in payload
    assert len(payload["services"]) == 12

    first_service = payload["services"][0]
    assert "id" in first_service
    assert "health" in first_service
    assert "cpu" in first_service
    assert "memory" in first_service
    assert "error_rate" in first_service
    assert "latency_p99" in first_service
    assert "status" in first_service
    env.close()


def test_training_pipeline_smoke_update() -> None:
    device = torch.device("cpu")
    env = MockIncidentEnv(max_steps=8, seed=11)
    model = ActorCritic().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=HyperParams().lr)

    batch = collect_rollout(env, model, rollout_steps=8, device=device)
    assert tuple(batch["obs"].shape) == (8, 72)
    assert len(batch["reward"]) == 8
    assert len(batch["done"]) == 8

    metrics = ppo_update(batch, model, optimizer, HyperParams())
    for key in ("loss", "actor_loss", "critic_loss", "entropy", "mean_reward"):
        assert key in metrics
        assert math.isfinite(float(metrics[key]))


def test_eval_pipeline_report_shape() -> None:
    report = run_random_policy_eval(episodes=3)
    assert 0.0 <= report.overall_score <= 100.0
    assert report.mean_mttr_steps >= 0.0
    assert report.scenario_results

    for scenario_name, metrics in report.scenario_results.items():
        assert isinstance(scenario_name, str)
        assert -1.0 <= metrics.mean_reward <= 1.0
        assert 0.0 <= metrics.success_rate <= 1.0
        assert metrics.mean_steps_to_resolution >= 0.0
