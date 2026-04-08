from __future__ import annotations


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
	return max(low, min(high, value))


def mttr_reward(
	steps_to_resolution: int,
	max_steps: int = 50,
	elite_steps: int = 5,
) -> float:
	"""Reward faster resolutions more highly, with partial progress signal.

	Returns a value in [-1.0, 1.0].
	"""
	if steps_to_resolution <= elite_steps:
		return 1.0
	if steps_to_resolution >= max_steps:
		return -1.0

	span = max(1, max_steps - elite_steps)
	progress = (steps_to_resolution - elite_steps) / span
	return _clamp(1.0 - 2.0 * progress)
