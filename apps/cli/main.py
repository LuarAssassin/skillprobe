"""SkillProbe CLI - A/B evaluate AI agent skills."""

import json
import os
import sys
from pathlib import Path

import click

# Add project root to path for package imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from packages.core.skill_profile.parser import parse_skill_dir
from packages.core.eval_spec.models import EvalSpec
from packages.generators.spec_generator.generator import generate_eval_spec
from packages.generators.task_generator.generator import generate_tasks, save_tasks_jsonl
from packages.runners.runner import run_baseline, run_with_skill, save_run
from packages.core.scoring.engine import score_run
from packages.core.scoring.engine import build_stability_map
from packages.core.scoring.judge import build_pairwise_llm_judge_maps
from packages.core.attribution.engine import analyze_attribution
from packages.core.reporting.generator import (
    generate_report,
    save_report_json,
    save_report_markdown,
)

_MODEL_ENV_VARS = ("SKILLPROBE_MODEL", "MODEL")


def _resolve_model(model: str | None) -> str:
    if model:
        return model

    for env_name in _MODEL_ENV_VARS:
        value = os.getenv(env_name, "").strip()
        if value:
            return value

    raise click.UsageError(
        "No model configured. Pass --model or set SKILLPROBE_MODEL/MODEL."
    )


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """SkillProbe: A/B evaluate AI agent skills."""
    pass


