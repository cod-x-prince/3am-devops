from __future__ import annotations


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
	return max(low, min(high, value))


def false_alarm_reward(false_positives: int, total_actions: int = 1) -> float:
	"""Penalize unnecessary actions while keeping reward bounded.

	Returns 1.0 when there are no false positives and trends toward -1.0 as
	the proportion of false positives increases.
	"""
	total_actions = max(1, total_actions)
	rate = false_positives / total_actions
	return _clamp(1.0 - 2.0 * rate)
