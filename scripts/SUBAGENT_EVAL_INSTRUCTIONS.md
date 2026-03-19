# SkillProbe 子 Agent 评测任务说明

你负责对**一批** OpenClaw-Medical-Skills 做 in-agent 评测，并返回结构化 JSON 结果。

## 输入

- 工作区目录 `skillprobe/outputs/batch_skills/batch_N/` 下有多条技能，每条技能一个子目录，内含 `SKILL.md`（或 `README.md`）。
- 同目录下有 `manifest.json`，格式为 `[{"skill_id": "xxx", "name": "skill-name"}, ...]`，用于在结果中填写 `skill_id`。

## 对每条技能执行

1. **Profile**：阅读该技能的 `SKILL.md`，把握领域、触发条件、能力边界。
2. **设计 2 个测试任务**：与技能声称价值相关、可答的短任务（一两句话的 prompt）。
3. **Baseline**：在不加载该技能的前提下，对 2 个任务各给出一段回答（模拟“无技能”的通用助手）。
4. **With-skill**：在遵循该技能内容的前提下，对同一 2 个任务再各给出一段回答。
5. **评分**：对 baseline 与 with_skill 各打 0–100 总分（可按 6 维度：Effectiveness 30、Quality 20、Efficiency 15、Stability 15、Trigger Fitness 10、Safety 10 粗估后加总）。
6. **结论**：`net_gain = with_skill_total - baseline_total`；`recommendation_label` 取其一：`Recommended` | `Conditionally Recommended` | `Not Recommended` | `Needs Revision` | `Inconclusive`。

## 输出格式

返回一个 **JSON 数组**，每个元素对应一条技能的评测结果，格式如下：

```json
{
  "skill_id": "从 manifest.json 取的 id",
  "status": "completed",
  "baseline_total": 55.0,
  "with_skill_total": 78.0,
  "net_gain": 23.0,
  "recommendation_label": "Recommended",
  "recommendation_detail": "一两句说明",
  "report_summary": "简短总结，2–3 句",
  "tasks": [
    {
      "prompt": "任务 1 的 prompt",
      "baseline_output": "无技能时的回答",
      "with_skill_output": "有技能时的回答",
      "baseline_scores": {"effectiveness": 12, "quality": 10, "efficiency": 8, "stability": 8, "trigger_fitness": 5, "safety": 6},
      "with_skill_scores": {"effectiveness": 22, "quality": 16, "efficiency": 10, "stability": 10, "trigger_fitness": 8, "safety": 8}
    },
    {
      "prompt": "任务 2 的 prompt",
      "baseline_output": "...",
      "with_skill_output": "...",
      "baseline_scores": {},
      "with_skill_scores": {}
    }
  ]
}
```

若某条技能无法评测（如无 SKILL.md、无法解析），可返回 `"status": "failed"`，并设 `error_message`，其他数值可为 null。

## 要求

- 必须按 manifest 中的顺序或名单，**每条技能都对应一个结果对象**，且 `skill_id` 与 manifest 一致。
- 最终回复中**只输出一个 JSON 数组**，不要包在 markdown 代码块里（方便主流程解析）；若必须用代码块，请标明 `results` 并只放该数组。
