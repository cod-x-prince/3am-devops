import json

from graders.llm_grader import LLMGrader, LLMGraderResult
from graders.programmatic import ProgrammaticGrader


def test_programmatic_grader_score_range():
    grader = ProgrammaticGrader()
    history = [
        {
            "tick": 1,
            "action_taken": "RestartService(service_1)",
            "newly_degraded": 1,
            "services_critical": 2,
            "services_down": 0,
        },
        {
            "tick": 2,
            "action_taken": "NoOp(service_2)",
            "newly_degraded": 0,
            "services_critical": 1,
            "services_down": 0,
        },
    ]
    result = grader.grade(episode_history=history, final_obs=[0.0] * 72, resolved=False)

    assert 0.0 <= result.blast_radius_score <= 1.0
    assert 0.0 <= result.overall_score <= 100.0
    assert isinstance(result.passed, bool)


def test_llm_grader_schema_parsing(monkeypatch):
    payload = {
        "root_cause_identification": 8,
        "remediation_appropriateness": 7,
        "blast_radius_minimization": 8,
        "action_efficiency": 6,
        "reasoning": "Reasonable action sequence.",
        "overall": 7.25,
    }

    class _FakeOllama:
        @staticmethod
        def chat(**kwargs):
            return {"message": {"content": json.dumps(payload)}}

    import graders.llm_grader as llm_module

    monkeypatch.setattr(llm_module, "ollama", _FakeOllama)

    grader = LLMGrader(model="llama3:8b-instruct-q4_K_M")
    result = grader.grade(
        incident_description="Bad deploy on service_1",
        action_sequence=["RollbackDeploy(service_1)"],
        final_service_states={"services": []},
        resolved=True,
    )

    assert isinstance(result, LLMGraderResult)
    assert 0 <= result.root_cause_identification <= 10
    assert 0.0 <= result.overall <= 10.0


def test_llm_grader_fallback_when_unavailable(monkeypatch):
    class _FailingOllama:
        @staticmethod
        def chat(**kwargs):
            raise RuntimeError("unavailable")

    import graders.llm_grader as llm_module

    monkeypatch.setattr(llm_module, "ollama", _FailingOllama)

    result = LLMGrader().grade(
        incident_description="incident",
        action_sequence=[],
        final_service_states={},
        resolved=False,
    )
    assert result == LLMGraderResult.fallback()
