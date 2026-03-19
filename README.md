# SkillProbe

A/B 评估 AI agent skills 的真实效果，基于评测结果驱动 skills 持续改进。

## 定位

SkillProbe 不是合规审查工具，不是 skill marketplace，而是一个 **效果评估与进化引擎**。

它回答一个核心问题：**某个 skill 被装进 agent 以后，到底带来了多少可量化收益？**

## 核心能力

- **Skill 画像**：解析 skill 文件，生成结构化能力画像
- **评测计划**：根据 skill 目标自动生成评测方案
- **任务生成**：自动生成覆盖正常/边界/歧义场景的测试任务
- **A/B 实验**：同一任务集，skill 开/关两组对比
- **多维评分**：规则评分 + 结果评分，LLM Judge 作为可选扩展层
- **归因分析**：不只说"涨了几分"，还说"为什么涨、哪段 skill 在起作用"
- **改进建议**：基于评测结果输出 skill 优化方向
- **运行时校验**：profile/spec/task/run/report 全部走 JSON Schema 校验

## 快速开始

```bash
# 安装
pip install -e .

# 评估一个 skill
skillprobe evaluate ./path/to/skill --tasks 30

# 只生成 skill 画像
skillprobe profile ./path/to/skill

# 只生成测试任务
skillprobe generate-tasks ./path/to/skill --count 30
```

`evaluate` 会在输出目录生成：
- `tasks.jsonl`
- `baseline_<id>.json`
- `with_skill_<id>.json`
- `report.json`
- `report.md`

## 评分体系

100 分制，6 个维度：

| 维度 | 权重 | 说明 |
|------|------|------|
| Effectiveness | 30 | 任务完成率、正确性、关键目标命中 |
| Quality | 20 | 输出专业性、清晰性、推理充分性 |
| Efficiency | 15 | 耗时、token 成本、工具调用开销 |
| Stability | 15 | 多次运行波动、异常输入抗性 |
| Trigger Fitness | 10 | 触发准确性、克制性 |
| Safety | 10 | 幻觉、冗长化、误导性、冲突 |

派生指标：
- **Net Gain**：启用 skill 后相对 baseline 的净增益
- **Value Index**：净增益 / 额外成本

当前状态说明：
- 本地 CLI 已落地 schema validation、rule-based hard checks、evidence-rich report、reproducibility metadata
- LLM Judge prompt 已准备好，但尚未默认接入最终聚合分
- Stability 仍基于单次 run，后续会扩展到 repeated runs

## 项目结构

```
skillprobe/
  docs/           # 项目文档
  schemas/        # JSON Schema 定义
  packages/       # 核心代码
    core/         # 画像、评分、归因、报告
    runners/      # A/B 实验执行器
    generators/   # 任务和评测计划生成器
    adapters/     # 外部 skill 源适配器
  prompts/        # LLM prompt 模板
  data/           # 种子数据和测试固件
  apps/cli/       # CLI 入口
  outputs/        # 实验输出
```

## 参考项目

- [superpowers](https://github.com/obra/superpowers) - skill 组织与工作流参考
- [OpenClaw-Medical-Skills](https://github.com/FreedomIntelligence/OpenClaw-Medical-Skills) - 首批评测实验品
- [clawhub](https://github.com/openclaw/clawhub) - skill 分发与版本管理参考

## License

MIT