@cli.command()
@click.argument("skill_path", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output JSON path")
def profile(skill_path: str, output: str | None):
    """Generate a SkillProfile from a skill directory."""
    click.echo(f"Profiling skill at: {skill_path}")
    p = parse_skill_dir(skill_path)

    result = json.dumps(p.to_dict(), indent=2, ensure_ascii=False)

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(result, encoding="utf-8")
        click.echo(f"Profile saved to: {output}")
    else:
        click.echo(result)


@cli.command()
@click.argument("skill_path", type=click.Path(exists=True))
@click.option("--model", default=None, help="Model to use; falls back to SKILLPROBE_MODEL or MODEL")
@click.option("--tasks", default=30, help="Number of tasks to generate")
@click.option("--output", "-o", default=None, help="Output JSON path")
def plan(skill_path: str, model: str | None, tasks: int, output: str | None):
    """Generate an EvalSpec (evaluation plan) for a skill."""
    model = _resolve_model(model)
    p = parse_skill_dir(skill_path)
    spec = generate_eval_spec(p, model=model, task_count=tasks)

    result = json.dumps(spec.to_dict(), indent=2, ensure_ascii=False)

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(result, encoding="utf-8")
        click.echo(f"EvalSpec saved to: {output}")
    else:
        click.echo(result)


@cli.command("generate-tasks")
@click.argument("skill_path", type=click.Path(exists=True))
@click.option("--count", default=30, help="Number of tasks")
@click.option("--model", default=None, help="Model for eval spec; falls back to SKILLPROBE_MODEL or MODEL")
@click.option("--output", "-o", default="outputs/tasks.jsonl", help="Output JSONL path")
def generate_tasks_cmd(skill_path: str, count: int, model: str | None, output: str):
    """Generate synthetic test tasks for a skill."""
    model = _resolve_model(model)
    p = parse_skill_dir(skill_path)
    spec = generate_eval_spec(p, model=model, task_count=count)
    tasks = generate_tasks(p, spec)

    path = save_tasks_jsonl(tasks, output)
    click.echo(f"Generated {len(tasks)} tasks -> {path}")


@cli.command()
@click.argument("skill_path", type=click.Path(exists=True))
@click.option("--model", default=None, help="Model to use for evaluation; falls back to SKILLPROBE_MODEL or MODEL")
@click.option("--tasks", default=30, help="Number of test tasks")
@click.option("--repeats", default=2, type=int, show_default=True, help="Repeated runs per arm for stability scoring")
@click.option("--llm-judge/--no-llm-judge", default=False, help="Enable pairwise LLM judge scoring")
@click.option("--judge-model", default=None, help="Judge model; defaults to --model")
@click.option("--db", default="outputs/evaluations.db", show_default=True, help="SQLite path for persisting evaluation results")
@click.option("--output-dir", "-o", default="outputs/runs", help="Output directory")
def evaluate(
    skill_path: str,
    model: str | None,
    tasks: int,
    repeats: int,
    llm_judge: bool,
    judge_model: str | None,
    db: str,
    output_dir: str,
):
    """Run full A/B evaluation pipeline for a skill."""
    model = _resolve_model(model)
    if repeats < 1:
        raise click.UsageError("--repeats must be >= 1")
    output_path = Path(output_dir)

    # Step 1: Profile
    click.echo("[1/7] Profiling skill...")
    p = parse_skill_dir(skill_path)
    click.echo(f"  Skill: {p.name} ({p.file_count} files, ~{p.total_tokens_estimate} tokens)")

    # Step 2: Generate eval spec
    click.echo("[2/7] Generating evaluation plan...")
    spec = generate_eval_spec(p, model=model, task_count=tasks)
    click.echo(f"  Categories: {', '.join(c.name for c in spec.task_categories)}")

    # Step 3: Generate tasks
    click.echo("[3/7] Generating test tasks...")
    task_list = generate_tasks(p, spec)
    save_tasks_jsonl(task_list, output_path / "tasks.jsonl")
    click.echo(f"  Generated {len(task_list)} tasks")

    # Step 4: Run baseline
    click.echo("[4/7] Running baseline (no skill)...")
    baseline_runs = []
    for repeat_index in range(repeats):
        seed_override = _seed_for_repeat(spec.baseline_config.seed, repeat_index)
        run = run_baseline(task_list, spec, seed_override=seed_override)
        save_run(run, output_path)
        baseline_runs.append(run)
        click.echo(
            f"  Repeat {repeat_index + 1}/{repeats}: "
            f"{run.summary['completed']}/{run.summary['total_tasks']} completed"
        )
    baseline = baseline_runs[0]

    # Step 5: Run with skill
    click.echo("[5/7] Running with skill...")
    skill_runs = []
    for repeat_index in range(repeats):
        seed_override = _seed_for_repeat(spec.skill_config.seed, repeat_index)
        run = run_with_skill(task_list, spec, seed_override=seed_override)
        save_run(run, output_path)
        skill_runs.append(run)
        click.echo(
            f"  Repeat {repeat_index + 1}/{repeats}: "
            f"{run.summary['completed']}/{run.summary['total_tasks']} completed, "
            f"trigger rate {run.summary['skill_trigger_rate']:.0%}"
        )
    with_skill = skill_runs[0]

    # Step 6: Score
    click.echo("[6/7] Scoring...")
    baseline_stability_map = build_stability_map(baseline_runs, task_list)
    skill_stability_map = build_stability_map(skill_runs, task_list)

    baseline_llm_map: dict[str, float] | None = None
    skill_llm_map: dict[str, float] | None = None
    if llm_judge:
        selected_judge_model = judge_model or model
        click.echo(f"  Running LLM judge with model: {selected_judge_model}")
        baseline_llm_map, skill_llm_map, judge_warnings = build_pairwise_llm_judge_maps(
            task_list,
            baseline,
            with_skill,
            model=selected_judge_model,
            timeout_seconds=max(
                spec.baseline_config.timeout_seconds,
                spec.skill_config.timeout_seconds,
            ),
        )
        if judge_warnings:
            click.echo(f"  LLM judge warnings: {len(judge_warnings)} task(s) fallback to non-judge scoring")

    base_agg, base_task_scores = score_run(
        baseline,
        task_list,
        llm_judge_map=baseline_llm_map,
        stability_map=baseline_stability_map,
    )
    skill_agg, skill_task_scores = score_run(
        with_skill,
        task_list,
        llm_judge_map=skill_llm_map,
        stability_map=skill_stability_map,
    )
    click.echo(f"  Baseline: {base_agg.total:.1f} / With skill: {skill_agg.total:.1f}")

    # Step 7: Attribution & Report
    click.echo("[7/7] Analyzing attribution and generating report...")
    attr = analyze_attribution(baseline, with_skill, base_task_scores, skill_task_scores)
    report = generate_report(
        p, spec, baseline, with_skill,
        base_agg, skill_agg,
        base_task_scores, skill_task_scores,
        attr,
    )

    # Save reports
    save_report_json(report, output_path / "report.json")
    md_path = save_report_markdown(report, output_path / "report.md")
    db_evaluation_id = _persist_evaluation_to_db(
        db_path=db,
        skill_path=skill_path,
        profile=p,
        report=report,
        tasks=task_list,
        baseline_run=baseline,
        skill_run=with_skill,
        baseline_task_scores=base_task_scores,
        skill_task_scores=skill_task_scores,
    )

    # Print summary
    net = report["scores"]["net_gain"]
    rec = report["recommendation"]
    click.echo("")
    click.echo("=" * 60)
    click.echo(f"  Skill: {p.name}")
    click.echo(f"  Baseline: {base_agg.total:.1f} | With Skill: {skill_agg.total:.1f} | Net Gain: {'+' if net >= 0 else ''}{net:.1f}")
    click.echo(f"  Recommendation: {rec['label'].upper()}")
    click.echo(f"  {rec['detail']}")
    click.echo(f"  Report: {md_path}")
    click.echo(f"  SQLite: {db} (evaluation_id={db_evaluation_id})")
    click.echo("=" * 60)


def _seed_for_repeat(base_seed: int | None, repeat_index: int) -> int | None:
    if base_seed is None:
        return None
    return base_seed + repeat_index


def _persist_evaluation_to_db(
    *,
    db_path: str,
    skill_path: str,
    profile,
    report: dict,
    tasks: list,
    baseline_run,
    skill_run,
    baseline_task_scores: list,
    skill_task_scores: list,
) -> int:
    from db.store import init_db, insert_skill, upsert_evaluation_result

    conn = init_db(db_path)
    try:
        insert_skill(
            conn,
            id=profile.id,
            name=profile.name,
            slug=profile.name.lower().replace(" ", "-")[:128],
            repo_source="local",
            repo_path=str(Path(skill_path).resolve()),
            description=profile.description,
            profile_json=json.dumps(profile.to_dict(), ensure_ascii=False),
            is_directly_testable=True,
        )

        baseline_results = {result.task_id: result for result in baseline_run.task_results}
        skill_results = {result.task_id: result for result in skill_run.task_results}
        baseline_scores_map = {score.task_id: score for score in baseline_task_scores}
        skill_scores_map = {score.task_id: score for score in skill_task_scores}

        task_rows = []
        for task in tasks:
            baseline_result = baseline_results.get(task.task_id)
            skill_result = skill_results.get(task.task_id)
            baseline_score = baseline_scores_map.get(task.task_id)
            skill_score = skill_scores_map.get(task.task_id)
            task_rows.append(
                {
                    "prompt": task.prompt,
                    "baseline_output": baseline_result.output if baseline_result else "",
                    "with_skill_output": skill_result.output if skill_result else "",
                    "baseline_scores": {
                        "dimensions": baseline_score.dimensions.to_dict() if baseline_score else {},
                        "rule_score": baseline_score.rule_score if baseline_score else 0.0,
                        "result_score": baseline_score.result_score if baseline_score else 0.0,
                        "llm_judge_score": baseline_score.llm_judge_score if baseline_score else 0.0,
                        "notes": baseline_score.notes if baseline_score else [],
                    },
                    "with_skill_scores": {
                        "dimensions": skill_score.dimensions.to_dict() if skill_score else {},
                        "rule_score": skill_score.rule_score if skill_score else 0.0,
                        "result_score": skill_score.result_score if skill_score else 0.0,
                        "llm_judge_score": skill_score.llm_judge_score if skill_score else 0.0,
                        "notes": skill_score.notes if skill_score else [],
                    },
                }
            )

        failed_tasks = baseline_run.summary.get("failed", 0) + skill_run.summary.get("failed", 0)
        status = "completed" if failed_tasks == 0 else "failed"
        error_message = (
            None
            if failed_tasks == 0
            else f"{failed_tasks} task executions failed across baseline and with-skill runs"
        )

        return upsert_evaluation_result(
            conn,
            skill_id=profile.id,
            status=status,
            baseline_total=report.get("scores", {}).get("baseline", {}).get("total"),
            with_skill_total=report.get("scores", {}).get("with_skill", {}).get("total"),
            net_gain=report.get("scores", {}).get("net_gain"),
            recommendation_label=report.get("recommendation", {}).get("label"),
            recommendation_detail=report.get("recommendation", {}).get("detail"),
            report_summary=report.get("attribution", {}).get("summary"),
            details_json=json.dumps(report, ensure_ascii=False),
            error_message=error_message,
            tasks=task_rows,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    cli()
