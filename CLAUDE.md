# SkillProbe Development Guide

## Project Structure

- `docs/` - 项目文档（vision, PRD, architecture, scoring model, roadmap）
- `schemas/` - JSON Schema 定义（5 个核心对象）
- `packages/core/` - 核心模块（skill_profile, eval_spec, scoring, attribution, reporting）
- `packages/runners/` - A/B 实验执行器
- `packages/generators/` - 任务和评测计划生成器
- `prompts/` - LLM prompt 模板
- `apps/cli/` - CLI 入口

## Quick Start

```bash
# Install
pip install -e .

# Profile a skill
python -m apps.cli.main profile ./examples/sample-skill

# Full evaluation
python -m apps.cli.main evaluate ./examples/sample-skill --model gpt-4o --tasks 30
```

## Key Design Decisions

- 评分体系 100 分制，6 维度（见 docs/scoring-model.md）
- A/B 实验唯一变量是 skill 开/关
- 三层评分：规则 + 结果 + LLM Judge
- 归因分析覆盖 5 个维度：触发、步骤、工具、格式、副作用

## Dependencies

- Python 3.11+
- litellm (多模型统一接口)
- click (CLI)
- python-frontmatter (SKILL.md 解析)
- jsonschema (schema 校验)
- jinja2 (报告模板)
