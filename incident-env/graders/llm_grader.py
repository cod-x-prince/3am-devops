from __future__ import annotations

import json
import os
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

try:
    import ollama
except Exception:  # pragma: no cover
    ollama = None


SYSTEM_PROMPT = (
    "You are a Senior SRE evaluating an AI incident response. "
    "Respond ONLY with valid JSON object matching the requested schema."
)


class _LLMResultModel(BaseModel):
    root_cause_identification: int
    remediation_appropriateness: int
    blast_radius_minimization: int
    action_efficiency: int
    reasoning: str
    overall: float


@dataclass
class LLMGraderResult:
    root_cause_identification: int
    remediation_appropriateness: int
    blast_radius_minimization: int
    action_efficiency: int
    reasoning: str
    overall: float

    @classmethod
    def fallback(cls) -> "LLMGraderResult":
        return cls(
            root_cause_identification=5,
            remediation_appropriateness=5,
            blast_radius_minimization=5,
            action_efficiency=5,
            reasoning="Fallback result: LLM grading unavailable.",
            overall=5.0,
        )


class LLMGrader:
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3:8b-instruct-q4_K_M")

    def _parse(self, content: str) -> LLMGraderResult:
        raw = content.strip()
        if raw.startswith("```"):
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                raw = raw[start : end + 1]

        payload = json.loads(raw)
        validated = _LLMResultModel(**payload)
        return LLMGraderResult(**validated.model_dump())

    def grade(
        self,
        incident_description: str,
        action_sequence: list[str],
        final_service_states: dict,
        resolved: bool,
    ) -> LLMGraderResult:
        if ollama is None:
            return LLMGraderResult.fallback()

        user_prompt = {
            "incident_description": incident_description,
            "action_sequence": action_sequence,
            "final_service_states": final_service_states,
            "resolved": bool(resolved),
            "required_output_schema": {
                "root_cause_identification": "int 0-10",
                "remediation_appropriateness": "int 0-10",
                "blast_radius_minimization": "int 0-10",
                "action_efficiency": "int 0-10",
                "reasoning": "string",
                "overall": "float 0-10",
            },
        }

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(user_prompt)},
                ],
            )
            content = response.get("message", {}).get("content", "")
            return self._parse(content)
        except (json.JSONDecodeError, ValidationError, KeyError, TypeError, Exception):
            return LLMGraderResult.fallback()
