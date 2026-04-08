"""
LLM-based grader using Llama 3 for qualitative evaluation.
Provides reasoning and feedback on agent decisions.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class LLMGraderResult:
    """Result from LLM grading."""
    
    overall_assessment: str  # "excellent", "good", "fair", "poor"
    reasoning_quality: float  # 0-100
    decision_quality: float  # 0-100
    efficiency: float  # 0-100
    narrative: str
    suggestions: List[str]
    available: bool  # Whether LLM was available


def grade_with_llm(
    scenario: str,
    services_history: List[List[Dict[str, Any]]],
    actions_taken: List[List[int]],
    action_reasoning: List[str],
    final_all_healthy: bool,
    ollama_url: str = "http://localhost:11434",
    model: str = "llama3:8b-instruct-q4_K_M",
    timeout: int = 30,
) -> LLMGraderResult:
    """
    Grade episode using LLM for qualitative assessment.
    
    Args:
        scenario: Scenario name (e.g., "bad_deploy")
        services_history: Service states at each step
        actions_taken: Actions [service_id, action_type] at each step
        action_reasoning: Human-readable action descriptions
        final_all_healthy: Whether all services healthy at end
        ollama_url: Ollama API endpoint
        model: Model tag to use
        timeout: Request timeout in seconds
    
    Returns:
        LLMGraderResult with qualitative assessment
    """
    
    # Check if requests is available
    if not REQUESTS_AVAILABLE:
        logger.warning("requests library not available, using fallback grader")
        return _fallback_grader()
    
    # Build prompt
    prompt = _build_grading_prompt(
        scenario, services_history, actions_taken, action_reasoning, final_all_healthy
    )
    
    try:
        # Call Ollama API
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                }
            },
            timeout=timeout
        )
        
        if response.status_code != 200:
            logger.warning(f"Ollama returned status {response.status_code}, using fallback")
            return _fallback_grader()
        
        # Parse response
        result = response.json()
        llm_output = result.get("response", "{}")
        
        # Parse JSON from LLM
        try:
            grading = json.loads(llm_output)
        except json.JSONDecodeError:
            logger.warning("LLM did not return valid JSON, using fallback")
            return _fallback_grader()
        
        # Extract scores with validation
        return LLMGraderResult(
            overall_assessment=grading.get("overall_assessment", "fair"),
            reasoning_quality=_clamp(grading.get("reasoning_quality", 50.0), 0, 100),
            decision_quality=_clamp(grading.get("decision_quality", 50.0), 0, 100),
            efficiency=_clamp(grading.get("efficiency", 50.0), 0, 100),
            narrative=grading.get("narrative", "Agent completed the task."),
            suggestions=grading.get("suggestions", []),
            available=True
        )
        
    except requests.exceptions.Timeout:
        logger.warning("Ollama request timed out, using fallback")
        return _fallback_grader()
    except requests.exceptions.ConnectionError:
        logger.warning("Could not connect to Ollama, using fallback")
        return _fallback_grader()
    except Exception as e:
        logger.warning(f"Unexpected error calling Ollama: {e}, using fallback")
        return _fallback_grader()


def _build_grading_prompt(
    scenario: str,
    services_history: List[List[Dict[str, Any]]],
    actions_taken: List[List[int]],
    action_reasoning: List[str],
    final_all_healthy: bool,
) -> str:
    """Build grading prompt for LLM."""
    
    initial_state = services_history[0] if services_history else []
    final_state = services_history[-1] if services_history else []
    
    initial_unhealthy = sum(
        1 for s in initial_state
        if s.get("status") in ["Critical", "Down", "Degraded"]
    )
    
    final_unhealthy = sum(
        1 for s in final_state
        if s.get("status") in ["Critical", "Down", "Degraded"]
    )
    
    prompt = f"""You are an expert SRE evaluating an autonomous incident response agent.

Scenario: {scenario}
Initial unhealthy services: {initial_unhealthy}/12
Final unhealthy services: {final_unhealthy}/12
Resolution successful: {final_all_healthy}
Steps taken: {len(actions_taken)}

Actions taken:
{chr(10).join(f"{i+1}. {reasoning}" for i, reasoning in enumerate(action_reasoning))}

Evaluate the agent's performance and respond in JSON format:
{{
  "overall_assessment": "excellent|good|fair|poor",
  "reasoning_quality": <0-100 score>,
  "decision_quality": <0-100 score>,
  "efficiency": <0-100 score>,
  "narrative": "<2-3 sentence summary>",
  "suggestions": ["<suggestion 1>", "<suggestion 2>"]
}}

Consider:
1. Did the agent identify the root cause quickly?
2. Were actions appropriate and effective?
3. Did the agent avoid unnecessary actions?
4. Was the resolution efficient?

Respond ONLY with valid JSON, no other text."""
    
    return prompt


def _fallback_grader() -> LLMGraderResult:
    """Return neutral grader result when LLM is unavailable."""
    return LLMGraderResult(
        overall_assessment="fair",
        reasoning_quality=50.0,
        decision_quality=50.0,
        efficiency=50.0,
        narrative="LLM grader unavailable. Programmatic grading recommended.",
        suggestions=["Ensure Ollama is running with llama3:8b-instruct-q4_K_M model"],
        available=False
    )


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value to range [min_val, max_val]."""
    return max(min_val, min(max_val, value))
