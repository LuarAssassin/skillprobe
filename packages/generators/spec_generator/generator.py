"""Generate EvalSpec from a SkillProfile."""

import uuid
from pathlib import Path

from packages.core.skill_profile.models import SkillProfile
from packages.core.eval_spec.models import EvalSpec, MetricWeights, RunConfig, TaskCategory
from packages.core.validation import validate_eval_spec


def generate_eval_spec(
    profile: SkillProfile,
    model: str = "",
    task_count: int = 30,
) -> EvalSpec:
    """Generate an EvalSpec based on a SkillProfile.

    Uses heuristics to determine appropriate task categories and test
    objectives based on the skill's problem domain and capabilities.
    """
    if not model:
        raise ValueError("model is required to generate an evaluation spec")

    # Determine task categories from problem domain
    categories = _infer_categories(profile, task_count)
    default_tools = _infer_default_tools(categories)

    # Build test objectives
    objectives = [
        f"Evaluate whether '{profile.name}' improves agent performance on {domain} tasks"
        for domain in profile.problem_domain[:3]
    ]
    objectives.append(f"Detect regressions or side effects from enabling '{profile.name}'")

    # Read full skill content for injection
    skill_content = _read_full_skill_content(profile)

    # Build baseline config (no skill)
    baseline = RunConfig(
        model=model,
        temperature=0.0,
        system_prompt="You are a helpful AI assistant.",
        tools=default_tools,
        timeout_seconds=120,
        seed=42,
    )

    # Build skill config (with skill injected into system prompt)
    skill_cfg = RunConfig(
        model=model,
        temperature=0.0,
        system_prompt="You are a helpful AI assistant.",
        skill_content=skill_content,
        tools=default_tools,
        timeout_seconds=120,
        seed=42,
    )

    spec = EvalSpec(
        id=str(uuid.uuid4())[:8],
        skill_profile_id=profile.id,
        task_domain=profile.problem_domain,
        test_objectives=objectives,
        task_categories=categories,
        baseline_config=baseline,
        skill_config=skill_cfg,
        metrics=MetricWeights(),
        min_tasks=max(20, task_count),
    )
    validate_eval_spec(spec)
    return spec


def _infer_categories(profile: SkillProfile, total_count: int) -> list[TaskCategory]:
    """Infer task categories from skill profile."""
    domain_keywords = " ".join(profile.problem_domain + profile.capabilities).lower()

    categories = []

    # Map common domain keywords to task categories
    category_map = {
        "retrieval": (["retrieval", "search", "find", "lookup", "query"], "Information retrieval tasks"),
        "qa": (["question", "answer", "qa", "ask", "clinical"], "Question answering tasks"),
        "summarization": (["summary", "summarize", "abstract", "digest"], "Summarization tasks"),
        "structured_extraction": (["extract", "structure", "parse", "field"], "Structured data extraction"),
        "analysis": (["analysis", "analyze", "evaluate", "assess", "review"], "Analysis and evaluation tasks"),
        "coding": (["code", "coding", "program", "implement", "debug", "refactor"], "Coding tasks"),
        "reasoning": (["reason", "logic", "decision", "plan", "design"], "Reasoning and planning tasks"),
    }

    matched = []
    for cat_name, (keywords, desc) in category_map.items():
        if any(kw in domain_keywords for kw in keywords):
            matched.append((cat_name, desc))

    # If no match, default to general categories
    if not matched:
        matched = [("qa", "General question answering"), ("reasoning", "General reasoning tasks")]

    # Distribute count across categories
    per_cat = max(5, total_count // len(matched))
    for cat_name, desc in matched:
        categories.append(TaskCategory(name=cat_name, description=desc, count=per_cat))

    return categories


def _read_full_skill_content(profile: SkillProfile) -> str:
    """Read the full skill content for injection."""
    if profile.source.type == "local" and profile.source.path:
        skill_dir = Path(profile.source.path)
        for name in ("SKILL.md", "skill.md", "README.md"):
            f = skill_dir / name
            if f.exists():
                return f.read_text(encoding="utf-8")
    return profile.content_summary


def _infer_default_tools(categories: list[TaskCategory]) -> list[str]:
    tool_set: set[str] = set()
    category_names = {category.name for category in categories}
    if "retrieval" in category_names:
        tool_set.add("web_search")
    return sorted(tool_set)
