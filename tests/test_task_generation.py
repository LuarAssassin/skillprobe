from packages.core.eval_spec.models import EvalSpec, MetricWeights, RunConfig, TaskCategory
from packages.core.skill_profile.parser import parse_skill_dir
from packages.generators.task_generator.generator import generate_tasks


def test_generate_tasks_honors_requested_count_for_single_category():
    profile = parse_skill_dir("examples/sample-skill")
    spec = EvalSpec(
        id="spec-001",
        skill_profile_id=profile.id,
        task_domain=["general"],
        test_objectives=["Verify task count handling."],
        task_categories=[
            TaskCategory(
                name="analysis",
                description="Analysis tasks",
                count=6,
                difficulty_distribution={"easy": 0.3, "medium": 0.4, "hard": 0.2, "edge": 0.1},
            )
        ],
        baseline_config=RunConfig(model="gpt-4o-mini"),
        skill_config=RunConfig(model="gpt-4o-mini", skill_content="sample"),
        metrics=MetricWeights(),
    )

    tasks = generate_tasks(profile, spec)

    assert len(tasks) == 6
