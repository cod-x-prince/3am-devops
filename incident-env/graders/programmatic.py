from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GraderResult:
    all_healthy: bool
    resolution_steps: int
    blast_radius_score: float
    false_positive_count: int
    curriculum_level_passed: bool
    overall_score: float
    passed: bool


class ProgrammaticGrader:
    def grade(self, episode_history: list[dict], final_obs, resolved: bool) -> GraderResult:
        resolution_steps = len(episode_history)

        newly_degraded = [max(0, int(item.get("newly_degraded", 0))) for item in episode_history]
        mean_spread = (sum(newly_degraded) / max(1, len(newly_degraded))) if newly_degraded else 0.0
        blast_radius_score = float(max(0.0, min(1.0, 1.0 - (mean_spread / 12.0))))

        false_positive_count = 0
        for item in episode_history:
            action_taken = str(item.get("action_taken", ""))
            services_critical = int(item.get("services_critical", 0))
            services_down = int(item.get("services_down", 0))
            if action_taken.startswith("NoOp") and (services_critical > 0 or services_down > 0):
                false_positive_count += 1

        all_healthy = bool(resolved)
        if not all_healthy and final_obs is not None:
            try:
                arr = list(final_obs)
                if len(arr) >= 72:
                    unhealthy = 0
                    for i in range(0, 72, 6):
                        cpu, memory, error_rate, _, p99, _ = arr[i : i + 6]
                        health = 1.0 - (0.3 * float(cpu) + 0.25 * float(memory) + 0.3 * float(error_rate) + 0.15 * float(p99))
                        if health < 0.9:
                            unhealthy += 1
                    all_healthy = unhealthy == 0
            except Exception:
                all_healthy = bool(resolved)

        speed_score = max(0.0, min(1.0, 1.0 - (resolution_steps / 50.0)))
        false_alarm_score = max(0.0, min(1.0, 1.0 - false_positive_count / 10.0))

        overall_score = float(
            max(
                0.0,
                min(
                    100.0,
                    100.0
                    * (
                        0.45 * speed_score
                        + 0.35 * blast_radius_score
                        + 0.20 * false_alarm_score
                    ),
                ),
            )
        )

        curriculum_level_passed = overall_score >= 60.0 and all_healthy
        passed = curriculum_level_passed

        return GraderResult(
            all_healthy=all_healthy,
            resolution_steps=resolution_steps,
            blast_radius_score=blast_radius_score,
            false_positive_count=false_positive_count,
            curriculum_level_passed=curriculum_level_passed,
            overall_score=overall_score,
            passed=passed,
        )
