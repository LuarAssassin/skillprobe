"""Scoring engine: rule-based, LLM judge, and aggregate scoring."""

from dataclasses import dataclass, field
import statistics

from packages.core.eval_spec.models import MetricWeights
from packages.generators.task_generator.models import Task
from packages.runners.runner import EvalRun, TaskResult


@dataclass
class DimensionScores:
    effectiveness: float = 0.0
    quality: float = 0.0
    efficiency: float = 0.0
    stability: float = 0.0
    trigger_fitness: float = 0.0
    safety: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.effectiveness + self.quality + self.efficiency
            + self.stability + self.trigger_fitness + self.safety
        )

    def to_dict(self) -> dict:
        return {
            "total": round(self.total, 2),
            "effectiveness": round(self.effectiveness, 2),
            "quality": round(self.quality, 2),
            "efficiency": round(self.efficiency, 2),
            "stability": round(self.stability, 2),
            "trigger_fitness": round(self.trigger_fitness, 2),
            "safety": round(self.safety, 2),
        }


@dataclass
class TaskScore:
    task_id: str
    dimensions: DimensionScores = field(default_factory=DimensionScores)
    rule_score: float = 0.0
    result_score: float = 0.0
    llm_judge_score: float = 0.0
    notes: list[str] = field(default_factory=list)
    rule_checks: dict[str, bool] = field(default_factory=dict)
    safety_issues: list[str] = field(default_factory=list)


def score_run(
    run: EvalRun,
    tasks: list[Task],
    weights: MetricWeights | None = None,
    llm_judge_map: dict[str, float] | None = None,
    stability_map: dict[str, float] | None = None,
) -> tuple[DimensionScores, list[TaskScore]]:
    """Score an entire run, returning aggregate and per-task scores."""
    if weights is None:
        weights = MetricWeights()

    task_map = {t.task_id: t for t in tasks}
    task_scores: list[TaskScore] = []

    for result in run.task_results:
        task = task_map.get(result.task_id)
        ts = _score_single_task(
            result,
            task,
            weights,
            llm_judge_score=llm_judge_map.get(result.task_id) if llm_judge_map else None,
            stability_score=stability_map.get(result.task_id) if stability_map else None,
        )
        task_scores.append(ts)

    # Aggregate
    if not task_scores:
        return DimensionScores(), task_scores

    n = len(task_scores)
    agg = DimensionScores(
        effectiveness=sum(ts.dimensions.effectiveness for ts in task_scores) / n,
        quality=sum(ts.dimensions.quality for ts in task_scores) / n,
        efficiency=sum(ts.dimensions.efficiency for ts in task_scores) / n,
        stability=sum(ts.dimensions.stability for ts in task_scores) / n,
        trigger_fitness=sum(ts.dimensions.trigger_fitness for ts in task_scores) / n,
        safety=sum(ts.dimensions.safety for ts in task_scores) / n,
    )

    return agg, task_scores


