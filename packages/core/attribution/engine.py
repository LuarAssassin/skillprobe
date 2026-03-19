"""Attribution engine: analyze why scores differ between baseline and skill runs."""

from dataclasses import dataclass, field

from packages.runners.runner import EvalRun, TaskResult
from packages.core.scoring.engine import TaskScore


@dataclass
class Attribution:
    gain_factors: list[str] = field(default_factory=list)
    regression_factors: list[str] = field(default_factory=list)
    suspicious_instructions: list[str] = field(default_factory=list)
    summary: str = ""
    trigger_analysis: dict = field(default_factory=dict)
    per_task: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "gain_factors": self.gain_factors,
            "regression_factors": self.regression_factors,
            "suspicious_instructions": self.suspicious_instructions,
            "summary": self.summary,
            "trigger_analysis": self.trigger_analysis,
            "per_task": self.per_task,
        }


def analyze_attribution(
    baseline_run: EvalRun,
    skill_run: EvalRun,
    baseline_scores: list[TaskScore],
    skill_scores: list[TaskScore],
) -> Attribution:
    """Compare baseline and skill runs to attribute differences."""
    attr = Attribution()

    # Build lookup maps
    base_results = {r.task_id: r for r in baseline_run.task_results}
    skill_results = {r.task_id: r for r in skill_run.task_results}
    base_score_map = {s.task_id: s for s in baseline_scores}
    skill_score_map = {s.task_id: s for s in skill_scores}

    gains = []
    regressions = []
    neutral = []

    for task_id in base_results:
        bs = base_score_map.get(task_id)
        ss = skill_score_map.get(task_id)
        if not bs or not ss:
            continue

        delta = ss.dimensions.total - bs.dimensions.total
        br = base_results[task_id]
        sr = skill_results.get(task_id)

        entry = {
            "task_id": task_id,
            "baseline_score": round(bs.dimensions.total, 2),
            "skill_score": round(ss.dimensions.total, 2),
            "delta": round(delta, 2),
            "skill_triggered": sr.skill_triggered if sr else False,
        }

        if delta > 2:
            gains.append(entry)
        elif delta < -2:
            regressions.append(entry)
        else:
            neutral.append(entry)

        attr.per_task.append(entry)

    # Trigger analysis
    total_skill = len(skill_results)
    triggered = sum(1 for r in skill_results.values() if r.skill_triggered)
    attr.trigger_analysis = {
        "total_tasks": total_skill,
        "triggered": triggered,
        "trigger_rate": triggered / total_skill if total_skill > 0 else 0,
        "triggered_with_gain": sum(
            1 for g in gains if g["skill_triggered"]
        ),
        "triggered_with_regression": sum(
            1 for r in regressions if r["skill_triggered"]
        ),
    }

    # Analyze gain factors
    attr.gain_factors = _analyze_gains(gains, base_results, skill_results)
    attr.regression_factors = _analyze_regressions(regressions, base_results, skill_results)

    # Build summary
    attr.summary = _build_summary(gains, regressions, neutral, attr.trigger_analysis)

    return attr


def _analyze_gains(
    gains: list[dict],
    base_results: dict[str, TaskResult],
    skill_results: dict[str, TaskResult],
) -> list[str]:
    """Analyze what caused improvements."""
    factors = []

    if not gains:
        return ["No significant gains detected"]

    # Check if gains correlate with skill triggering
    triggered_gains = [g for g in gains if g["skill_triggered"]]
    if len(triggered_gains) > len(gains) * 0.7:
        factors.append("Gains strongly correlate with skill activation")

    # Check output quality differences
    longer_outputs = 0
    more_structured = 0
    for g in gains:
        tid = g["task_id"]
        br = base_results.get(tid)
        sr = skill_results.get(tid)
        if br and sr:
            if len(sr.output) > len(br.output) * 1.2:
                longer_outputs += 1
            if any(m in sr.output for m in ["1.", "- ", "##"]) and not any(
                m in br.output for m in ["1.", "- ", "##"]
            ):
                more_structured += 1

    if longer_outputs > len(gains) * 0.5:
        factors.append("Skill produces more detailed outputs")
    if more_structured > len(gains) * 0.3:
        factors.append("Skill improves output structure and organization")

    if not factors:
        factors.append(f"{len(gains)} tasks showed improvement (further LLM analysis recommended)")

    return factors


def _analyze_regressions(
    regressions: list[dict],
    base_results: dict[str, TaskResult],
    skill_results: dict[str, TaskResult],
) -> list[str]:
    """Analyze what caused regressions."""
    factors = []

    if not regressions:
        return ["No significant regressions detected"]

    # Check for verbosity increase
    verbose_count = 0
    error_count = 0
    for r in regressions:
        tid = r["task_id"]
        br = base_results.get(tid)
        sr = skill_results.get(tid)
        if br and sr:
            if len(sr.output) > len(br.output) * 2:
                verbose_count += 1
            if sr.error and not br.error:
                error_count += 1

    if verbose_count > len(regressions) * 0.3:
        factors.append("Skill causes excessive verbosity in some tasks")
    if error_count > 0:
        factors.append(f"Skill introduced errors in {error_count} tasks")

    # Check if regressions happen on specific task types
    regressed_types = set()
    for r in regressions:
        # task_id format: "category-hash"
        parts = r["task_id"].rsplit("-", 1)
        if len(parts) == 2:
            regressed_types.add(parts[0])

    if regressed_types:
        factors.append(f"Regressions concentrated in: {', '.join(regressed_types)}")

    if not factors:
        factors.append(f"{len(regressions)} tasks showed regression (further analysis needed)")

    return factors


def _build_summary(
    gains: list[dict],
    regressions: list[dict],
    neutral: list[dict],
    trigger_analysis: dict,
) -> str:
    """Build a human-readable attribution summary."""
    total = len(gains) + len(regressions) + len(neutral)
    if total == 0:
        return "No tasks to analyze."

    parts = [
        f"Analyzed {total} tasks.",
        f"{len(gains)} improved, {len(regressions)} regressed, {len(neutral)} neutral.",
    ]

    rate = trigger_analysis.get("trigger_rate", 0)
    parts.append(f"Skill trigger rate: {rate:.0%}.")

    if gains and trigger_analysis.get("triggered_with_gain", 0) > 0:
        parts.append(
            f"{trigger_analysis['triggered_with_gain']}/{len(gains)} gains occurred when skill was active."
        )

    return " ".join(parts)
