from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from envs import ActionModel, IncidentEnv, ObservationModel, OpenIncidentEnv, RewardModel


def test_incident_env_spaces_and_reset() -> None:
    env = IncidentEnv()
    assert env.observation_space.shape == (72,)
    assert list(env.action_space.nvec) == [12, 7]

    observation, info = env.reset()
    assert observation.shape == (72,)
    assert info["scenario"] == "bad_deploy"
    assert info["num_services"] == 12


def test_incident_env_state_is_serializable_and_updates() -> None:
    env = IncidentEnv()
    env.reset()

    state = env.state()
    assert state["scenario"] == "bad_deploy"
    assert state["step_count"] == 0
    assert len(state["observation"]) == 72
    assert len(state["engine_state"]["services"]) == 12

    json.dumps(state)

    observation, reward, terminated, truncated, info = env.step(np.array([3, 2]))
    assert observation.shape == (72,)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert info["step_count"] == 1

    updated = env.state()
    assert updated["step_count"] == 1
    assert updated["last_reward"] == reward


def test_scenarios_differentiate_fault_profiles() -> None:
    easy_env = IncidentEnv(scenario="bad_deploy")
    medium_env = IncidentEnv(scenario="cascade_timeout")
    hard_env = IncidentEnv(scenario="multi_fault")

    _, easy_info = easy_env.reset()
    _, medium_info = medium_env.reset()
    _, hard_info = hard_env.reset()

    assert len(easy_info["active_faults"]) == 1
    assert len(medium_info["active_faults"]) >= 1
    assert len(hard_info["active_faults"]) >= 2


def test_openenv_typed_interface() -> None:
    env = OpenIncidentEnv(scenario="bad_deploy", max_steps=10)
    observation = env.reset()
    assert isinstance(observation, ObservationModel)
    assert len(observation.values) == 72

    action = ActionModel(service_id=3, action_type=2)
    next_observation, reward, done, info = env.step(action)
    assert isinstance(next_observation, ObservationModel)
    assert isinstance(reward, RewardModel)
    assert isinstance(done, bool)
    assert isinstance(info, dict)
    assert "current_unhealthy" in info

    state = env.state()
    assert isinstance(state, dict)
    env.close()


def test_openenv_submission_files_exist() -> None:
    project_root = Path(__file__).resolve().parents[1]
    assert (project_root / "openenv.yaml").exists()
    assert (project_root / "inference.py").exists()
    assert (project_root / "Dockerfile").exists()
