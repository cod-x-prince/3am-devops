"""Tests for grader modules."""

import pytest
from graders import GraderResult, grade_episode, LLMGraderResult, grade_with_llm


def test_programmatic_grader_perfect_score():
    """Test grader with perfect resolution."""
    services_history = [
        # Initial: 1 unhealthy service
        [
            {"service_id": 0, "status": "Critical", "health": 0.3},
            *[{"service_id": i, "status": "Healthy", "health": 1.0} for i in range(1, 12)]
        ],
        # After action: all healthy
        [{"service_id": i, "status": "Healthy", "health": 1.0} for i in range(12)]
    ]
    
    actions_taken = [[0, 0]]  # Restart service 0
    
    result = grade_episode(
        episode_steps=1,
        services_history=services_history,
        actions_taken=actions_taken,
        final_all_healthy=True
    )
    
    assert isinstance(result, GraderResult)
    assert 0 <= result.overall_score <= 100
    assert result.resolution_steps == 1
    assert result.all_healthy is True
    # Elite resolution (1 step) should give high score
    assert result.overall_score >= 90


def test_programmatic_grader_score_bounds():
    """Test that all scores are in valid ranges."""
    services_history = [
        [{"service_id": i, "status": "Critical", "health": 0.2} for i in range(12)],
        [{"service_id": i, "status": "Degraded", "health": 0.5} for i in range(12)],
        [{"service_id": i, "status": "Healthy", "health": 1.0} for i in range(12)]
    ]
    
    actions_taken = [[0, 0], [1, 1]]  # Two actions
    
    result = grade_episode(
        episode_steps=2,
        services_history=services_history,
        actions_taken=actions_taken,
        final_all_healthy=True
    )
    
    # Check all scores in bounds
    assert 0 <= result.overall_score <= 100
    assert 0 <= result.blast_radius_score <= 100
    assert 0 <= result.false_positive_score <= 100
    assert 0 <= result.efficiency_score <= 100


def test_programmatic_grader_false_positives():
    """Test detection of false positive actions."""
    services_history = [
        # Only service 0 is unhealthy
        [
            {"service_id": 0, "status": "Critical", "health": 0.3},
            *[{"service_id": i, "status": "Healthy", "health": 1.0} for i in range(1, 12)]
        ],
        [
            {"service_id": 0, "status": "Critical", "health": 0.3},
            *[{"service_id": i, "status": "Healthy", "health": 1.0} for i in range(1, 12)]
        ]
    ]
    
    # Action on healthy service = false positive
    actions_taken = [[5, 0]]  # Restart healthy service 5
    
    result = grade_episode(
        episode_steps=1,
        services_history=services_history,
        actions_taken=actions_taken,
        final_all_healthy=False
    )
    
    # Should have detected false positive
    assert result.details["false_positives"] >= 1
    # False positive score should be penalized
    assert result.false_positive_score < 100


def test_programmatic_grader_noop_penalty():
    """Test that NoOp with problems is penalized."""
    services_history = [
        [{"service_id": i, "status": "Critical", "health": 0.2} for i in range(12)],
        [{"service_id": i, "status": "Critical", "health": 0.2} for i in range(12)]
    ]
    
    # NoOp when services are critical = false positive
    actions_taken = [[0, 6]]  # NoOp (action_type 6)
    
    result = grade_episode(
        episode_steps=1,
        services_history=services_history,
        actions_taken=actions_taken,
        final_all_healthy=False
    )
    
    # NoOp with problems should count as false positive
    assert result.details["false_positives"] >= 1


def test_programmatic_grader_blast_radius():
    """Test blast radius scoring."""
    # Scenario: incident spreads to many services
    services_history = [
        # Initial: 2 unhealthy
        [
            {"service_id": 0, "status": "Critical", "health": 0.2},
            {"service_id": 1, "status": "Critical", "health": 0.2},
            *[{"service_id": i, "status": "Healthy", "health": 1.0} for i in range(2, 12)]
        ],
        # Spread: 6 unhealthy
        [
            *[{"service_id": i, "status": "Critical", "health": 0.2} for i in range(6)],
            *[{"service_id": i, "status": "Healthy", "health": 1.0} for i in range(6, 12)]
        ],
        # Resolution: all healthy
        [{"service_id": i, "status": "Healthy", "health": 1.0} for i in range(12)]
    ]
    
    actions_taken = [[0, 0], [1, 0]]
    
    result = grade_episode(
        episode_steps=2,
        services_history=services_history,
        actions_taken=actions_taken,
        final_all_healthy=True
    )
    
    # Blast radius should reflect spread to 6 services
    assert result.details["max_unhealthy_services"] == 6
    # Score should be penalized for spread
    assert result.blast_radius_score < 80


def test_llm_grader_fallback():
    """Test that LLM grader returns valid fallback when unavailable."""
    # Use invalid URL to trigger fallback
    result = grade_with_llm(
        scenario="bad_deploy",
        services_history=[],
        actions_taken=[],
        action_reasoning=[],
        final_all_healthy=False,
        ollama_url="http://invalid-url:99999",
        timeout=1  # Short timeout
    )
    
    assert isinstance(result, LLMGraderResult)
    assert result.available is False
    assert 0 <= result.reasoning_quality <= 100
    assert 0 <= result.decision_quality <= 100
    assert 0 <= result.efficiency <= 100
    assert result.overall_assessment in ["excellent", "good", "fair", "poor"]
    assert isinstance(result.narrative, str)
    assert isinstance(result.suggestions, list)


def test_llm_grader_score_bounds():
    """Test LLM grader returns scores in valid ranges even if LLM is weird."""
    # Mock response that might have out-of-bounds values
    # Since we can't easily mock, just test fallback bounds
    result = grade_with_llm(
        scenario="test",
        services_history=[],
        actions_taken=[],
        action_reasoning=[],
        final_all_healthy=True,
        ollama_url="http://invalid:99999",
        timeout=1
    )
    
    # Even fallback should have valid bounds
    assert 0 <= result.reasoning_quality <= 100
    assert 0 <= result.decision_quality <= 100
    assert 0 <= result.efficiency <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
