from packages.core.eval_spec.models import MetricWeights
from packages.core.scoring.engine import score_run
from packages.generators.task_generator.models import ScoringHints, Task
from packages.runners.runner import EvalRun, TaskResult


def _task() -> Task:
    return Task(
        task_id="qa-001",
        task_type="qa",
        prompt="Produce a short answer with explicit Summary and Actions sections.",
        difficulty="medium",
        scoring_hints=ScoringHints(
            key_points=["summary", "actions"],
            required_tools=["web_search"],
            required_fields=["Summary", "Actions"],
            anti_patterns=["as an ai language model"],
        ),
        category="qa",
    )


def _run(result: TaskResult) -> EvalRun:
    return EvalRun(
        run_id="run-001",
        eval_spec_id="spec-001",
        run_type="with_skill",
        started_at="2026-03-19T10:00:00",
        completed_at="2026-03-19T10:00:01",
        task_results=[result],
    )


def test_rule_score_penalizes_missing_required_fields_and_tools():
    task = _task()
    result = TaskResult(
        task_id=task.task_id,
        output="Summary: this answer forgot one section.",
        tool_calls=[],
        duration_ms=400,
        tokens_input=30,
        tokens_output=20,
    )

    _, task_scores = score_run(_run(result), [task], MetricWeights())

    assert task_scores[0].rule_score < 0.8
    assert any("required field" in note.lower() for note in task_scores[0].notes)
    assert any("required tool" in note.lower() for note in task_scores[0].notes)


def test_rule_score_rewards_complete_outputs():
    task = _task()
    missing = TaskResult(
        task_id=task.task_id,
        output="Summary: present only.",
        tool_calls=[],
        duration_ms=500,
        tokens_input=30,
        tokens_output=20,
    )
    complete = TaskResult(
        task_id=task.task_id,
        output="Summary: covered.\nActions: verify and ship.",
        tool_calls=[{"tool": "web_search", "input": {"q": "skillprobe"}, "output": {"ok": True}}],
        duration_ms=500,
        tokens_input=30,
        tokens_output=20,
    )

    _, missing_scores = score_run(_run(missing), [task], MetricWeights())
    _, complete_scores = score_run(_run(complete), [task], MetricWeights())

    assert complete_scores[0].rule_score > missing_scores[0].rule_score
    assert complete_scores[0].dimensions.safety >= missing_scores[0].dimensions.safety


def test_safety_notes_flag_anti_patterns():
    task = _task()
    result = TaskResult(
        task_id=task.task_id,
        output="As an AI language model, I would maybe provide a Summary and Actions section.",
        tool_calls=[{"tool": "web_search", "input": {"q": "skillprobe"}, "output": {"ok": True}}],
        duration_ms=400,
        tokens_input=30,
        tokens_output=20,
    )

    _, task_scores = score_run(_run(result), [task], MetricWeights())

    assert task_scores[0].dimensions.safety < 10.0
    assert any("anti-pattern" in note.lower() for note in task_scores[0].notes)
