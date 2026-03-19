"""EvalSpec data model and generator."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TaskCategory:
    name: str
    description: str = ""
    count: int = 10
    difficulty_distribution: dict[str, float] = field(
        default_factory=lambda: {"easy": 0.3, "medium": 0.4, "hard": 0.2, "edge": 0.1}
    )


@dataclass
class RunConfig:
    model: str = ""
    temperature: float = 0.0
    system_prompt: str = ""
    skill_content: str = ""
    tools: list[str] = field(default_factory=list)
    timeout_seconds: int = 120
    seed: int | None = None


@dataclass
class MetricWeights:
    effectiveness: float = 0.30
    quality: float = 0.20
    efficiency: float = 0.15
    stability: float = 0.15
    trigger_fitness: float = 0.10
    safety: float = 0.10


@dataclass
class EvalSpec:
    id: str
    skill_profile_id: str
    task_domain: list[str]
    test_objectives: list[str]
    task_categories: list[TaskCategory]
    baseline_config: RunConfig
    skill_config: RunConfig
    metrics: MetricWeights = field(default_factory=MetricWeights)
    min_net_gain: float = 3.0
    max_regression_rate: float = 0.15
    min_tasks: int = 20
    max_failures: int = 5
    max_cost_usd: float | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "skill_profile_id": self.skill_profile_id,
            "task_domain": self.task_domain,
            "test_objectives": self.test_objectives,
            "task_categories": [
                {
                    "name": c.name,
                    "description": c.description,
                    "count": c.count,
                    "difficulty_distribution": c.difficulty_distribution,
                }
                for c in self.task_categories
            ],
            "baseline_config": {
                "model": self.baseline_config.model,
                "temperature": self.baseline_config.temperature,
                "system_prompt": self.baseline_config.system_prompt,
                "tools": self.baseline_config.tools,
                "timeout_seconds": self.baseline_config.timeout_seconds,
                "seed": self.baseline_config.seed,
            },
            "skill_config": {
                "model": self.skill_config.model,
                "temperature": self.skill_config.temperature,
                "system_prompt": self.skill_config.system_prompt,
                "skill_content": self.skill_config.skill_content[:100] + "...",
                "tools": self.skill_config.tools,
                "timeout_seconds": self.skill_config.timeout_seconds,
                "seed": self.skill_config.seed,
            },
            "metrics": {
                "effectiveness_weight": self.metrics.effectiveness,
                "quality_weight": self.metrics.quality,
                "efficiency_weight": self.metrics.efficiency,
                "stability_weight": self.metrics.stability,
                "trigger_fitness_weight": self.metrics.trigger_fitness,
                "safety_weight": self.metrics.safety,
            },
            "created_at": self.created_at,
        }
