from pathlib import Path

from packages.core.attribution.engine import Attribution
from packages.core.reporting.generator import generate_report
from packages.core.scoring.engine import DimensionScores, TaskScore
from packages.core.skill_profile.parser import parse_skill_dir
from packages.generators.spec_generator.generator import generate_eval_spec
from packages.generators.task_generator.generator import generate_tasks
from packages.runners.runner import EvalRun, TaskResult

from packages.core.validation import (
    validate_eval_report,
    validate_eval_run,
    validate_eval_spec,
    validate_skill_profile,
    validate_task,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_SKILL = PROJECT_ROOT / "examples" / "sample-skill"


def _sample_profile():
    return parse_skill_dir(SAMPLE_SKILL)


def _sample_spec():
    return generate_eval_spec(_sample_profile(), model="gpt-4o-mini", task_count=6)


def _sample_tasks():
    return generate_tasks(_sample_profile(), _sample_spec())


def _sample_run(run_type: str) -> EvalRun:
    task = _sample_tasks()[0]
    return EvalRun(
        run_id=f"{run_type}-001",
        eval_spec_id="spec-001",
        run_type=run_type,
        config={
            "model": "gpt-4o-mini",
            "temperature": 0.0,
            "system_prompt": "You are a helpful AI assistant.",
            "tools": ["web_search"],
            "timeout_seconds": 30,
            "seed": 42,
        },
        started_at="2026-03-19T10:00:00",
        completed_at="2026-03-19T10:00:02",
        task_results=[
            TaskResult(
                task_id=task.task_id,
                output="Summary: clear answer\nActions: verify requirements",
                tool_calls=[{"tool": "web_search", "input": {"q": "sample"}, "output": {"ok": True}}],
                duration_ms=1250,
                tokens_input=120,
                tokens_output=80,
                skill_triggered=run_type == "with_skill",
                skill_trigger_count=1 if run_type == "with_skill" else 0,
            )
        ],
    )


def _sample_report():
    profile = _sample_profile()
    spec = _sample_spec()
    tasks = _sample_tasks()
    baseline_run = _sample_run("baseline")
    skill_run = _sample_run("with_skill")
    baseline_scores = DimensionScores(effectiveness=20, quality=12, efficiency=10, stability=10, trigger_fitness=7, safety=9)
    skill_scores = DimensionScores(effectiveness=24, quality=15, efficiency=9, stability=10, trigger_fitness=8, safety=9)
    baseline_task_scores = [TaskScore(task_id=tasks[0].task_id, dimensions=baseline_scores, notes=["baseline evidence"])]
    skill_task_scores = [TaskScore(task_id=tasks[0].task_id, dimensions=skill_scores, notes=["skill evidence"])]
    attribution = Attribution(summary="Skill improved structure.", trigger_analysis={"trigger_rate": 1.0})
    return generate_report(
        profile,
        spec,
        baseline_run,
        skill_run,
        baseline_scores,
        skill_scores,
        baseline_task_scores,
        skill_task_scores,
        attribution,
    )


def test_generated_profile_validates_against_schema():
    profile = _sample_profile()
    validate_skill_profile(profile)


def test_generated_eval_spec_validates_against_schema():
    spec = _sample_spec()
    validate_eval_spec(spec)


def test_generated_tasks_validate_against_schema():
    for task in _sample_tasks():
        validate_task(task)


def test_generated_run_validates_against_schema():
    validate_eval_run(_sample_run("with_skill"))


def test_generated_report_validates_against_schema():
    validate_eval_report(_sample_report())
