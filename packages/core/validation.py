"""Schema validation helpers for SkillProbe artifacts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_DIR = _PROJECT_ROOT / "schemas"

_SCHEMA_FILES = {
    "skill_profile": "skill_profile.schema.json",
    "eval_spec": "eval_spec.schema.json",
    "task": "task.schema.json",
    "eval_run": "eval_run.schema.json",
    "eval_report": "eval_report.schema.json",
}


class ArtifactValidationError(ValueError):
    """Raised when a serialized artifact does not match its schema."""


def validate_skill_profile(profile: Any) -> dict[str, Any]:
    return _validate("skill_profile", profile)


def validate_eval_spec(spec: Any) -> dict[str, Any]:
    return _validate("eval_spec", spec)


def validate_task(task: Any) -> dict[str, Any]:
    return _validate("task", task)


def validate_eval_run(run: Any) -> dict[str, Any]:
    return _validate("eval_run", run)


def validate_eval_report(report: Any) -> dict[str, Any]:
    return _validate("eval_report", report)


def _validate(schema_name: str, artifact: Any) -> dict[str, Any]:
    payload = _serialize(artifact)
    validator = _load_validator(schema_name)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.absolute_path))
    if errors:
        raise ArtifactValidationError(_format_validation_error(schema_name, errors[0]))
    return payload


def _serialize(artifact: Any) -> dict[str, Any]:
    if isinstance(artifact, dict):
        return artifact
    if hasattr(artifact, "to_dict"):
        return artifact.to_dict()
    raise TypeError(f"Unsupported artifact type for validation: {type(artifact)!r}")


@lru_cache(maxsize=len(_SCHEMA_FILES))
def _load_validator(schema_name: str) -> Draft7Validator:
    try:
        schema_file = _SCHEMA_DIR / _SCHEMA_FILES[schema_name]
    except KeyError as exc:
        raise KeyError(f"Unknown schema name: {schema_name}") from exc

    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    return Draft7Validator(schema, format_checker=FormatChecker())


def _format_validation_error(schema_name: str, error: JsonSchemaValidationError) -> str:
    path = ".".join(str(part) for part in error.absolute_path) or "<root>"
    return f"{schema_name} validation failed at {path}: {error.message}"