def _score_single_task(
    result: TaskResult,
    task: Task | None,
    weights: MetricWeights,
    llm_judge_score: float | None = None,
    stability_score: float | None = None,
) -> TaskScore:
    """Score a single task result."""
    ts = TaskScore(task_id=result.task_id)

    # --- Rule-based scoring ---
    rule, rule_notes, rule_checks = _rule_score(result, task)
    ts.rule_score = rule
    ts.notes.extend(rule_notes)
    ts.rule_checks = rule_checks

    # --- Result-based scoring ---
    res, result_notes = _result_score(result, task)
    ts.result_score = res
    ts.notes.extend(result_notes)

    has_llm_judge = llm_judge_score is not None
    if has_llm_judge:
        ts.llm_judge_score = max(0.0, min(1.0, llm_judge_score or 0.0))

    # --- Map to dimensions ---
    # Effectiveness (30 max): based on completion and correctness
    if result.error:
        ts.dimensions.effectiveness = 0.0
    else:
        if has_llm_judge:
            effectiveness_core = rule * 0.3 + res * 0.4 + ts.llm_judge_score * 0.3
        else:
            effectiveness_core = rule * 0.4 + res * 0.6
        ts.dimensions.effectiveness = effectiveness_core * 30.0

    # Quality (20 max): based on output length, structure
    quality_core = _quality_heuristic(result)
    if has_llm_judge:
        quality_core = quality_core * 0.6 + ts.llm_judge_score * 0.4
    ts.dimensions.quality = quality_core * 20.0

    # Efficiency (15 max): based on duration and tokens
    ts.dimensions.efficiency = _efficiency_score(result) * 15.0

    # Stability (15 max): default neutral unless repeated-run variance is provided
    if stability_score is None:
        ts.dimensions.stability = 10.0
    else:
        ts.dimensions.stability = max(0.0, min(15.0, stability_score))

    # Trigger fitness (10 max): based on skill trigger accuracy
    ts.dimensions.trigger_fitness = _trigger_fitness(result) * 10.0

    # Safety (10 max): based on absence of issues
    safety_score, safety_notes = _safety_score(result, task)
    ts.dimensions.safety = safety_score * 10.0
    ts.safety_issues = safety_notes
    ts.notes.extend(safety_notes)

    return ts


def build_stability_map(
    runs: list[EvalRun],
    tasks: list[Task],
) -> dict[str, float]:
    """Build per-task stability scores from repeated runs (0-15 points).

    Stability is derived from run-to-run variance of each task's core
    performance proxy: 0.5 * rule_score + 0.5 * result_score.
    """
    if len(runs) < 2:
        return {}

    per_task_values: dict[str, list[float]] = {}
    for run in runs:
        _, task_scores = score_run(run, tasks)
        for task_score in task_scores:
            core = task_score.rule_score * 0.5 + task_score.result_score * 0.5
            per_task_values.setdefault(task_score.task_id, []).append(core)

    stability: dict[str, float] = {}
    for task in tasks:
        values = per_task_values.get(task.task_id, [])
        if len(values) < 2:
            stability[task.task_id] = 10.0
            continue

        stddev = statistics.pstdev(values)
        normalized = max(0.0, 1.0 - min(stddev / 0.25, 1.0))
        stability[task.task_id] = round(normalized * 15.0, 2)

    return stability


def _rule_score(result: TaskResult, task: Task | None) -> tuple[float, list[str], dict[str, bool]]:
    """Rule-based scoring (0-1). Checks hard requirements."""
    if result.error:
        return 0.0, [f"Task failed before scoring: {result.error}"], {"execution_success": False}

    notes: list[str] = []
    checks: dict[str, bool] = {}
    output = result.output.strip()

    checks["has_output"] = bool(output)
    if not output:
        notes.append("Missing required output.")
        return 0.0, notes, checks

    output_lower = output.lower()
    tool_names = {
        str(tool_call.get("tool", "")).strip().lower()
        for tool_call in result.tool_calls
        if isinstance(tool_call, dict)
    }

    if task:
        for field in task.scoring_hints.required_fields:
            check_name = f"required_field:{field}"
            matched = field.lower() in output_lower
            checks[check_name] = matched
            if not matched:
                notes.append(f"Missing required field: {field}")

        for tool in task.scoring_hints.required_tools:
            check_name = f"required_tool:{tool}"
            matched = tool.lower() in tool_names
            checks[check_name] = matched
            if not matched:
                notes.append(f"Missing required tool: {tool}")

        for point in task.scoring_hints.key_points:
            check_name = f"key_point:{point}"
            matched = point.lower() in output_lower
            checks[check_name] = matched
            if not matched:
                notes.append(f"Missing key point: {point}")

    if len(output.split()) < 10:
        checks["minimum_word_count"] = False
        notes.append("Output is shorter than the minimum useful length.")
    else:
        checks["minimum_word_count"] = True

    passed = sum(1 for value in checks.values() if value)
    total = len(checks)
    score = passed / total if total else 1.0
    return min(1.0, score), notes, checks


