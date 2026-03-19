---
name: skillprobe
description: >
  A/B evaluate any AI agent skill's real impact. Generates skill profiles,
  synthetic test tasks, compares baseline vs with-skill behavior, performs
  attribution analysis, and produces structured reports with install
  recommendations. Use when you need to decide whether a skill is worth
  enabling, or when optimizing an existing skill.
homepage: https://clawhub.ai/LuarAssassin/skillprobe
metadata:
  clawdbot:
    emoji: "🔬"
    files: ["scripts/*"]
---

# SkillProbe — Skill Effect Evaluator

Evaluate whether an AI agent skill actually improves performance, or just adds complexity.

## How Evaluation Runs (No Extra API Key Required)

This skill is designed to run **inside the same agent or runtime** that will use the evaluated skills (e.g. Cursor agent, OpenClaw, ClaudeCode). In that case:

- **Steps 4–5 (baseline / with-skill)** are executed by the current agent: you run the same test tasks once without the target skill in context, and once with it. The agent’s existing model access is used; no separate `OPENAI_API_KEY` or other API key is required for the skill itself.
- The optional **standalone CLI** (`skillprobe evaluate …`) is for local runs outside an agent; only that path may require a configured LLM API key (e.g. `OPENAI_API_KEY`).

So: **in-agent or in OpenClaw/ClaudeCode, the skill is directly testable** — follow the 7-step workflow using the runtime’s own model and tools.

## When to Use

Trigger this skill when:
- Someone asks "should we install this skill?" or "is this skill worth it?"
- Evaluating a new skill before adoption
- Comparing skill versions (old vs new)
- Investigating why agent performance changed after adding a skill
- Optimizing or improving an existing skill based on data
- Building a skill quality report or leaderboard

## What This Skill Does

SkillProbe gives you a structured methodology to answer: **"Does this skill actually help?"**

It guides you through a 7-step evaluation pipeline:

### Step 1: Profile the Skill

Read the target skill's SKILL.md and extract:
- Problem domain and claimed capabilities
- Trigger conditions
- Dependencies and boundaries
- Content size and complexity

### Step 2: Design the Evaluation Plan

Based on the skill profile, determine:
- Which task categories to test (QA, retrieval, coding, analysis, etc.)
- How many tasks per category
- Difficulty distribution (easy/medium/hard/edge)
- What metrics matter most for this skill
- Success and stopping criteria

### Step 3: Generate Test Tasks

Create a diverse set of test tasks that:
- Cover the skill's claimed value proposition
- Include normal, boundary, and adversarial cases
- Have clear scoring criteria
- Are representative of real-world usage

### Step 4: Run Baseline (No Skill)

Execute all tasks WITHOUT the target skill enabled:
- Record outputs, tool calls when available, and token usage
- Measure duration and note missing traces explicitly if the runtime cannot provide them
- Establish the performance floor

### Step 5: Run With Skill

Execute the SAME tasks WITH the target skill enabled:
- Use identical model, temperature, tools, and seed
- The ONLY variable is skill on/off
- Record skill trigger events (when, how often, whether helpful)

### Step 6: Score Both Runs

Apply layered scoring:

**Layer 1 — Rule-based** (hard requirements):
- Did it produce output?
- Did it call required tools?
- Did it include required fields?
- Did it pass schema validation?

**Layer 2 — Result-based** (objective correctness):
- Answer accuracy vs reference
- Information completeness
- Test pass rate

**Layer 3 — LLM Judge** (soft quality, optional if runtime supports it):
- Reasoning depth
- Professional quality
- Task completion degree
- A vs B preference comparison

Score across 6 dimensions (100-point scale):

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| Effectiveness | 30 | Task completion, correctness, key objective hits |
| Quality | 20 | Professionalism, clarity, reasoning depth |
| Efficiency | 15 | Duration, token cost, tool call overhead |
| Stability | 15 | Run-to-run variance and edge case resilience when repeated runs are available |
| Trigger Fitness | 10 | Trigger accuracy, restraint, utility |
| Safety | 10 | Hallucination, verbosity, misleading content |

### Step 7: Attribute and Report

