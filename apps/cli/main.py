"""SkillProbe CLI - A/B evaluate AI agent skills."""

import json
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
from packages.core.attribution.engine import analyze_attribution
from packages.core.reporting.generator import (
    generate_report,
    save_report_json,
    save_report_markdown,
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
@click.option("--model", default="gpt-4o", help="Model to use")
@click.option("--tasks", default=30, help="Number of tasks to generate")
@click.option("--output", "-o", default=None, help="Output JSON path")
def plan(skill_path: str, model: str, tasks: int, output: str | None):
    """Generate an EvalSpec (evaluation plan) for a skill."""
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
@click.option("--model", default="gpt-4o", help="Model for eval spec")
@click.option("--output", "-o", default="outputs/tasks.jsonl", help="Output JSONL path")
def generate_tasks_cmd(skill_path: str, count: int, model: str, output: str):
    """Generate synthetic test tasks for a skill."""
    p = parse_skill_dir(skill_path)
    spec = generate_eval_spec(p, model=model, task_count=count)
    tasks = generate_tasks(p, spec)

    path = save_tasks_jsonl(tasks, output)
    click.echo(f"Generated {len(tasks)} tasks -> {path}")


@cli.command()
@click.argument("skill_path", type=click.Path(exists=True))
@click.option("--model", default="gpt-4o", help="Model to use for evaluation")
@click.option("--tasks", default=30, help="Number of test tasks")
@click.option("--output-dir", "-o", default="outputs/runs", help="Output directory")
def evaluate(skill_path: str, model: str, tasks: int, output_dir: str):
    """Run full A/B evaluation pipeline for a skill."""
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
    baseline = run_baseline(task_list, spec)
    save_run(baseline, output_path)
    click.echo(f"  Completed: {baseline.summary['completed']}/{baseline.summary['total_tasks']}")

    # Step 5: Run with skill
    click.echo("[5/7] Running with skill...")
    with_skill = run_with_skill(task_list, spec)
    save_run(with_skill, output_path)
    click.echo(f"  Completed: {with_skill.summary['completed']}/{with_skill.summary['total_tasks']}")
    click.echo(f"  Skill trigger rate: {with_skill.summary['skill_trigger_rate']:.0%}")

    # Step 6: Score
    click.echo("[6/7] Scoring...")
    base_agg, base_task_scores = score_run(baseline, task_list)
    skill_agg, skill_task_scores = score_run(with_skill, task_list)
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
    click.echo("=" * 60)


if __name__ == "__main__":
    cli()
