"""
IncidentEnv - OpenEnv-compatible environment for autonomous incident remediation.
"""

from __future__ import annotations

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from typing import Any, Dict, Tuple

import incident_core


class IncidentEnv(gym.Env):
    """
    Incident remediation environment with 12 microservices.
    
    Observation space: (72,) - 12 services × 6 metrics
    Action space: MultiDiscrete([12, 7]) - service_id, action_type
    """
    
    metadata = {"render_modes": []}
    
    def __init__(
        self,
        scenario: str = "bad_deploy",
        curriculum_level: int = 1,
        max_steps: int = 50,
        **kwargs
    ):
        super().__init__()
        
        self.scenario = scenario
        self.curriculum_level = curriculum_level
        self.max_steps = max_steps
        
        # Initialize Rust engine
        self.engine = incident_core.RustServiceGraph(scenario, curriculum_level)
        
        # Define spaces
        self.observation_space = spaces.Box(
            low=0.0,
            high=1.0,
            shape=(72,),
            dtype=np.float32
        )
        
        self.action_space = spaces.MultiDiscrete([12, 7])
        
        self._step_count = 0
    
    def reset(
        self,
        *,
        seed: int | None = None,
        options: Dict[str, Any] | None = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reset the environment to initial state."""
        super().reset(seed=seed)
        
        obs = self.engine.reset()
        self._step_count = 0
        
        info = {
            "scenario": self.scenario,
            "curriculum_level": self.curriculum_level,
            "num_services": 12,
        }
        
        return np.array(obs, dtype=np.float32), info
    
    def step(
        self, action: np.ndarray | list
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        Execute one step in the environment.
        
        Args:
            action: [service_id (0-11), action_type (0-6)]
        
        Returns:
            obs, reward, terminated, truncated, info
        """
        if isinstance(action, np.ndarray):
            action = action.tolist()
        
        # Ensure action is list of ints
        action = [int(action[0]), int(action[1])]
        
        obs, reward, terminated, truncated, info = self.engine.step(action)
        self._step_count += 1
        
        # Convert obs to numpy array
        obs = np.array(obs, dtype=np.float32)
        
        # Add step count to info
        info["step_count"] = self._step_count
        
        return obs, float(reward), bool(terminated), bool(truncated), info
    
    def render(self):
        """Render the environment (no-op for now)."""
        pass
    
    def close(self):
        """Clean up resources."""
        pass
