from packages.core.attribution.engine import Attribution
from packages.core.reporting.generator import generate_report
from packages.core.scoring.engine import DimensionScores, TaskScore
from packages.core.skill_profile.parser import parse_skill_dir
from packages.generators.spec_generator.generator import generate_eval_spec
from packages.generators.task_generator.generator import generate_tasks
from packages.runners.runner import EvalRun, TaskResult


def _build_report():
    profile = parse_skill_dir("examples/sample-skill")
    spec = generate_eval_spec(profile, model="gpt-4o-mini", task_count=6)
    task = generate_tasks(profile, spec)[0]

    baseline_run = EvalRun(
        run_id="baseline-1",
        eval_spec_id=spec.id,
        run_type="baseline",
        config={"model": "gpt-4o-mini", "temperature": 0.0, "system_prompt": "baseline", "seed": 42},
        started_at="2026-03-19T10:00:00",
        completed_at="2026-03-19T10:00:01",
        task_results=[TaskResult(task_id=task.task_id, output="Summary: baseline\nActions: none", duration_ms=1000, tokens_input=50, tokens_output=40)],
    )
    skill_run = EvalRun(
        run_id="skill-1",
        eval_spec_id=spec.id,
        run_type="with_skill",
        config={"model": "gpt-4o-mini", "temperature": 0.0, "system_prompt": "baseline", "seed": 42, "skill_content_hash": "abc123"},
        started_at="2026-03-19T10:00:02",
        completed_at="2026-03-19T10:00:03",
        task_results=[TaskResult(task_id=task.task_id, output="Summary: improved\nActions: verify", duration_ms=1200, tokens_input=60, tokens_output=55, skill_triggered=True, skill_trigger_count=1)],
    )

    baseline_scores = DimensionScores(effectiveness=18, quality=10, efficiency=12, stability=10, trigger_fitness=8, safety=9)
    skill_scores = DimensionScores(effectiveness=24, quality=15, efficiency=11, stability=10, trigger_fitness=9, safety=9)
    baseline_task_scores = [TaskScore(task_id=task.task_id, dimensions=baseline_scores, rule_score=0.6, result_score=0.5, notes=["missing required tool"])]
    skill_task_scores = [TaskScore(task_id=task.task_id, dimensions=skill_scores, rule_score=0.9, result_score=0.7, notes=["all hard requirements satisfied"])]
    attribution = Attribution(
        gain_factors=["Skill improved structure and completeness."],
        regression_factors=[],
        summary="Skill improved output quality with small extra cost.",
        trigger_analysis={"trigger_rate": 1.0},
    )

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


def test_report_includes_structured_recommendation_and_evidence():
    report = _build_report()

    assert report["recommendation"]["label"] in {
        "recommended",
        "conditionally_recommended",
        "not_recommended",
        "needs_revision",
        "inconclusive",
    }
    assert "score_evidence" in report
    assert "baseline" in report["score_evidence"]
    assert "with_skill" in report["score_evidence"]


def test_report_includes_reproducibility_metadata():
    report = _build_report()

    assert "reproducibility" in report
    assert report["reproducibility"]["baseline"]["model"] == "gpt-4o-mini"
    assert report["reproducibility"]["with_skill"]["skill_content_hash"] == "abc123"
