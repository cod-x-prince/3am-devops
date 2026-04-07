from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import sys

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

from tests.mock_env import MockIncidentEnv


@dataclass
class ScenarioMetrics:
	mean_reward: float
	mean_steps_to_resolution: float
	mean_false_positives: float


@dataclass
class EvalReport:
	scenario_results: dict[str, ScenarioMetrics]
	overall_score: float
	mean_mttr_steps: float
	mean_blast_radius: float
	false_positive_rate: float
	curriculum_level_reached: int
	vs_human_baseline: str


def run_random_policy_eval(episodes: int = 25) -> EvalReport:
	env = MockIncidentEnv(max_steps=30, seed=7)
	rewards = []
	steps = []
	false_positives = []

	for _ in range(episodes):
		obs, _ = env.reset()
		done = False
		ep_reward = 0.0
		ep_steps = 0
		ep_false = 0

		while not done:
			action = env.action_space.sample()
			obs, reward, terminated, truncated, info = env.step(action)
			done = terminated or truncated
			ep_reward += reward
			ep_steps += 1
			if action[1] == 6 and info.get("services_critical", 0) > 0:
				ep_false += 1

		rewards.append(ep_reward)
		steps.append(ep_steps)
		false_positives.append(ep_false)

	scenario_metrics = ScenarioMetrics(
		mean_reward=float(np.mean(rewards)),
		mean_steps_to_resolution=float(np.mean(steps)),
		mean_false_positives=float(np.mean(false_positives)),
	)

	overall_score = float(np.clip((scenario_metrics.mean_reward + 1.0) * 50.0, 0.0, 100.0))
	report = EvalReport(
		scenario_results={"mock_bad_deploy": scenario_metrics},
		overall_score=overall_score,
		mean_mttr_steps=scenario_metrics.mean_steps_to_resolution,
		mean_blast_radius=0.5,
		false_positive_rate=float(np.mean(false_positives) / max(1, int(np.mean(steps)))),
		curriculum_level_reached=1,
		vs_human_baseline=f"Agent: {scenario_metrics.mean_steps_to_resolution:.1f} steps | Human: 4.2hr",
	)
	return report


if __name__ == "__main__":
	result = run_random_policy_eval(episodes=20)
	print(asdict(result))
