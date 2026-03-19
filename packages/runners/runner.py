"""A/B experiment runners for baseline and with-skill evaluation."""

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from litellm import completion

from packages.core.eval_spec.models import EvalSpec, RunConfig
from packages.core.validation import validate_eval_run
from packages.generators.task_generator.models import Task


@dataclass
class TaskResult:
    task_id: str
    output: str = ""
    reasoning_summary: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    duration_ms: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    error: str = ""
    skill_triggered: bool = False
    skill_trigger_count: int = 0
    skill_trigger_points: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "output": self.output,
            "reasoning_summary": self.reasoning_summary,
            "tool_calls": self.tool_calls,
            "artifacts": self.artifacts,
            "duration_ms": self.duration_ms,
            "tokens_used": {"input": self.tokens_input, "output": self.tokens_output},
            "error": self.error,
            "skill_triggered": self.skill_triggered,
            "skill_trigger_count": self.skill_trigger_count,
            "skill_trigger_points": self.skill_trigger_points,
        }


@dataclass
class EvalRun:
    run_id: str
    eval_spec_id: str
    run_type: str  # "baseline" or "with_skill"
    config: dict = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""
    task_results: list[TaskResult] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        completed = sum(1 for r in self.task_results if not r.error)
        failed = sum(1 for r in self.task_results if r.error)
        total_dur = sum(r.duration_ms for r in self.task_results)
        total_tok = sum(r.tokens_input + r.tokens_output for r in self.task_results)
        triggered = sum(1 for r in self.task_results if r.skill_triggered)
        total = len(self.task_results)
        return {
            "total_tasks": total,
            "completed": completed,
            "failed": failed,
            "total_duration_ms": total_dur,
            "total_tokens": total_tok,
            "skill_trigger_rate": triggered / total if total > 0 else 0,
        }

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "eval_spec_id": self.eval_spec_id,
            "run_type": self.run_type,
            "config": self.config,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "task_results": [r.to_dict() for r in self.task_results],
            "summary": self.summary,
        }


def run_baseline(
    tasks: list[Task],
    spec: EvalSpec,
    seed_override: int | None = None,
) -> EvalRun:
    """Run tasks without skill (baseline)."""
    config = spec.baseline_config
    if seed_override is not None:
        config = replace(config, seed=seed_override)
    return _run_tasks(tasks, config, spec, run_type="baseline")


def run_with_skill(
    tasks: list[Task],
    spec: EvalSpec,
    seed_override: int | None = None,
) -> EvalRun:
    """Run tasks with skill enabled."""
    config = spec.skill_config
    if seed_override is not None:
        config = replace(config, seed=seed_override)
    return _run_tasks(tasks, config, spec, run_type="with_skill")


def _run_tasks(
    tasks: list[Task],
    config: RunConfig,
    spec: EvalSpec,
    run_type: str,
) -> EvalRun:
    """Execute tasks against an LLM with the given config."""
    run = EvalRun(
        run_id=str(uuid.uuid4())[:8],
        eval_spec_id=spec.id,
        run_type=run_type,
        config=_build_run_config(config),
        started_at=datetime.now().isoformat(),
    )

    # Build system prompt
    system_prompt = config.system_prompt
    if config.skill_content:
        system_prompt += f"\n\n# Skill Instructions\n\n{config.skill_content}"

    for task in tasks:
        result = _execute_single_task(task, config, system_prompt)
        run.task_results.append(result)

    run.completed_at = datetime.now().isoformat()
    return run


def _execute_single_task(
    task: Task,
    config: RunConfig,
    system_prompt: str,
) -> TaskResult:
    """Execute a single task and capture results."""
    result = TaskResult(task_id=task.task_id)

    user_message = task.prompt
    if task.context:
        user_message = f"Context: {task.context}\n\nTask: {task.prompt}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    start = time.monotonic()
    try:
        completion_kwargs = {
            "model": config.model,
            "messages": messages,
            "temperature": config.temperature,
            "seed": config.seed,
            "timeout": config.timeout_seconds,
        }
        tools = _normalize_tools(config.tools)
        if tools:
            completion_kwargs["tools"] = tools

        response = completion(**completion_kwargs)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        result.output = response.choices[0].message.content or ""
        result.duration_ms = elapsed_ms

        usage = response.usage
        if usage:
            result.tokens_input = usage.prompt_tokens or 0
            result.tokens_output = usage.completion_tokens or 0

        result.tool_calls = _extract_tool_calls(response)

        # Detect skill trigger (heuristic: check if output references skill concepts)
        if config.skill_content:
            result.skill_triggered = _detect_skill_influence(result.output, config.skill_content)
            result.skill_trigger_count = 1 if result.skill_triggered else 0

    except Exception as e:
        result.error = str(e)
        result.duration_ms = int((time.monotonic() - start) * 1000)

    return result


def _detect_skill_influence(output: str, skill_content: str) -> bool:
    """Heuristic to detect if the skill influenced the output.

    Checks if the output contains terminology or patterns that are
    distinctive to the skill content but unlikely in generic responses.
    """
    # Extract distinctive terms from skill (words that appear in skill but are somewhat specific)
    skill_words = set(skill_content.lower().split())
    common_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                    "have", "has", "had", "do", "does", "did", "will", "would", "could",
                    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
                    "on", "with", "at", "by", "from", "as", "into", "through", "during",
                    "before", "after", "above", "below", "between", "and", "but", "or",
                    "not", "no", "if", "then", "than", "that", "this", "it", "its"}
    distinctive = skill_words - common_words

    output_words = set(output.lower().split())
    overlap = distinctive & output_words

    # If more than 5% of distinctive skill terms appear in output, likely influenced
    if len(distinctive) > 0:
        return len(overlap) / len(distinctive) > 0.05
    return False


def _build_run_config(config: RunConfig) -> dict:
    serialized = {
        "model": config.model,
        "temperature": config.temperature,
        "system_prompt": config.system_prompt,
        "tools": config.tools,
        "timeout_seconds": config.timeout_seconds,
        "seed": config.seed,
    }
    if config.skill_content:
        serialized["skill_content_hash"] = hashlib.sha256(
            config.skill_content.encode("utf-8")
        ).hexdigest()[:12]
        serialized["skill_content_preview"] = config.skill_content[:120]
    return {key: value for key, value in serialized.items() if value is not None}


def _normalize_tools(tools: list[str]) -> list[dict]:
    """Convert configured tool names to OpenAI-compatible tool descriptors."""
    normalized: list[dict] = []
    for tool_name in tools:
        name = str(tool_name).strip()
        if not name:
            continue
        normalized.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"Tool: {name}",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": True,
                    },
                },
            }
        )
    return normalized


def _extract_tool_calls(response) -> list[dict]:
    try:
        message = response.choices[0].message
    except Exception:
        return []

    tool_calls = getattr(message, "tool_calls", None) or []
    extracted: list[dict] = []
    for tool_call in tool_calls:
        name = ""
        arguments = {}

        function = getattr(tool_call, "function", None)
        if function is not None:
            name = getattr(function, "name", "") or ""
            raw_arguments = getattr(function, "arguments", "") or ""
            if isinstance(raw_arguments, str):
                try:
                    arguments = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    arguments = {"raw": raw_arguments}
            elif isinstance(raw_arguments, dict):
                arguments = raw_arguments

        extracted.append({"tool": name, "input": arguments})

    return extracted


def save_run(run: EvalRun, output_dir: str | Path) -> Path:
    """Save an EvalRun to JSON."""
    validate_eval_run(run)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run.run_type}_{run.run_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(run.to_dict(), f, indent=2, ensure_ascii=False)
    return path
