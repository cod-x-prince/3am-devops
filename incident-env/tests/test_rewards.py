from __future__ import annotations

from rewards import blast_radius_reward, composite_reward, false_alarm_reward, mttr_reward
from tasks import TASKS, score_task


def test_reward_helpers_are_bounded():
    assert -1.0 <= mttr_reward(1) <= 1.0
    assert -1.0 <= mttr_reward(50) <= 1.0
    assert -1.0 <= blast_radius_reward(8, 4) <= 1.0
    assert -1.0 <= false_alarm_reward(0, 1) <= 1.0
    assert -1.0 <= composite_reward(4, 5, 2, 0, 2) <= 1.0


def test_score_task_returns_normalized_value():
    for spec in TASKS:
        score = score_task(
            task_id=spec.task_id,
            steps_to_resolution=3,
            previous_unhealthy=6,
            current_unhealthy=1,
            false_positives=0,
            total_actions=2,
        )
        assert 0.0 <= score <= 1.0


def test_task_catalog_has_three_levels():
    difficulties = [task.difficulty for task in TASKS]
    assert difficulties == ["easy", "medium", "hard"]
