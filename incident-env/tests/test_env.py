import json

import gymnasium as gym
import numpy as np

from envs.incident_env import IncidentEnv
from envs.scenarios import list_scenarios


def test_env_contract_shapes():
    env = IncidentEnv(scenario="bad_deploy", curriculum_level=1)
    assert env.observation_space.shape == (72,)
    assert isinstance(env.action_space, gym.spaces.MultiDiscrete)
    assert env.action_space.nvec.tolist() == [12, 7]

    obs, info = env.reset()
    assert isinstance(obs, np.ndarray)
    assert obs.shape == (72,)
    assert obs.dtype == np.float32
    assert "services_json" in info


def test_env_step_contract_and_reward_bounds():
    env = IncidentEnv(scenario="bad_deploy", curriculum_level=1)
    env.reset()
    action = np.array([1, 0], dtype=np.int64)
    obs, reward, terminated, truncated, info = env.step(action)

    assert obs.shape == (72,)
    assert -1.0 <= float(reward) <= 1.0
    assert isinstance(terminated, bool)
    assert truncated is False

    required = {
        "tick",
        "action_taken",
        "newly_degraded",
        "services_healthy",
        "services_critical",
        "services_down",
        "cumulative_reward",
        "curriculum_level",
        "scenario",
        "services_json",
    }
    assert required.issubset(info.keys())

    parsed = json.loads(info["services_json"])
    assert "services" in parsed
    assert "connections" in parsed


def test_env_eventually_terminates():
    env = IncidentEnv(scenario="memory_leak", curriculum_level=1)
    env.reset()
    done = False
    for _ in range(60):
        _, _, terminated, truncated, _ = env.step(env.action_space.sample())
        done = terminated or truncated
        if done:
            break
    assert done is True


def test_all_scenarios_load():
    names = list_scenarios()
    assert len(names) >= 6
    for name in names:
        env = IncidentEnv(scenario=name, curriculum_level=1)
        obs, _ = env.reset()
        assert obs.shape == (72,)
