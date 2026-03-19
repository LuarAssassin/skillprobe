"""Pairwise LLM judge scoring utilities."""

from __future__ import annotations

import json
from pathlib import Path

from litellm import completion

from packages.generators.task_generator.models import Task
from packages.runners.runner import EvalRun


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_JUDGE_PROMPT_PATH = _PROJECT_ROOT / "prompts" / "llm_judge" / "compare_outputs.txt"


def build_pairwise_llm_judge_maps(
    tasks: list[Task],
    baseline_run: EvalRun,
    skill_run: EvalRun,
    *,
    model: str,
    timeout_seconds: int = 120,
) -> tuple[dict[str, float], dict[str, float], list[str]]:
    """Return normalized (0-1) judge scores for baseline and with-skill outputs."""
    baseline_by_task = {result.task_id: result for result in baseline_run.task_results}
    skill_by_task = {result.task_id: result for result in skill_run.task_results}
    template = _JUDGE_PROMPT_PATH.read_text(encoding="utf-8")

    baseline_scores: dict[str, float] = {}
    skill_scores: dict[str, float] = {}
    warnings: list[str] = []

    for task in tasks:
        baseline_result = baseline_by_task.get(task.task_id)
        skill_result = skill_by_task.get(task.task_id)
        if baseline_result is None or skill_result is None:
            continue
        if baseline_result.error or skill_result.error:
            continue

        prompt = _render_prompt(template, task, baseline_result.output, skill_result.output)

        try:
            response = completion(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert evaluator. Respond only with valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                timeout=timeout_seconds,
            )
            content = response.choices[0].message.content or ""
            parsed = _parse_json_object(content)
            baseline_scores_raw = parsed.get("scores_a")
            skill_scores_raw = parsed.get("scores_b")
            baseline_score = _normalized_score(baseline_scores_raw)
            skill_score = _normalized_score(skill_scores_raw)

            if baseline_score is None or skill_score is None:
                warnings.append(f"LLM judge returned invalid scores for task {task.task_id}")
                continue

            baseline_scores[task.task_id] = baseline_score
            skill_scores[task.task_id] = skill_score
        except Exception as exc:
            warnings.append(f"LLM judge failed for task {task.task_id}: {exc}")

    return baseline_scores, skill_scores, warnings


def _render_prompt(template: str, task: Task, baseline_output: str, skill_output: str) -> str:
    return template.format(
        task_prompt=task.prompt,
        task_context=task.context or "(none)",
        baseline_output=baseline_output,
        skill_output=skill_output,
        key_points=", ".join(task.scoring_hints.key_points) or "(none)",
        anti_patterns=", ".join(task.scoring_hints.anti_patterns) or "(none)",
    )


def _parse_json_object(content: str) -> dict:
    content = content.strip()
    if not content:
        return {}

    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(content[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    return {}


def _normalized_score(raw_scores: object) -> float | None:
    if not isinstance(raw_scores, dict):
        return None

    numeric_values: list[float] = []
    for value in raw_scores.values():
        if isinstance(value, (int, float)):
            numeric_values.append(float(value))

    if not numeric_values:
        return None

    average_0_10 = sum(numeric_values) / len(numeric_values)
    clamped = max(0.0, min(10.0, average_0_10))
    return clamped / 10.0
