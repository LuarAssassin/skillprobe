"""Report generator: produce structured Markdown and JSON reports."""

import json
from datetime import datetime
from pathlib import Path

from packages.core.attribution.engine import Attribution
from packages.core.scoring.engine import DimensionScores, TaskScore
from packages.core.validation import validate_eval_report
from packages.runners.runner import EvalRun
from packages.core.skill_profile.models import SkillProfile
from packages.core.eval_spec.models import EvalSpec


def generate_report(
    profile: SkillProfile,
    spec: EvalSpec,
    baseline_run: EvalRun,
    skill_run: EvalRun,
    baseline_scores: DimensionScores,
    skill_scores: DimensionScores,
    baseline_task_scores: list[TaskScore],
    skill_task_scores: list[TaskScore],
    attribution: Attribution,
) -> dict:
    """Generate a complete evaluation report as a dict."""
    net_gain = skill_scores.total - baseline_scores.total

    # Calculate value index
    base_tokens = sum(
        r.tokens_input + r.tokens_output for r in baseline_run.task_results
    )
    skill_tokens = sum(
        r.tokens_input + r.tokens_output for r in skill_run.task_results
    )
    extra_tokens = max(0, skill_tokens - base_tokens)
    value_index = net_gain / (extra_tokens / 1000 + 1) if extra_tokens > 0 else net_gain

    # Determine recommendation
    recommendation = _determine_recommendation(net_gain, attribution, skill_scores)

    # Find exemplars
    best, worst = _find_exemplars(baseline_task_scores, skill_task_scores)

    report = {
        "report_id": f"rpt-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "eval_spec_id": spec.id,
        "skill_profile_id": profile.id,
        "skill_name": profile.name,
        "baseline_run_id": baseline_run.run_id,
        "skill_run_id": skill_run.run_id,
        "generated_at": datetime.now().isoformat(),
        "scores": {
            "baseline": baseline_scores.to_dict(),
            "with_skill": skill_scores.to_dict(),
            "net_gain": round(net_gain, 2),
            "value_index": round(value_index, 2),
        },
        "cost_comparison": {
            "baseline_tokens": base_tokens,
            "skill_tokens": skill_tokens,
            "extra_tokens": extra_tokens,
            "baseline_duration_ms": sum(r.duration_ms for r in baseline_run.task_results),
            "skill_duration_ms": sum(r.duration_ms for r in skill_run.task_results),
        },
        "trigger_analysis": attribution.trigger_analysis,
        "attribution": attribution.to_dict(),
        "score_evidence": {
            "baseline": _build_score_evidence(baseline_task_scores),
            "with_skill": _build_score_evidence(skill_task_scores),
        },
        "reproducibility": {
            "baseline": dict(baseline_run.config),
            "with_skill": dict(skill_run.config),
        },
        "exemplars": {
            "best_improvements": best,
            "worst_regressions": worst,
        },
        "recommendation": recommendation,
        "improvement_suggestions": _generate_suggestions(attribution, skill_scores),
    }

    return report


def _determine_recommendation(
    net_gain: float,
    attribution: Attribution,
    skill_scores: DimensionScores,
) -> dict:
    """Determine recommendation label and detail."""
    has_regressions = len(attribution.regression_factors) > 1 or (
        attribution.regression_factors
        and attribution.regression_factors[0] != "No significant regressions detected"
    )

    if net_gain >= 8 and not has_regressions:
        label = "recommended"
        detail = f"Net gain of {net_gain:.1f} with no significant regressions."
    elif net_gain >= 3:
        if has_regressions:
            label = "conditionally_recommended"
            detail = (
                f"Net gain of {net_gain:.1f}, but some regressions detected. "
                f"Consider enabling only for specific task types."
            )
        else:
            label = "recommended"
            detail = f"Net gain of {net_gain:.1f}."
    elif net_gain >= 0:
        label = "needs_revision"
        detail = f"Marginal gain of {net_gain:.1f}. Skill needs improvement to justify adoption."
    else:
        label = "not_recommended"
        detail = f"Net loss of {net_gain:.1f}. Skill degrades performance."

    return {"label": label, "detail": detail}


