from __future__ import annotations

from typing import Any

from .incident_env import IncidentEnv
from .openenv_models import ActionModel, ObservationModel, RewardModel


class OpenIncidentEnv:
    """OpenEnv-compatible adapter with typed Pydantic models."""

    def __init__(
        self,
        scenario: str = "bad_deploy",
        curriculum_level: int = 1,
        max_steps: int = 50,
        **kwargs: Any,
    ) -> None:
        self._env = IncidentEnv(
            scenario=scenario,
            curriculum_level=curriculum_level,
            max_steps=max_steps,
            **kwargs,
        )
        self.observation_space = self._env.observation_space
        self.action_space = self._env.action_space
        self.state_space = self._env.state_space

    def reset(self) -> ObservationModel:
        observation, _ = self._env.reset()
        return ObservationModel(values=observation.tolist())

    def step(
        self, action: ActionModel | dict[str, int]
    ) -> tuple[ObservationModel, RewardModel, bool, dict[str, Any]]:
        action_model = (
            action if isinstance(action, ActionModel) else ActionModel.model_validate(action)
        )
        observation, reward, terminated, truncated, info = self._env.step(action_model.as_list())
        done = bool(terminated or truncated)
        return (
            ObservationModel(values=observation.tolist()),
            RewardModel(value=float(reward)),
            done,
            info,
        )

    def state(self) -> dict[str, Any]:
        return self._env.state()

    def close(self) -> None:
        self._env.close()
