from __future__ import annotations

from .blast_radius import blast_radius_reward
from .false_alarm import false_alarm_reward
from .mttr import mttr_reward


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
	return max(low, min(high, value))


def composite_reward(
	steps_to_resolution: int,
	previous_unhealthy: int,
	current_unhealthy: int,
	false_positives: int,
	total_actions: int,
	max_steps: int = 50,
) -> float:
	"""Blend partial-progress signals into a single bounded reward.

	The weights favor fast resolution, then blast-radius reduction, then
	avoiding false positives.
	"""
	mttr = mttr_reward(steps_to_resolution, max_steps=max_steps)
	blast = blast_radius_reward(previous_unhealthy, current_unhealthy)
	false_alarm = false_alarm_reward(false_positives, total_actions=max(total_actions, 1))

	# Normalize to a smooth, bounded reward in [-1, 1].
	reward = (0.5 * mttr) + (0.3 * blast) + (0.2 * false_alarm)
	return _clamp(reward)
