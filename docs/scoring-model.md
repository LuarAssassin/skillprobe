# SkillProbe Scoring Model

## 总体设计

100 分制，6 个一级维度，三层评分方法混合。

## 一级维度

### 1. Effectiveness 效果分（30 分）
- 任务完成率 (completion_rate)
- 正确性 (correctness)
- 关键目标命中率 (key_objective_hit_rate)

### 2. Quality 质量分（20 分）
- 输出专业性 (professionalism)
- 清晰性 (clarity)
- 结构化程度 (structure)
- 推理充分性 (reasoning_depth)

### 3. Efficiency 效率分（15 分）
- 平均耗时 (avg_duration_ms)
- Token 成本 (token_cost)
- 工具调用开销 (tool_call_overhead)

### 4. Stability 稳定性分（15 分）
- 多次运行波动 (variance)
- 异常输入抗性 (edge_case_resilience)
- 边界任务表现 (boundary_performance)

### 5. Trigger Fitness 触发适配分（10 分）
- 该触发时是否触发 (true_positive_rate)
- 不该触发时是否克制 (true_negative_rate)
- 触发后是否真正产生帮助 (trigger_utility)

### 6. Safety 副作用分（10 分）
- 幻觉增加 (hallucination_delta)
- 冗长化 (verbosity_delta)
- 误导性建议 (misleading_rate)
- 与现有 system prompt 冲突 (conflict_rate)

## 三层评分方法

### Layer 1: 规则评分 (Rule-based)
适用于硬指标，无需 LLM 参与：
- 是否调用特定工具
- 是否生成指定结构
- 是否包含关键字段
- 是否通过 schema 校验
- 文件是否成功输出

### Layer 2: 结果评分 (Result-based)
适用于客观可验证的结果：
- 答案正确性（与参考答案比对）
- 信息提取完整率
- 命中率 / 召回率
- 单元测试通过率

### Layer 3: LLM Judge 评分
适用于软指标，需要 LLM 判断：
- 推理质量
- 任务完成度
- 专业性
- 清晰度
- A vs B 偏好比较

### 聚合策略

```
task_score = Σ(dimension_weight * dimension_score) for each dimension
eval_score = mean(task_scores)  # 可选 trimmed mean 去极值
```

## 派生指标

### Net Gain（净增益）
```
net_gain = eval_score(with_skill) - eval_score(baseline)
```

### Value Index（价值指数）
```
value_index = net_gain / extra_cost
extra_cost = (avg_tokens_with - avg_tokens_baseline) * token_price
           + (avg_time_with - avg_time_baseline) * time_weight
```

## 结论标签

| 标签 | 条件 |
|------|------|
| Recommended | net_gain >= 8, 无显著退化 |
| Conditionally Recommended | net_gain >= 3, 部分任务类型有退化 |
| Not Recommended | net_gain < 0 或显著副作用 |
| Needs Revision | 有潜力但当前版本问题明显 |
| Inconclusive | 数据不足或波动过大 |

## 报告输出格式

不要只说"这个 skill 72 分"。

要说：
> 这个 skill 总分 72，净增益 +9，价值指数中等。
> 适合文献检索和药物研究任务，不适合临床摘要任务。
> 主要提升来自工具调用引导（+12），主要退化来自冗长化（-3）。
