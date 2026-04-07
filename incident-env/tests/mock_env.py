import gymnasium as gym
import numpy as np


class MockIncidentEnv(gym.Env):
    """Contract-compatible mock environment for Track B unblock work."""

    metadata = {"render_modes": []}

    def __init__(self, max_steps: int = 30, seed: int | None = None):
        super().__init__()
        self.observation_space = gym.spaces.Box(
            low=0.0,
            high=1.0,
            shape=(72,),
            dtype=np.float32,
        )
        self.action_space = gym.spaces.MultiDiscrete([12, 7])
        self.max_steps = max_steps
        self._rng = np.random.default_rng(seed)
        self._step_count = 0

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        self._step_count = 0
        obs = self._sample_obs()
        info = {
            "scenario": "mock_bad_deploy",
            "curriculum_level": 1,
            "num_services": 12,
        }
        return obs, info

    def step(self, action):
        self._step_count += 1

        target_service, action_type = int(action[0]), int(action[1])
        base_reward = float(self._rng.uniform(-0.02, 0.02))
        action_bias = 0.02 if action_type in (0, 2, 5) else -0.005
        reward = float(np.clip(base_reward + action_bias, -1.0, 1.0))

        terminated = bool(self._rng.random() < 0.04)
        if self._step_count >= self.max_steps:
            terminated = True
        truncated = False

        obs = self._sample_obs()
        info = {
            "tick": self._step_count,
            "action_taken": f"{action_type}@service_{target_service}",
            "newly_degraded": int(self._rng.integers(0, 2)),
            "services_healthy": int(self._rng.integers(6, 12)),
            "services_critical": int(self._rng.integers(0, 4)),
            "services_down": int(self._rng.integers(0, 2)),
            "cumulative_reward": reward,
            "curriculum_level": 1,
            "scenario": "mock_bad_deploy",
            "services_json": "{}",
        }
        return obs, reward, terminated, truncated, info

    def _sample_obs(self) -> np.ndarray:
        return self._rng.uniform(0.0, 1.0, size=(72,)).astype(np.float32)
