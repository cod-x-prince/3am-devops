"""
Programmatic grader for deterministic evaluation of agent performance.
Returns scores in [0, 100] based on objective metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class GraderResult:
    """Result from programmatic grading."""
    
    overall_score: float  # 0-100
    resolution_steps: int
    blast_radius_score: float  # 0-100
    false_positive_score: float  # 0-100
    efficiency_score: float  # 0-100
    all_healthy: bool
    details: Dict[str, Any]


def grade_episode(
    episode_steps: int,
    services_history: List[List[Dict[str, Any]]],
    actions_taken: List[List[int]],
    final_all_healthy: bool,
) -> GraderResult:
    """
    Grade an episode based on objective metrics.
    
    Args:
        episode_steps: Number of steps taken to resolve incident
        services_history: List of service states at each step
        actions_taken: List of [service_id, action_type] at each step
        final_all_healthy: Whether all services are healthy at end
    
    Returns:
        GraderResult with scores and details
    """
    
    # Resolution steps score (0-100)
    # Elite: ≤5 steps = 100, Linear decay to 50 steps = 0
    if episode_steps <= 5:
        resolution_score = 100.0
    elif episode_steps >= 50:
        resolution_score = 0.0
    else:
        resolution_score = 100.0 - ((episode_steps - 5) / 45.0) * 100.0
    
    # Blast radius score (0-100)
    # Measure how many services were affected over time
    max_unhealthy = 0
    total_unhealthy = 0
    
    for services_at_step in services_history:
        unhealthy_count = sum(
            1 for s in services_at_step
            if s.get("status") in ["Critical", "Down", "Degraded"]
        )
        max_unhealthy = max(max_unhealthy, unhealthy_count)
        total_unhealthy += unhealthy_count
    
    # Score: fewer affected services = higher score
    # 0 unhealthy = 100, 12 unhealthy = 0
    if max_unhealthy == 0:
        blast_radius_score = 100.0
    else:
        # Penalize based on max simultaneous failures
        blast_radius_score = max(0.0, 100.0 - (max_unhealthy / 12.0) * 100.0)
    
    # False positive score (0-100)
    # Penalize actions on healthy services and NoOps when problems exist
    false_positives = 0
    
    for i, action in enumerate(actions_taken):
        if i >= len(services_history):
            break
        
        service_id, action_type = action
        services_at_step = services_history[i]
        
        # NoOp is action_type 6
        if action_type == 6:
            # Check if there were any unhealthy services
            any_unhealthy = any(
                s.get("status") in ["Critical", "Down", "Degraded"]
                for s in services_at_step
            )
            if any_unhealthy:
                false_positives += 1
        else:
            # Check if action was on healthy service
            if service_id < len(services_at_step):
                target_service = services_at_step[service_id]
                if target_service.get("status") == "Healthy":
                    false_positives += 1
    
    # Score: fewer false positives = higher score
    if len(actions_taken) == 0:
        false_positive_score = 100.0
    else:
        false_positive_score = max(
            0.0, 100.0 - (false_positives / len(actions_taken)) * 100.0
        )
    
    # Efficiency score (0-100)
    # Combination of speed and action quality
    if episode_steps == 0:
        efficiency_score = 0.0
    else:
        # Fewer steps and fewer false positives = higher efficiency
        efficiency_score = (resolution_score * 0.7) + (false_positive_score * 0.3)
    
    # Overall score (weighted average)
    # Resolution: 40%, Blast radius: 30%, False positives: 20%, Efficiency: 10%
    overall_score = (
        resolution_score * 0.40
        + blast_radius_score * 0.30
        + false_positive_score * 0.20
        + efficiency_score * 0.10
    )
    
    # Bonus for complete resolution
    if final_all_healthy:
        overall_score = min(100.0, overall_score * 1.1)
    
    # Ensure bounds
    overall_score = max(0.0, min(100.0, overall_score))
    
    return GraderResult(
        overall_score=overall_score,
        resolution_steps=episode_steps,
        blast_radius_score=blast_radius_score,
        false_positive_score=false_positive_score,
        efficiency_score=efficiency_score,
        all_healthy=final_all_healthy,
        details={
            "resolution_score": resolution_score,
            "max_unhealthy_services": max_unhealthy,
            "total_unhealthy_steps": total_unhealthy,
            "false_positives": false_positives,
            "total_actions": len(actions_taken),
        }
    )
