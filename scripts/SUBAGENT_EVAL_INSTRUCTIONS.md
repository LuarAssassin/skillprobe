# SkillProbe 子 Agent 评测任务说明（三角色隔离架构）

你是**编排者（Orchestrator）**，负责对一批 OpenClaw-Medical-Skills 做 in-agent A/B 评测。

本说明采用**三角色隔离架构**：你（编排者）只做准备和评分，测试任务的实际执行**必须委托给两个独立的子 agent**。

对每条技能，复制此清单跟踪进度：

```
评测进度：
- [ ] 阶段一：Profile 技能 + 设计 2 个测试任务
- [ ] 阶段二-A：派发 Baseline 子 agent（不含 skill 内容）
- [ ] 阶段二-B：派发 With-Skill 子 agent（含完整 skill）
- [ ] 阶段三：收集两臂结果 + 逐任务评分 + 归因 + 结论
```

---

## 输入

- `skillprobe/outputs/batch_skills/batch_N/` 下有多条技能，每条一个子目录，内含 `SKILL.md`（或 `README.md`）。
- 同目录 `manifest.json` 格式：`[{"skill_id": "xxx", "name": "skill-name"}, ...]`

---

## 对每条技能的三阶段流程

### 阶段一：准备（你来做）

1. **Profile**：阅读该技能的 `SKILL.md`，把握领域、触发条件、能力边界。
2. **设计 2 个测试任务**：与技能声称价值相关、可答的短任务（一两句话的 prompt）。
   - 为每个任务分配 `task_id`（格式：`task-001`, `task-002`）
   - 任务 prompt 中**禁止提及**技能名称或 A/B 实验
   - 任务必须自包含，无跨任务依赖

### 阶段二：派发执行（你委托，自己不执行）

你必须创建**两个独立的子 agent 会话**来执行任务。

#### 派发给 Sub-Agent A（Baseline）

用以下 prompt 创建一个**新的子 agent**。**严禁**在此 prompt 中包含任何技能内容：

```
你是一个任务执行者。请独立完成以下每个任务，基于你自己的知识和能力作答。

规则：
- 逐个独立回答每个任务
- 不要阅读、引用或应用任何额外的技能文件或指令集
- 不要询问额外的上下文或技能
- 给出你的最佳回答

任务列表：
1. [task-001] {粘贴任务1的 prompt}
2. [task-002] {粘贴任务2的 prompt}

输出格式：
返回一个 JSON 数组，每个元素对应一个任务：
[{"task_id": "task-001", "output": "你的回答", "reasoning_summary": "思路"}]
只返回 JSON 数组。
```

#### 派发给 Sub-Agent B（With-Skill）

用以下 prompt 创建**另一个新的子 agent**。**必须**包含完整技能内容：

```
你是一个任务执行者。在回答之前，先阅读并理解以下技能内容，然后将其指导应用到每个任务中。

## 需应用的技能
{粘贴被测技能的完整 SKILL.md 内容}

---

规则：
- 先理解上面的技能内容
- 将技能方法论应用到每个任务中
- 逐个独立回答

任务列表：
1. [task-001] {与 Arm A 完全相同的任务 prompt}
2. [task-002] {与 Arm A 完全相同的任务 prompt}

输出格式：
返回一个 JSON 数组：
[{"task_id": "task-001", "output": "你的回答", "reasoning_summary": "思路及技能影响", "skill_applied": true, "skill_influence_notes": "技能改变了什么"}]
只返回 JSON 数组。
```

#### 派发约束

| 约束 | 要求 |
|------|------|
| 隔离性 | Arm A 和 Arm B 必须是**不同的子 agent 会话**（不同 session_id） |
| 单臂单会话 | 同一个子 agent 中**禁止同时执行两个臂** |
| 变量控制 | 两臂使用相同模型、温度、工具配置；唯一变量是技能开/关 |
| 技能隔离 | Arm A 的 prompt 中**绝不出现**技能内容、技能名称、技能描述 |
| 证据记录 | 记录每个子 agent 的 `session_id` / `agent_id` |

### 阶段三：评分与报告（你来做）

收到两个子 agent 的输出后：

1. **配对对齐**：按 task_id 匹配 baseline 和 with-skill 输出
2. **逐任务评分**：对 baseline 与 with_skill 各打 0–100 总分
   - Effectiveness 30 / Quality 20 / Efficiency 15 / Stability 15 / Trigger Fitness 10 / Safety 10
3. **汇总**：`net_gain = with_skill_total - baseline_total`
4. **结论标签**：`Recommended` | `Conditionally Recommended` | `Not Recommended` | `Needs Revision` | `Inconclusive`
   - 不允许因"预判 runtime 不支持"而直接 `Inconclusive`
   - 仅当真实尝试后证据不足（如重复硬失败）才允许 `Inconclusive`

---

## 输出格式

返回一个 **JSON 数组**，每个元素对应一条技能：

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
  "dispatch_evidence": {
    "orchestrator_role": "prepare_and_score_only",
    "baseline_agent_session_id": "arm-a-session-id",
    "skill_agent_session_id": "arm-b-session-id",
    "baseline_prompt_contains_skill": false
  },
  "tasks": [
    {
      "prompt": "任务 prompt",
      "baseline_output": "Sub-Agent A 的原始输出",
      "with_skill_output": "Sub-Agent B 的原始输出",
      "baseline_evidence": {"session_id": "arm-a-session-id", "agent_id": "arm-a-agent-id", "timestamp": "..."},
      "with_skill_evidence": {"session_id": "arm-b-session-id", "agent_id": "arm-b-agent-id", "timestamp": "..."},
      "baseline_scores": {"effectiveness": 12, "quality": 10, "efficiency": 8, "stability": 8, "trigger_fitness": 5, "safety": 6},
      "with_skill_scores": {"effectiveness": 22, "quality": 16, "efficiency": 10, "stability": 10, "trigger_fitness": 8, "safety": 8}
    }
  ]
}
```

若某条技能无法评测，返回 `"status": "failed"` 并设 `error_message`。

---

## 严格要求

### 必须遵守

- 每条技能的 baseline 和 with-skill 由**不同子 agent** 执行
- `status="completed"` 要求每个任务都有**非空** `baseline_output` 和 `with_skill_output`（真实执行输出）
- `status="completed"` 要求每个任务有 `baseline_evidence.session_id` 和 `with_skill_evidence.session_id`，且两者**不同**
- 新增 `dispatch_evidence` 字段，证明编排者未自行执行任务
- 至少完成一个技能的完整三阶段流程再提交

### 禁止行为

- ❌ 编排者自己执行测试任务（你只做准备和评分）
- ❌ 在 baseline 子 agent 的 prompt 中泄露技能内容
- ❌ 在同一个子 agent 中先做 baseline 再做 with-skill
- ❌ 使用"假设""模拟""推测""hypothetical""simulated"等表述作为完成依据
- ❌ 修改子 agent 返回的原始输出后再评分
- ❌ 只做阶段一就结束（必须完成阶段二的派发执行）
- ❌ 主动把 batch 中技能 A 的评测上下文带入技能 B 的评测

### 最终输出

- 回复中**只输出一个 JSON 数组**
- 若必须用代码块，标明 `results` 并只放该数组
