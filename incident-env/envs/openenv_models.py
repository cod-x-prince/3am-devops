from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ObservationModel(BaseModel):
    """Typed OpenEnv observation for IncidentEnv."""

    values: list[float] = Field(min_length=72, max_length=72)

    @field_validator("values")
    @classmethod
    def validate_bounds(cls, values: list[float]) -> list[float]:
        normalized = [float(value) for value in values]
        for value in normalized:
            if value < 0.0 or value > 1.0:
                raise ValueError("observation values must be in [0.0, 1.0]")
        return normalized


class ActionModel(BaseModel):
    """Typed OpenEnv action for IncidentEnv."""

    service_id: int = Field(ge=0, le=11)
    action_type: int = Field(ge=0, le=6)

    def as_list(self) -> list[int]:
        return [self.service_id, self.action_type]


class RewardModel(BaseModel):
    """Typed OpenEnv reward for IncidentEnv."""

    value: float = Field(ge=-1.0, le=1.0)


class StepResultModel(BaseModel):
    """Typed OpenEnv step payload."""

    observation: ObservationModel
    reward: RewardModel
    done: bool
    info: dict[str, Any]
