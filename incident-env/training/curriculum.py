from __future__ import annotations

from collections import deque


class CurriculumScheduler:
	THRESHOLDS = {1: 0.60, 2: 0.65, 3: 0.70, 4: 0.75, 5: 0.80}
	WINDOW = 50

	def __init__(self):
		self.current_level = 1
		self.recent_rewards = deque(maxlen=self.WINDOW)

	def update(self, episode_reward: float) -> bool:
		"""Return True when curriculum level advances."""
		self.recent_rewards.append(float(episode_reward))

		if len(self.recent_rewards) < self.WINDOW:
			return False

		threshold = self.THRESHOLDS.get(self.current_level, 1.0)
		avg_reward = sum(self.recent_rewards) / len(self.recent_rewards)
		if avg_reward <= threshold:
			return False

		if self.current_level >= 5:
			return False

		self.current_level += 1
		self.recent_rewards.clear()
		return True
