# SkillProbe Product Requirements

## 项目目标

构建一个针对 AI coding agent 的 skills 效果评估系统，能够对任意 skill 进行能力画像、测试任务生成、A/B 对比实验、自动评分、归因分析、评测报告生成、改进建议输出。

## 系统必须回答的 8 个问题

1. 这个 skill 想解决什么问题？
2. 应该用什么任务来测试它？
3. 不启用它时，agent 表现如何？
4. 启用它后，agent 表现如何？
5. 提升发生在哪些子维度？
6. 是否有退化、幻觉、过度约束、额外成本？
7. 提升是否真的是这个 skill 带来的？
8. 下一步该优化 skill 的哪一部分？

## 核心对象模型

### SkillProfile
描述 skill 是什么：名称、描述、目标问题域、触发条件、输入输出特征、依赖工具、适用边界。

### EvalSpec
描述怎么测：任务域、测试目标、测试集来源、baseline 配置、with-skill 配置、指标集合、打分权重、成功/失败定义、终止条件。

### TaskSet / Task
描述测什么：task_id、task_type、prompt、context、expected_artifacts、scoring_hints、difficulty、risk_level。

### EvalRun
描述跑了什么：运行配置、任务结果、轨迹记录、工具调用、耗时、token 用量、skill 触发事件。

### EvalReport
描述结论是什么：总体对比、分维度评分、归因分析、推荐结论、改进建议。

## 功能模块

### A. Skill Ingestion（skill 导入与画像）
- 输入：本地 skill 目录 / git repo
- 输出：SkillProfile JSON
- 解析 SKILL.md 和配套文件，提取结构化元数据

### B. EvalSpec Generator（评测计划生成）
- 输入：SkillProfile
- 输出：EvalSpec
- 根据 skill 目标推断任务类型，生成评测计划

### C. Task Generator（任务生成器）
- 输入：SkillProfile + EvalSpec
- 输出：TaskSet (JSONL)
- 支持模板生成、LLM 扩写、混合数据集
- 覆盖正常/边界/歧义/失败诱发样本

### D. A/B Runner（对比实验执行器）
- Run A：不启用目标 skill
- Run B：启用目标 skill
- 控制变量：同一底模、温度、工具权限、时间限制、系统提示
- 记录：最终输出、中间思考、工具调用、文件产出、耗时、token、错误、skill 触发情况

### E. Scoring Engine（评分引擎）
三层评分：
1. 规则评分：硬指标（工具调用、结构校验、字段完整性）
2. 结果评分：客观结果（正确性、完整率、测试通过率）
3. LLM Judge 评分：软指标（推理质量、专业性、清晰度）

### F. Attribution Engine（归因引擎）
分析维度：
1. 触发归因：skill 是否真实被用到
2. 步骤归因：是否改变了任务分解路径
3. 工具归因：是否引导了更合适的工具使用
4. 格式归因：是否仅改善了表达风格
5. 副作用归因：是否增加冗余步骤/幻觉

### G. Report Generator（报告生成器）
输出标准化报告：实验概览、skill 画像、任务集说明、对比分析、归因分析、综合评分、推荐结论、优化建议。

结论标签：Recommended / Conditionally Recommended / Not Recommended / Needs Revision / Inconclusive

### H. Improvement Advisor（改进建议器）
基于评测结果生成：prompt 修改建议、examples 补充建议、触发条件修改建议、结构化 candidate patch、回归测试计划。

## 核心成功指标

- 单个 skill 评测流程可完整跑通
- 产出结构化报告
- 能区分"有效提升"和"无效复杂化"
- 能发现至少 3 类退化模式
- 能形成针对 skill 的明确改进建议