Determine WHY scores differ:

- **Trigger attribution**: Was the skill actually activated?
- **Step attribution**: Did it change the reasoning approach?
- **Tool attribution**: Did it guide better tool usage?
- **Format attribution**: Did it only change formatting, not substance?
- **Side-effect attribution**: Did it add unnecessary complexity?

Output a structured report with:
- Score comparison table (baseline vs with-skill)
- Net Gain and Value Index
- Per-category breakdown
- Best improvements and worst regressions (with examples)
- Recommendation label: Recommended / Conditionally Recommended / Not Recommended / Needs Revision / Inconclusive
- Specific improvement suggestions for the skill author

## Output Format

The final report should follow this structure:

```markdown
# Skill Evaluation Report: [skill-name]

## Summary
- Recommendation: [LABEL]
- Net Gain: [+/-X.X points]
- Value Index: [X.XX]

## Score Comparison
| Dimension | Baseline | With Skill | Delta |
|-----------|----------|------------|-------|
| ... | ... | ... | ... |

## Attribution
[Why scores differ]

## Improvement Suggestions
[Actionable changes for the skill author]
```

## Key Principles

1. **A/B must be reproducible**: Same model, temperature, seed, tools, tasks. Only variable is skill on/off.
2. **Scoring must be evidence-backed**: Use rules and result checks first; use LLM judge only as an optional additional layer.
3. **Conclusions must have attribution**: Don't just say "+8 points". Say WHY and WHERE.
4. **Evaluation drives improvement**: Every report should include actionable next steps.
5. **Be honest about uncertainty**: If data is insufficient, say "Inconclusive", not "Recommended".

## Derived Metrics

**Net Gain** = score(with_skill) - score(baseline)

**Value Index** = Net Gain / extra_cost
- Where extra_cost accounts for additional tokens and time

## Recommendation Thresholds

| Label | Condition |
|-------|-----------|
| Recommended | Net Gain >= 8, no significant regressions |
| Conditionally Recommended | Net Gain >= 3, some regressions in specific categories |
| Not Recommended | Net Gain < 0 or significant side effects |
| Needs Revision | Potential exists but current version has clear issues |
| Inconclusive | Insufficient data or high variance |

## Packaging Note

- **Primary use**: In ClawHub/OpenClaw or in an agent (e.g. Cursor, ClaudeCode), this skill is used as a prompt-driven workflow. The agent executes baseline and with-skill runs itself using the runtime’s model; no extra API key is required.
- The bundled `scripts/evaluate.sh` is an **optional** helper for standalone local runs; it invokes the SkillProbe Python CLI when installed. That CLI path may require a configured LLM API key (e.g. `OPENAI_API_KEY`).
- If you are not using the CLI, follow the 7-step workflow in this file and state which evidence was or was not directly observable.

## External Endpoints

When run **in-agent or in OpenClaw/ClaudeCode**: the runtime’s existing model is used; no separate endpoint or API key is required by this skill. When run via the **standalone CLI**, the CLI uses a configured LLM provider (e.g. OpenAI); task prompts, skill content, and agent outputs are sent there for execution and optional judge scoring. No other external endpoints. All evaluation logic runs locally.

## Security & Privacy

- Skill content being evaluated is sent to the configured LLM provider for execution
- Task prompts and agent outputs may be sent to the LLM for optional judge scoring
- All evaluation data (profiles, tasks, runs, reports) is stored locally
- No data is sent to SkillProbe servers or any third party beyond the LLM provider
- No telemetry or analytics are collected

## Model Invocation Note

This skill guides the agent through a structured evaluation workflow. When used inside an agent or OpenClaw/ClaudeCode, the runtime performs baseline and with-skill runs using its own model. When using the standalone CLI, the CLI’s configured LLM provider is used. Optional LLM judge scoring is supported where the runtime allows it.

## Trust Statement

When used in-agent or in OpenClaw/ClaudeCode, task prompts and skill content are handled by the same runtime you already use. When using the standalone CLI, they are sent to the CLI’s configured LLM provider. Only install this skill if you trust that runtime or provider with the content of the skills you plan to evaluate.