def _find_exemplars(
    baseline_scores: list[TaskScore],
    skill_scores: list[TaskScore],
) -> tuple[list[dict], list[dict]]:
    """Find best improvements and worst regressions."""
    base_map = {s.task_id: s for s in baseline_scores}
    deltas = []

    for ss in skill_scores:
        bs = base_map.get(ss.task_id)
        if bs:
            delta = ss.dimensions.total - bs.dimensions.total
            deltas.append({
                "task_id": ss.task_id,
                "baseline_score": round(bs.dimensions.total, 2),
                "skill_score": round(ss.dimensions.total, 2),
                "delta": round(delta, 2),
            })

    deltas.sort(key=lambda x: x["delta"], reverse=True)

    best = deltas[:3] if deltas else []
    worst = deltas[-3:][::-1] if len(deltas) >= 3 else []

    return best, worst


def _generate_suggestions(
    attribution: Attribution,
    skill_scores: DimensionScores,
) -> list[dict]:
    """Generate improvement suggestions based on evaluation results."""
    suggestions = []

    # Low effectiveness
    if skill_scores.effectiveness < 20:
        suggestions.append({
            "target": "skill_content",
            "issue": "Low effectiveness score",
            "suggestion": "Review and strengthen the core instructions. Ensure the skill provides actionable, specific guidance rather than general principles.",
            "priority": "high",
        })

    # Low trigger fitness
    if skill_scores.trigger_fitness < 6:
        suggestions.append({
            "target": "trigger_conditions",
            "issue": "Poor trigger accuracy",
            "suggestion": "Refine trigger conditions to be more specific. Add negative examples to prevent false triggers.",
            "priority": "high",
        })

    # Safety issues
    if skill_scores.safety < 7:
        suggestions.append({
            "target": "safety_guardrails",
            "issue": "Safety concerns detected",
            "suggestion": "Add explicit guardrails against hallucination and over-confidence. Include uncertainty acknowledgment patterns.",
            "priority": "high",
        })

    # Regression factors
    for factor in attribution.regression_factors:
        if "verbosity" in factor.lower():
            suggestions.append({
                "target": "output_format",
                "issue": "Excessive verbosity",
                "suggestion": "Add conciseness guidelines. Specify maximum output length or structure constraints.",
                "priority": "medium",
            })
        if "error" in factor.lower():
            suggestions.append({
                "target": "error_handling",
                "issue": "Skill introduces errors",
                "suggestion": "Review skill instructions for ambiguous or conflicting directives that may confuse the model.",
                "priority": "high",
            })

    return suggestions


def _build_score_evidence(task_scores: list[TaskScore]) -> dict:
    if not task_scores:
        return {
            "task_count": 0,
            "avg_rule_score": 0.0,
            "avg_result_score": 0.0,
            "avg_llm_judge_score": 0.0,
            "notable_notes": [],
        }

    unique_notes: list[str] = []
    for score in task_scores:
        for note in score.notes:
            if note not in unique_notes:
                unique_notes.append(note)

    return {
        "task_count": len(task_scores),
        "avg_rule_score": round(sum(score.rule_score for score in task_scores) / len(task_scores), 2),
        "avg_result_score": round(sum(score.result_score for score in task_scores) / len(task_scores), 2),
        "avg_llm_judge_score": round(sum(score.llm_judge_score for score in task_scores) / len(task_scores), 2),
        "notable_notes": unique_notes[:10],
    }


def save_report_json(report: dict, output_path: str | Path) -> Path:
    """Save report as JSON."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    validate_eval_report(report)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return output_path


def save_report_markdown(report: dict, output_path: str | Path) -> Path:
    """Save report as Markdown."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    validate_eval_report(report)

    md = _render_markdown(report)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)
    return output_path


