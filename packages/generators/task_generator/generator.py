"""Generate synthetic test tasks from EvalSpec and SkillProfile."""

import json
import re
import uuid
from pathlib import Path

from packages.core.eval_spec.models import EvalSpec, TaskCategory
from packages.core.skill_profile.models import SkillProfile
from packages.core.validation import validate_task
from packages.generators.task_generator.models import ScoringHints, Task

# Template-based task generation for common categories
_TASK_TEMPLATES: dict[str, list[dict]] = {
    "qa": [
        {
            "prompt": "What are the key differences between {topic_a} and {topic_b}?",
            "difficulty": "easy",
            "hints": ["comparison", "clarity"],
        },
        {
            "prompt": "Explain the mechanism of action of {topic_a} and its clinical implications.",
            "difficulty": "medium",
            "hints": ["accuracy", "depth"],
        },
        {
            "prompt": "A patient presents with {symptom}. Given conflicting evidence about {topic_a}, what is the most evidence-based approach?",
            "difficulty": "hard",
            "hints": ["evidence-based", "nuance"],
        },
        {
            "prompt": "Is it true that {false_claim}? Explain why or why not.",
            "difficulty": "edge",
            "hints": ["hallucination-resistance", "correction"],
        },
    ],
    "retrieval": [
        {
            "prompt": "Find recent research on {topic_a} published in the last 2 years.",
            "difficulty": "easy",
            "hints": ["recency", "relevance"],
        },
        {
            "prompt": "Summarize the top 3 clinical trials investigating {topic_a} for {condition}.",
            "difficulty": "medium",
            "hints": ["specificity", "completeness"],
        },
        {
            "prompt": "Compare the findings of {study_a} and {study_b} regarding {topic_a}.",
            "difficulty": "hard",
            "hints": ["cross-reference", "accuracy"],
        },
    ],
    "summarization": [
        {
            "prompt": "Summarize the following text in 3 bullet points:\n\n{text_block}",
            "difficulty": "easy",
            "hints": ["conciseness", "key-points"],
        },
        {
            "prompt": "Create a structured clinical summary from the following patient notes:\n\n{text_block}",
            "difficulty": "medium",
            "hints": ["structure", "completeness"],
        },
        {
            "prompt": "Synthesize findings from these 3 abstracts into a coherent evidence summary:\n\n{text_block}",
            "difficulty": "hard",
            "hints": ["synthesis", "coherence"],
        },
    ],
    "coding": [
        {
            "prompt": "Write a function that {coding_task}.",
            "difficulty": "easy",
            "hints": ["correctness", "readability"],
        },
        {
            "prompt": "Refactor the following code to improve {quality_aspect}:\n\n{code_block}",
            "difficulty": "medium",
            "hints": ["improvement", "no-regression"],
        },
        {
            "prompt": "Debug the following code that fails when {edge_case}:\n\n{code_block}",
            "difficulty": "hard",
            "hints": ["root-cause", "fix-correctness"],
        },
    ],
    "reasoning": [
        {
            "prompt": "Given {scenario}, what would be the best approach and why?",
            "difficulty": "medium",
            "hints": ["logic", "justification"],
        },
        {
            "prompt": "Evaluate the trade-offs between {option_a} and {option_b} for {goal}.",
            "difficulty": "hard",
            "hints": ["trade-off-analysis", "completeness"],
        },
    ],
    "analysis": [
        {
            "prompt": "Analyze the following data and identify key patterns:\n\n{data_block}",
            "difficulty": "medium",
            "hints": ["pattern-recognition", "insight"],
        },
    ],
    "structured_extraction": [
        {
            "prompt": "Extract the following fields from this text: {fields}\n\nText: {text_block}",
            "difficulty": "medium",
            "hints": ["completeness", "accuracy"],
        },
    ],
}


def generate_tasks(
    profile: SkillProfile,
    spec: EvalSpec,
) -> list[Task]:
    """Generate a set of test tasks based on profile and spec.

    Uses template-based generation. For production use, this should be
    augmented with LLM-based task generation.
    """
    tasks: list[Task] = []

    for category in spec.task_categories:
        cat_tasks = _generate_category_tasks(profile, category)
        tasks.extend(cat_tasks)

    return tasks