def _result_score(result: TaskResult, task: Task | None) -> tuple[float, list[str]]:
    """Result-based scoring (0-1). Checks objective correctness."""
    if result.error or not result.output.strip():
        return 0.0, ["No usable output for result-based scoring."]

    score = 0.5  # base for having output
    notes: list[str] = []

    # If reference answer exists, do simple overlap check
    if task and task.reference_answer:
        ref_words = set(task.reference_answer.lower().split())
        out_words = set(result.output.lower().split())
        if ref_words:
            overlap = len(ref_words & out_words) / len(ref_words)
            score = 0.3 + 0.7 * overlap
            notes.append(f"Reference overlap: {overlap:.2f}")

    return min(1.0, score), notes


def _quality_heuristic(result: TaskResult) -> float:
    """Heuristic quality score (0-1)."""
    if not result.output.strip():
        return 0.0

    score = 0.4
    output = result.output

    # Structure indicators
    if any(marker in output for marker in ["1.", "- ", "* ", "##"]):
        score += 0.2

    # Reasonable length (not too short, not excessively long)
    words = len(output.split())
    if 50 <= words <= 2000:
        score += 0.2
    elif words > 2000:
        score += 0.1  # slightly penalize verbosity

    # Contains reasoning indicators
    reasoning_markers = ["because", "therefore", "however", "specifically", "for example"]
    if any(m in output.lower() for m in reasoning_markers):
        score += 0.2

    return min(1.0, score)


def _efficiency_score(result: TaskResult) -> float:
    """Efficiency score (0-1). Lower time/tokens = higher score."""
    if result.error:
        return 0.0

    score = 0.5

    # Duration scoring (under 10s is good, over 60s is bad)
    if result.duration_ms < 10000:
        score += 0.3
    elif result.duration_ms < 30000:
        score += 0.15

    # Token scoring (under 2000 total is efficient)
    total_tokens = result.tokens_input + result.tokens_output
    if total_tokens < 2000:
        score += 0.2
    elif total_tokens < 5000:
        score += 0.1

    return min(1.0, score)


def _trigger_fitness(result: TaskResult) -> float:
    """Trigger fitness score (0-1)."""
    # For baseline runs, this is always 1.0 (no skill to trigger)
    if not result.skill_triggered and result.skill_trigger_count == 0:
        return 0.8  # neutral

    # For skill runs, triggered = good (assuming task is relevant)
    if result.skill_triggered:
        return 0.9

    return 0.5  # skill available but not triggered


def _safety_score(result: TaskResult, task: Task | None) -> tuple[float, list[str]]:
    """Safety score (0-1). Checks for red flags."""
    if result.error:
        return 0.3, ["Execution error reduced safety confidence."]

    if not result.output.strip():
        return 0.5, ["Empty output reduced safety confidence."]

    score = 1.0
    output_lower = result.output.lower()
    notes: list[str] = []

    # Check for hallucination indicators
    hallucination_markers = [
        "i'm not sure but",
        "i think maybe",
        "as an ai language model",
    ]
    for marker in hallucination_markers:
        if marker in output_lower:
            score -= 0.15
            notes.append(f"Hallucination marker detected: {marker}")

    # Check for excessive hedging
    hedge_count = sum(1 for w in ["might", "perhaps", "possibly", "maybe"]
                      if w in output_lower)
    if hedge_count > 5:
        score -= 0.1
        notes.append("Excessive hedging detected.")

    if task:
        for anti_pattern in task.scoring_hints.anti_patterns:
            if anti_pattern.lower() in output_lower:
                score -= 0.2
                notes.append(f"Anti-pattern detected: {anti_pattern}")

    return max(0.0, score), notes
