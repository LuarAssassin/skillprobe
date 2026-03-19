import sqlite3

from apps.cli.main import _persist_evaluation_to_db
from packages.core.scoring.engine import DimensionScores, TaskScore
from packages.core.skill_profile.parser import parse_skill_dir
from packages.generators.spec_generator.generator import generate_eval_spec
from packages.generators.task_generator.generator import generate_tasks
from packages.runners.runner import EvalRun, TaskResult


def test_persist_evaluation_to_db_writes_summary_and_task_rows(tmp_path):
    profile = parse_skill_dir("examples/sample-skill")
    spec = generate_eval_spec(profile, model="test-model", task_count=6)
    task = generate_tasks(profile, spec)[0]

    baseline_run = EvalRun(
        run_id="baseline-001",
        eval_spec_id=spec.id,
        run_type="baseline",
        task_results=[TaskResult(task_id=task.task_id, output="baseline output")],
    )
    skill_run = EvalRun(
        run_id="skill-001",
        eval_spec_id=spec.id,
        run_type="with_skill",
        task_results=[TaskResult(task_id=task.task_id, output="skill output", skill_triggered=True, skill_trigger_count=1)],
    )

    baseline_task_scores = [
        TaskScore(
            task_id=task.task_id,
            dimensions=DimensionScores(effectiveness=10, quality=8, efficiency=9, stability=10, trigger_fitness=8, safety=9),
            rule_score=0.6,
            result_score=0.5,
        )
    ]
    skill_task_scores = [
        TaskScore(
            task_id=task.task_id,
            dimensions=DimensionScores(effectiveness=14, quality=10, efficiency=9, stability=11, trigger_fitness=9, safety=9),
            rule_score=0.8,
            result_score=0.7,
            llm_judge_score=0.9,
        )
    ]
    report = {
        "scores": {
            "baseline": {"total": 54.0},
            "with_skill": {"total": 62.0},
            "net_gain": 8.0,
        },
        "recommendation": {"label": "recommended", "detail": "net gain is positive"},
        "attribution": {"summary": "improved structure"},
    }

    db_path = tmp_path / "evals.db"
    evaluation_id = _persist_evaluation_to_db(
        db_path=str(db_path),
        skill_path="examples/sample-skill",
        profile=profile,
        report=report,
        tasks=[task],
        baseline_run=baseline_run,
        skill_run=skill_run,
        baseline_task_scores=baseline_task_scores,
        skill_task_scores=skill_task_scores,
    )

    conn = sqlite3.connect(str(db_path))
    try:
        eval_count = conn.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]
        task_count = conn.execute("SELECT COUNT(*) FROM evaluation_tasks").fetchone()[0]
    finally:
        conn.close()

    assert evaluation_id > 0
    assert eval_count == 1
    assert task_count == 1