def _generate_category_tasks(
    profile: SkillProfile,
    category: TaskCategory,
) -> list[Task]:
    """Generate tasks for a single category."""
    templates = _TASK_TEMPLATES.get(category.name, _TASK_TEMPLATES.get("reasoning", []))
    tasks = []

    # Distribute across difficulty levels
    counts = _allocate_difficulty_counts(category.count, category.difficulty_distribution)

    # Fill placeholders with skill-relevant content
    placeholders = _build_placeholders(profile)

    task_num = 0
    for difficulty, count in counts.items():
        matching = [t for t in templates if t["difficulty"] == difficulty]
        if not matching:
            matching = templates  # fallback to any template

        for i in range(count):
            template = matching[i % len(matching)]
            prompt = template["prompt"]

            # Substitute placeholders
            for key, values in placeholders.items():
                if f"{{{key}}}" in prompt:
                    prompt = prompt.replace(f"{{{key}}}", values[task_num % len(values)])

            task_num += 1
            scoring_hints = _build_scoring_hints(category, template, prompt)
            task = Task(
                task_id=f"{category.name}-{uuid.uuid4().hex[:6]}",
                task_type=category.name,
                prompt=prompt,
                difficulty=difficulty,
                category=category.name,
                scoring_hints=scoring_hints,
                risk_level="low" if difficulty in ("easy", "medium") else "medium",
                tags=profile.problem_domain[:3],
            )
            validate_task(task)
            tasks.append(task)

    return tasks[:category.count]


def _allocate_difficulty_counts(total_count: int, distribution: dict[str, float]) -> dict[str, int]:
    """Allocate difficulty counts while preserving the requested total.

    Uses a largest-remainder strategy so fractional weights do not silently
    drop tasks when `total_count` is small.
    """
    if total_count <= 0:
        return {difficulty: 0 for difficulty in distribution}

    raw_counts = {
        difficulty: total_count * max(weight, 0.0)
        for difficulty, weight in distribution.items()
    }
    counts = {
        difficulty: int(raw_count)
        for difficulty, raw_count in raw_counts.items()
    }

    assigned = sum(counts.values())
    remaining = total_count - assigned

    if remaining > 0:
        by_remainder = sorted(
            distribution,
            key=lambda difficulty: (raw_counts[difficulty] - counts[difficulty], raw_counts[difficulty]),
            reverse=True,
        )
        for difficulty in by_remainder[:remaining]:
            counts[difficulty] += 1

    return counts


def _build_placeholders(profile: SkillProfile) -> dict[str, list[str]]:
    """Build placeholder values from skill profile."""
    domains = profile.problem_domain if profile.problem_domain else ["the target domain"]
    caps = profile.capabilities if profile.capabilities else ["general tasks"]

    return {
        "topic_a": domains + caps[:3],
        "topic_b": (caps + domains)[:5],
        "condition": domains[:3] + ["general use case"],
        "symptom": ["unexpected behavior", "performance degradation", "incorrect output"],
        "false_claim": [
            f"{domains[0]} is always the best approach",
            f"There is no evidence supporting {domains[0] if domains else 'this approach'}",
        ],
        "study_a": ["Study A (2024)", "RCT-2023-001"],
        "study_b": ["Study B (2023)", "Meta-analysis-2024"],
        "text_block": [
            f"[Sample text about {d} would be inserted here for evaluation]"
            for d in domains[:3]
        ] or ["[Sample text would be inserted here]"],
        "coding_task": ["parses the input", "validates the schema", "transforms the data"],
        "code_block": ["[Code sample would be inserted here]"],
        "quality_aspect": ["readability", "performance", "error handling"],
        "edge_case": ["input is empty", "input contains special characters"],
        "scenario": [f"working with {d}" for d in domains[:3]] or ["a complex scenario"],
        "option_a": ["approach A", "method 1"],
        "option_b": ["approach B", "method 2"],
        "goal": [f"improving {d}" for d in domains[:2]] or ["the objective"],
        "data_block": ["[Data would be inserted here]"],
        "fields": ["name, date, category, value"],
    }


def _build_scoring_hints(category: TaskCategory, template: dict, prompt: str) -> ScoringHints:
    key_points = list(template.get("hints", []))
    required_tools: list[str] = []
    required_fields: list[str] = []
    anti_patterns: list[str] = []

    if category.name == "retrieval":
        required_tools.append("web_search")
        anti_patterns.extend(["cannot browse", "can't browse"])

    if category.name == "structured_extraction":
        required_fields.extend(_extract_required_fields_from_prompt(prompt))

    if category.name == "summarization":
        required_fields.append("summary")

    return ScoringHints(
        key_points=key_points,
        required_tools=required_tools,
        required_fields=required_fields,
        anti_patterns=anti_patterns,
    )


def _extract_required_fields_from_prompt(prompt: str) -> list[str]:
    match = re.search(r"fields from this text:\s*([^\n]+)", prompt, re.IGNORECASE)
    if not match:
        return []

    raw_fields = match.group(1)
    fields = [part.strip() for part in raw_fields.split(",")]
    return [field for field in fields if field]


def save_tasks_jsonl(tasks: list[Task], output_path: str | Path) -> Path:
    """Save tasks as JSONL file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for task in tasks:
            validate_task(task)
            f.write(json.dumps(task.to_dict(), ensure_ascii=False) + "\n")
    return output_path