def _render_markdown(report: dict) -> str:
    """Render report dict as Markdown."""
    scores = report["scores"]
    rec = report["recommendation"]
    attr = report["attribution"]
    cost = report["cost_comparison"]

    lines = [
        f"# SkillProbe Evaluation Report",
        f"",
        f"**Skill**: {report.get('skill_name', 'Unknown')}",
        f"**Generated**: {report['generated_at']}",
        f"**Recommendation**: {rec['label'].upper()}",
        f"",
        f"> {rec['detail']}",
        f"",
        f"## Scores",
        f"",
        f"| Dimension | Baseline | With Skill | Delta |",
        f"|-----------|----------|------------|-------|",
    ]

    base = scores["baseline"]
    skill = scores["with_skill"]
    for dim in ["effectiveness", "quality", "efficiency", "stability", "trigger_fitness", "safety"]:
        b = base.get(dim, 0)
        s = skill.get(dim, 0)
        d = s - b
        sign = "+" if d >= 0 else ""
        lines.append(f"| {dim.replace('_', ' ').title()} | {b:.1f} | {s:.1f} | {sign}{d:.1f} |")

    lines.extend([
        f"| **Total** | **{base['total']:.1f}** | **{skill['total']:.1f}** | **{'+' if scores['net_gain'] >= 0 else ''}{scores['net_gain']:.1f}** |",
        f"",
        f"**Net Gain**: {scores['net_gain']:.1f}",
        f"**Value Index**: {scores['value_index']:.2f}",
        f"",
        f"## Cost Comparison",
        f"",
        f"| Metric | Baseline | With Skill |",
        f"|--------|----------|------------|",
        f"| Tokens | {cost['baseline_tokens']} | {cost['skill_tokens']} |",
        f"| Duration (ms) | {cost['baseline_duration_ms']} | {cost['skill_duration_ms']} |",
        f"",
        f"## Attribution",
        f"",
        f"{attr.get('summary', 'N/A')}",
        f"",
    ])

    if attr.get("gain_factors"):
        lines.append("### Gain Factors")
        for f in attr["gain_factors"]:
            lines.append(f"- {f}")
        lines.append("")

    if attr.get("regression_factors"):
        lines.append("### Regression Factors")
        for f in attr["regression_factors"]:
            lines.append(f"- {f}")
        lines.append("")

    # Exemplars
    exemplars = report.get("exemplars", {})
    if exemplars.get("best_improvements"):
        lines.extend(["## Best Improvements", ""])
        for ex in exemplars["best_improvements"]:
            lines.append(f"- **{ex['task_id']}**: {ex['baseline_score']} -> {ex['skill_score']} (delta: +{ex['delta']})")
        lines.append("")

    if exemplars.get("worst_regressions"):
        lines.extend(["## Worst Regressions", ""])
        for ex in exemplars["worst_regressions"]:
            lines.append(f"- **{ex['task_id']}**: {ex['baseline_score']} -> {ex['skill_score']} (delta: {ex['delta']})")
        lines.append("")

    # Suggestions
    suggestions = report.get("improvement_suggestions", [])
    if suggestions:
        lines.extend(["## Improvement Suggestions", ""])
        for s in suggestions:
            lines.append(f"- [{s['priority'].upper()}] **{s['target']}**: {s['suggestion']}")
        lines.append("")

    evidence = report.get("score_evidence", {})
    if evidence:
        lines.extend(["## Score Evidence", ""])
        for run_name in ("baseline", "with_skill"):
            run_evidence = evidence.get(run_name, {})
            if not run_evidence:
                continue
            lines.append(f"### {run_name.replace('_', ' ').title()}")
            lines.append(f"- Tasks: {run_evidence.get('task_count', 0)}")
            lines.append(f"- Avg rule score: {run_evidence.get('avg_rule_score', 0):.2f}")
            lines.append(f"- Avg result score: {run_evidence.get('avg_result_score', 0):.2f}")
            for note in run_evidence.get("notable_notes", [])[:3]:
                lines.append(f"- {note}")
            lines.append("")

    reproducibility = report.get("reproducibility", {})
    if reproducibility:
        lines.extend(["## Reproducibility", ""])
        for run_name in ("baseline", "with_skill"):
            config = reproducibility.get(run_name, {})
            if not config:
                continue
            lines.append(f"### {run_name.replace('_', ' ').title()}")
            for key, value in config.items():
                lines.append(f"- {key}: {value}")
            lines.append("")

    return "\n".join(lines)
