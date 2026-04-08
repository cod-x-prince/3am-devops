from __future__ import annotations


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
	return max(low, min(high, value))


def blast_radius_reward(
	previous_unhealthy: int,
	current_unhealthy: int,
	total_services: int = 12,
) -> float:
	"""Reward shrinking the blast radius, penalize spread.

	Positive values indicate recovery progress; negative values indicate spread.
	"""
	total_services = max(1, total_services)
	delta = previous_unhealthy - current_unhealthy
	normalized_delta = delta / total_services

	if current_unhealthy == 0 and previous_unhealthy > 0:
		return 1.0

	return _clamp(normalized_delta * 2.0)
