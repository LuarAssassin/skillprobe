# SkillProbe Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make SkillProbe's published package, runtime outputs, and reported scores internally consistent, machine-validated, and test-covered without discarding the current prompt-driven workflow that already performs well in OpenClaw.

**Architecture:** Keep the existing prompt-first evaluation flow, but add a validation layer around every core artifact (`SkillProfile`, `EvalSpec`, `Task`, `EvalRun`, `EvalReport`) and strengthen the runner/scoring pipeline so published claims map to concrete evidence. Treat the ClawHub package as a lightweight front-end to the methodology, while the local Python project remains the deterministic execution engine.

**Tech Stack:** Python 3.11+, Click, LiteLLM, jsonschema, pytest, Markdown/JSON schemas

---

### Task 1: Add a real test baseline

**Files:**
- Create: `/Users/luarassassin/reference-projects-me/skillprobe/tests/test_validation.py`
- Create: `/Users/luarassassin/reference-projects-me/skillprobe/tests/test_scoring.py`
- Create: `/Users/luarassassin/reference-projects-me/skillprobe/tests/test_reporting.py`
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/pyproject.toml`

**Step 1: Write the failing tests**

Add tests that prove:
- current generated `EvalSpec` can be validated against schema
- current `EvalRun` serialization can be validated against schema
- current `EvalReport` serialization can be validated against schema
- rule-based scoring checks `required_fields`, `required_tools`, and anti-pattern penalties

**Step 2: Run tests to verify they fail**

Run: `cd /Users/luarassassin/reference-projects-me/skillprobe && python -m pytest -q`

Expected:
- new tests fail because validation utilities do not exist yet
- existing project still has no meaningful passing baseline

**Step 3: Implement the minimum project scaffolding needed by the tests**

Add the smallest code needed to import validation helpers and exercise the current data models.

**Step 4: Run tests again**

Run: `cd /Users/luarassassin/reference-projects-me/skillprobe && python -m pytest -q`

Expected:
- test collection succeeds
- failures narrow to the missing runtime behavior, not missing files

### Task 2: Validate every core artifact at runtime

**Files:**
- Create: `/Users/luarassassin/reference-projects-me/skillprobe/packages/core/validation.py`
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/packages/core/skill_profile/parser.py`
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/packages/core/eval_spec/models.py`
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/packages/generators/task_generator/models.py`
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/packages/runners/runner.py`
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/packages/core/reporting/generator.py`
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/apps/cli/main.py`

**Step 1: Write the failing validation-focused tests**

Extend tests to assert:
- invalid objects raise a clear `ValidationError`
- saved JSON artifacts are schema-valid
- CLI commands do not emit invalid report shapes

**Step 2: Run only the failing validation tests**

Run: `cd /Users/luarassassin/reference-projects-me/skillprobe && python -m pytest tests/test_validation.py -q`

Expected:
- failures point to missing schema loading and invalid serialized shapes

**Step 3: Write minimal validation code**

Implement:
- schema loader and cache
- `validate_skill_profile`, `validate_eval_spec`, `validate_task`, `validate_run`, `validate_report`
- runtime validation before save/return in CLI and persistence functions

**Step 4: Make model serialization match schemas**

Adjust `to_dict()` shapes so schemas and runtime agree.

**Step 5: Re-run validation tests**

Run: `cd /Users/luarassassin/reference-projects-me/skillprobe && python -m pytest tests/test_validation.py -q`

Expected:
- validation tests pass

### Task 3: Turn scoring from heuristics-only into evidence-backed rule scoring

**Files:**
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/packages/core/scoring/engine.py`
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/packages/runners/runner.py`
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/packages/core/reporting/generator.py`
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/tests/test_scoring.py`
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/tests/test_reporting.py`

**Step 1: Write the failing scoring tests**

Add tests that require:
- rule-based score to respect `required_fields`
- rule-based score to respect `required_tools`
- anti-patterns to reduce safety or rule outcomes
- reports to include evidence instead of only aggregate totals

**Step 2: Run the scoring tests and verify failure**

Run: `cd /Users/luarassassin/reference-projects-me/skillprobe && python -m pytest tests/test_scoring.py tests/test_reporting.py -q`

Expected:
- failures show current score engine ignores required tools/fields and report omits evidence

**Step 3: Implement the minimal scoring changes**

Add:
- structured rule checks
- rule/result evidence notes
- richer run config metadata for reproducibility
- report sections that expose scoring evidence and comparison context

**Step 4: Re-run the scoring/report tests**

Run: `cd /Users/luarassassin/reference-projects-me/skillprobe && python -m pytest tests/test_scoring.py tests/test_reporting.py -q`

Expected:
- scoring/report tests pass

### Task 4: Harden runner traces and published execution path

**Files:**
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/packages/runners/runner.py`
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/clawhub/SKILL.md`
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/clawhub/README.md`
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/clawhub/scripts/evaluate.sh`
- Modify: `/Users/luarassassin/reference-projects-me/skillprobe/README.md`

**Step 1: Write the failing runner/publish tests**

Add tests that require:
- run config to persist enough reproducibility metadata
- published helper script to fail gracefully with actionable instructions when runtime is absent

**Step 2: Run targeted tests**

Run: `cd /Users/luarassassin/reference-projects-me/skillprobe && python -m pytest tests/test_validation.py tests/test_reporting.py -q`

Expected:
- failures indicate missing metadata or mismatched publish assumptions

**Step 3: Implement minimal runtime and package fixes**

Add:
- reproducibility metadata such as system prompt, tool list, skill hash, timeout
- safer helper script with runtime detection and clear fallback instructions
- documentation wording that distinguishes prompt-only ClawHub usage from local CLI execution

**Step 4: Re-run the targeted tests**

Run: `cd /Users/luarassassin/reference-projects-me/skillprobe && python -m pytest -q`

Expected:
- test suite passes cleanly

### Task 5: Verify end-to-end behavior

**Files:**
- Use existing files only

**Step 1: Run an end-to-end dry evaluation against the sample skill**

Run: `cd /Users/luarassassin/reference-projects-me/skillprobe && python -m apps.cli.main profile ./examples/sample-skill`

Expected:
- valid JSON output

**Step 2: Run plan and task generation**

Run: `cd /Users/luarassassin/reference-projects-me/skillprobe && python -m apps.cli.main plan ./examples/sample-skill --tasks 6`

Expected:
- valid plan JSON

Run: `cd /Users/luarassassin/reference-projects-me/skillprobe && python -m apps.cli.main generate-tasks ./examples/sample-skill --count 6 --output /tmp/skillprobe-tasks.jsonl`

Expected:
- schema-valid JSONL task file

**Step 3: If API credentials are available, run a small live evaluation**

Run: `cd /Users/luarassassin/reference-projects-me/skillprobe && python -m apps.cli.main evaluate ./examples/sample-skill --model gpt-4o --tasks 2 --output-dir /tmp/skillprobe-eval`

Expected:
- valid run artifacts and report

If credentials are unavailable, explicitly report that live evaluation could not be completed.
