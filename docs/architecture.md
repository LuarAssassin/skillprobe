# SkillProbe Architecture

## 系统架构

```
                    +------------------+
                    |    CLI / API     |
                    +--------+---------+
                             |
                    +--------v---------+
                    |    Pipeline      |
                    |   Orchestrator   |
                    +--------+---------+
                             |
        +--------------------+--------------------+
        |          |         |         |          |
   +----v---+ +---v----+ +--v---+ +---v----+ +---v----+
   | Skill  | | Eval   | | Task | |  A/B   | | Report |
   | Ingest | | Spec   | | Gen  | | Runner | |  Gen   |
   +----+---+ | Gen    | +--+---+ +---+----+ +---+----+
        |     +---+----+    |         |          |
        |         |         |    +----+----+     |
        v         v         v    |         |     v
   SkillProfile EvalSpec TaskSet | Score   | EvalReport
                                 | Engine  |
                                 +----+----+
                                      |
                                 +----v----+
                                 | Attrib  |
                                 | Engine  |
                                 +---------+
```

## 数据流

```
Skill Dir/Repo
    |
    v
[Skill Ingestion] --> SkillProfile
    |
    v
[EvalSpec Generator] --> EvalSpec
    |
    v
[Task Generator] --> TaskSet (JSONL)
    |
    +---> [Baseline Runner] --> EvalRun (baseline)
    |
    +---> [Skill Runner] ----> EvalRun (with-skill)
              |
              v
         [Scoring Engine] --> TaskScore[] --> EvalScore
              |
              v
         [Attribution Engine] --> Attribution
              |
              v
         [Report Generator] --> EvalReport (MD + JSON)
              |
              v
         [Improvement Advisor] --> Patches + Suggestions
```

## 技术选型

| 组件 | 技术 | 理由 |
|------|------|------|
| 语言 | Python 3.11+ | AI/LLM 生态最成熟 |
| CLI | Click | 轻量、组合性好 |
| LLM 调用 | litellm | 多模型统一接口 |
| Schema 校验 | jsonschema | 标准 JSON Schema |
| 数据格式 | JSON / JSONL | 通用、可流式 |
| 报告 | Jinja2 | 模板化 Markdown |
| 配置 | YAML | 人类可读 |

## 模块职责

### packages/core/skill_profile/
- 解析 SKILL.md (YAML frontmatter + Markdown)
- 提取元数据、触发条件、问题域
- 输出 SkillProfile JSON

### packages/core/eval_spec/
- EvalSpec 数据模型
- 校验与序列化

### packages/core/scoring/
- RuleScorer: 规则评分
- ResultScorer: 结果评分
- LLMJudgeScorer: LLM 比较评分
- AggregateScorer: 加权聚合

### packages/core/attribution/
- TraceComparator: 轨迹对比
- TriggerAnalyzer: 触发分析
- CausalAnalyzer: 因果归因
- 输出归因报告

### packages/core/reporting/
- MarkdownReporter: Markdown 报告
- JSONReporter: JSON 报告
- 模板管理

### packages/runners/
- BaselineRunner: 无 skill 执行
- SkillRunner: 有 skill 执行
- TraceRecorder: 轨迹记录
- ArtifactCollector: 产物收集

### packages/generators/spec_generator/
- 根据 SkillProfile 推断评测计划
- 模板库管理

### packages/generators/task_generator/
- TemplateGenerator: 模板生成
- LLMGenerator: LLM 扩写生成
- HybridGenerator: 混合生成

### apps/cli/
- 主入口 `skillprobe`
- 子命令：profile, plan, generate-tasks, run, score, report, evaluate (全流程)

## A/B 实验控制变量

必须保证唯一变量是 skill 开/关：
- 同一底模 (model)
- 同一温度 (temperature)
- 同一系统提示 (system prompt)
- 同一工具集 (tools)
- 同一任务集 (task set)
- 同一时间限制 (timeout)
- 同一随机种子 (seed, 如果模型支持)

## 可扩展性

- Adapter 模式支持多种 skill 来源（本地目录、git repo、clawhub）
- Scorer 可插拔，支持自定义评分器
- Runner 可插拔，支持不同 agent 运行时
- Reporter 可插拔，支持不同输出格式
