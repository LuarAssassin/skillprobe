"""Parse SKILL.md files and generate SkillProfile."""

import hashlib
import re
from pathlib import Path

import frontmatter

from packages.core.skill_profile.models import (
    SkillBoundaries,
    SkillDependencies,
    SkillProfile,
    SkillSource,
)
from packages.core.validation import validate_skill_profile

# Rough token estimate: ~4 chars per token
CHARS_PER_TOKEN = 4


def parse_skill_dir(skill_path: str | Path) -> SkillProfile:
    """Parse a skill directory and return a SkillProfile.

    Looks for SKILL.md as the primary file. Falls back to README.md.
    Also scans for supporting files (rules/, examples, etc).
    """
    skill_path = Path(skill_path).resolve()
    if not skill_path.is_dir():
        raise ValueError(f"Not a directory: {skill_path}")

    skill_md = _find_skill_file(skill_path)
    if skill_md is None:
        raise FileNotFoundError(f"No SKILL.md or README.md found in {skill_path}")

    post = frontmatter.load(str(skill_md))
    metadata = post.metadata or {}
    content = post.content or ""

    # Count files
    all_files = list(skill_path.rglob("*"))
    file_count = sum(1 for f in all_files if f.is_file() and not _is_hidden(f))

    # Estimate total tokens from all text files
    total_chars = 0
    for f in all_files:
        if f.is_file() and f.suffix in (".md", ".txt", ".yaml", ".yml", ".json"):
            try:
                total_chars += f.stat().st_size
            except OSError:
                pass

    # Extract metadata from frontmatter
    name = metadata.get("name", skill_path.name)
    description = metadata.get("description", "")
    version = str(metadata.get("version", metadata.get("metadata", {}).get("version", "0.0.0")))
    author = metadata.get("author", metadata.get("metadata", {}).get("author", ""))
    license_ = metadata.get("license", "")

    # Generate stable ID
    skill_id = hashlib.sha256(f"{name}:{skill_path}".encode()).hexdigest()[:12]

    # Extract structured info from content
    problem_domain = _extract_domains(content, metadata)
    trigger_conditions = _extract_triggers(content, metadata)
    capabilities = _extract_capabilities(content)
    rule_count = _count_rules(skill_path, content)

    profile = SkillProfile(
        id=skill_id,
        name=name,
        description=description if isinstance(description, str) else str(description),
        version=version,
        author=author,
        license=license_,
        source=SkillSource(type="local", path=str(skill_path)),
        problem_domain=problem_domain,
        trigger_conditions=trigger_conditions,
        capabilities=capabilities,
        dependencies=SkillDependencies(),
        boundaries=SkillBoundaries(),
        content_summary=content[:500] + ("..." if len(content) > 500 else ""),
        rule_count=rule_count,
        file_count=file_count,
        total_tokens_estimate=total_chars // CHARS_PER_TOKEN,
    )
    validate_skill_profile(profile)
    return profile


def _find_skill_file(skill_path: Path) -> Path | None:
    """Find the primary skill definition file."""
    for name in ("SKILL.md", "skill.md", "README.md", "readme.md"):
        candidate = skill_path / name
        if candidate.exists():
            return candidate
    return None


def _is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def _extract_domains(content: str, metadata: dict) -> list[str]:
    """Extract problem domains from content and metadata."""
    domains = []
    # Check metadata
    if "domain" in metadata:
        val = metadata["domain"]
        domains.extend(val if isinstance(val, list) else [val])
    if "tags" in metadata:
        domains.extend(metadata["tags"] if isinstance(metadata["tags"], list) else [])

    # Heuristic: look for "use when" / "trigger when" patterns
    patterns = [
        r"(?:use|trigger|invoke)\s+(?:this\s+)?(?:skill\s+)?when\s+(.+?)(?:\.|$)",
        r"(?:best for|designed for|helps with)[:\s]+(.+?)(?:\.|$)",
    ]
    for pat in patterns:
        for match in re.finditer(pat, content, re.IGNORECASE | re.MULTILINE):
            domains.append(match.group(1).strip()[:100])

    return domains[:10] if domains else ["general"]


def _extract_triggers(content: str, metadata: dict) -> list[str]:
    """Extract trigger conditions."""
    triggers = []
    desc = metadata.get("description", "")
    if isinstance(desc, str):
        # Look for trigger-like sentences in description
        for line in desc.split("\n"):
            line = line.strip()
            if any(kw in line.lower() for kw in ("trigger", "when", "use this")):
                triggers.append(line[:200])

    # Look for trigger sections in content
    in_trigger = False
    for line in content.split("\n"):
        stripped = line.strip()
        if re.match(r"^#+\s*.*trigger", stripped, re.IGNORECASE):
            in_trigger = True
            continue
        if in_trigger:
            if stripped.startswith("#"):
                in_trigger = False
            elif stripped.startswith("- ") or stripped.startswith("* "):
                triggers.append(stripped.lstrip("-* ").strip()[:200])

    return triggers[:10]


def _extract_capabilities(content: str) -> list[str]:
    """Extract capability descriptions from content headers and lists."""
    caps = []
    for match in re.finditer(r"^##\s+(.+)$", content, re.MULTILINE):
        heading = match.group(1).strip()
        if len(heading) < 100 and not heading.lower().startswith(("table of", "reference")):
            caps.append(heading)
    return caps[:15]


def _count_rules(skill_path: Path, content: str) -> int:
    """Count rules/guidelines in the skill."""
    count = 0
    # Count rule files in rules/ directory
    rules_dir = skill_path / "rules"
    if rules_dir.is_dir():
        count += sum(1 for f in rules_dir.iterdir() if f.is_file() and f.suffix == ".md")

    # Count numbered list items or rule-like patterns in content
    count += len(re.findall(r"^\d+\.\s+", content, re.MULTILINE))
    count += len(re.findall(r"^-\s+\*\*[A-Z]", content, re.MULTILINE))

    return count
