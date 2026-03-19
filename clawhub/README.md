# SkillProbe

A/B evaluate any AI agent skill's real impact.

## What It Does

SkillProbe is a skill that gives your agent the ability to evaluate OTHER skills. In ClawHub/OpenClaw it is primarily a prompt-driven evaluation workflow; the helper script only works when the full local SkillProbe Python project is also installed.

It provides a structured 7-step methodology:

1. Profile the target skill
2. Design an evaluation plan
3. Generate test tasks
4. Run baseline (no skill)
5. Run with skill
6. Score across 6 dimensions
7. Attribute differences and generate report

## Install

```bash
clawhub install skillprobe
```

## Requirements

- **In-agent or OpenClaw/ClaudeCode**: none. The runtime runs baseline and with-skill tasks using its own model; no extra API key is required.
- **Standalone local CLI** (optional): Python 3.11+, `pip install -e /path/to/skillprobe`, and a configured LLM API key (e.g. `OPENAI_API_KEY`) only when you run the CLI outside an agent.

## Usage

Ask your agent:
- "Evaluate whether [skill-name] is worth installing"
- "Compare the old and new versions of [skill-name]"
- "Should we keep [skill-name] enabled?"

The agent will follow the SkillProbe methodology to produce a structured evaluation report with scores, attribution analysis, and actionable recommendations.

If you want deterministic local artifacts (`tasks.jsonl`, run JSON, report JSON/Markdown), install the full SkillProbe project and run:

```bash
skillprobe evaluate ./path/to/skill --tasks 30
```

## Scoring Dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Effectiveness | 30% | Task completion and correctness |
| Quality | 20% | Output professionalism and reasoning |
| Efficiency | 15% | Time and token cost |
| Stability | 15% | Consistency across runs |
| Trigger Fitness | 10% | Activation accuracy |
| Safety | 10% | Absence of side effects |

## Current Implementation Notes

- The ClawHub package is optimized for prompt-guided use inside OpenClaw.
- The local Python project validates profiles/specs/tasks/runs/reports against JSON Schema at runtime.
- Rule-based scoring checks required fields and required tools when tasks specify them.
- LLM judge and multi-run stability analysis are still planned extensions, not default-on behavior in the current local runtime.

## License

MIT
