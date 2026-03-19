# SkillProbe Roadmap

## M0: 项目定义 [当前]
- [x] 项目结构
- [x] vision.md
- [x] product-requirements.md
- [x] architecture.md
- [x] scoring-model.md
- [x] roadmap.md

## M1: 对象模型与 Schema
- [ ] skill_profile.schema.json
- [ ] eval_spec.schema.json
- [ ] task.schema.json
- [ ] eval_run.schema.json
- [ ] eval_report.schema.json

## M2: Skill 解析与画像生成
- [ ] SKILL.md 解析器
- [ ] SkillProfile 生成器
- [ ] 示例画像输出

## M3: EvalSpec 生成器
- [ ] 自动生成评测计划
- [ ] 模板化场景支持
- [ ] 人工编辑接口

## M4: 任务生成器
- [ ] 模板生成
- [ ] LLM 扩写生成
- [ ] 任务难度分层
- [ ] JSONL 输出

## M5: A/B Runner
- [ ] Baseline runner
- [ ] Skill runner
- [ ] Trace recorder
- [ ] Artifact collector

## M6: 评分引擎
- [ ] 规则评分器
- [ ] LLM Judge 评分器
- [ ] 聚合评分器

## M7: 归因与报告
- [ ] 归因分析器
- [ ] Markdown 报告生成器
- [ ] JSON 报告导出

## M8: 首个案例
- [ ] 选定 OpenClaw-Medical-Skills 中 1~3 个 skill
- [ ] 完整评测报告
- [ ] 对比分析
- [ ] 演示文档

## M9: Web 展示页（可选）
- [ ] Skill report page
- [ ] Leaderboard page
- [ ] Version compare page
