"""Skill profile data models."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SkillSource:
    type: str  # "local", "git", "clawhub"
    path: str | None = None
    url: str | None = None
    commit: str | None = None


@dataclass
class SkillDependencies:
    tools: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)


@dataclass
class SkillBoundaries:
    applicable: list[str] = field(default_factory=list)
    not_applicable: list[str] = field(default_factory=list)


@dataclass
class SkillProfile:
    id: str
    name: str
    description: str
    problem_domain: list[str]
    source: SkillSource
    version: str = "0.0.0"
    author: str = ""
    license: str = ""
    trigger_conditions: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    dependencies: SkillDependencies = field(default_factory=SkillDependencies)
    boundaries: SkillBoundaries = field(default_factory=SkillBoundaries)
    content_summary: str = ""
    rule_count: int = 0
    file_count: int = 0
    total_tokens_estimate: int = 0
    profiled_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        source = {"type": self.source.type}
        if self.source.path is not None:
            source["path"] = self.source.path
        if self.source.url is not None:
            source["url"] = self.source.url
        if self.source.commit is not None:
            source["commit"] = self.source.commit

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "license": self.license,
            "source": source,
            "problem_domain": self.problem_domain,
            "trigger_conditions": self.trigger_conditions,
            "capabilities": self.capabilities,
            "dependencies": {
                "tools": self.dependencies.tools,
                "models": self.dependencies.models,
                "data_sources": self.dependencies.data_sources,
            },
            "boundaries": {
                "applicable": self.boundaries.applicable,
                "not_applicable": self.boundaries.not_applicable,
            },
            "content_summary": self.content_summary,
            "rule_count": self.rule_count,
            "file_count": self.file_count,
            "total_tokens_estimate": self.total_tokens_estimate,
            "profiled_at": self.profiled_at,
        }
