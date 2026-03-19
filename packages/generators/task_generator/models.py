"""Task data model."""

from dataclasses import dataclass, field


@dataclass
class ScoringHints:
    key_points: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    required_fields: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)


@dataclass
class Task:
    task_id: str
    task_type: str  # retrieval, qa, summarization, etc.
    prompt: str
    difficulty: str  # easy, medium, hard, edge
    context: str = ""
    expected_artifacts: list[str] = field(default_factory=list)
    reference_answer: str = ""
    scoring_hints: ScoringHints = field(default_factory=ScoringHints)
    risk_level: str = "low"
    category: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "prompt": self.prompt,
            "context": self.context,
            "expected_artifacts": self.expected_artifacts,
            "reference_answer": self.reference_answer,
            "scoring_hints": {
                "key_points": self.scoring_hints.key_points,
                "required_tools": self.scoring_hints.required_tools,
                "required_fields": self.scoring_hints.required_fields,
                "anti_patterns": self.scoring_hints.anti_patterns,
            },
            "difficulty": self.difficulty,
            "risk_level": self.risk_level,
            "category": self.category,
            "tags": self.tags,
        }
