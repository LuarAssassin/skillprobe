# SkillProbe Vision

## 一句话

A/B 评估 AI agent skills 的真实效果，基于评测结果驱动 skills 持续改进。

## 问题

当前 AI agent skill 生态存在一个根本缺口：**没有效果层**。

现有工具链覆盖了 skill 的发布、版本管理、搜索、安装，但没有人回答：
- 这个 skill 装了以后到底有没有用？
- 提升发生在哪些任务上？
- 有没有副作用？
- 值不值得保留？
- 怎么基于数据改进它？

## 解法

SkillProbe 是一个离线 A/B 评测引擎，针对任意 skill 执行：

1. 能力画像提取
2. 评测计划自动生成
3. 测试任务自动生成
4. baseline vs with-skill 对比实验
5. 三层混合评分（规则 + 结果 + LLM Judge）
6. 归因分析
7. 结构化报告输出
8. 改进建议生成

## 不做什么

- 不做合规审查主平台
- 不做 skill marketplace
- 不做生产环境在线流量实验
- 不做全自动无监督 skill 替换
- 不做大规模 registry 全量评测（v1）

## 目标用户

1. 将社区 skill 接入自家 agent 的团队
2. OpenClaw / NanoClaw / coding agent 使用者
3. Skill 作者
4. Skill registry 运营方

## 核心价值主张

让社区 skills 从"拍脑袋接入"变成"可量化准入、可归因分析、可持续进化"。

## v1 聚焦场景

评估 OpenClaw-Medical-Skills 中 1~3 个医学 skill，对医疗 research/问答/摘要任务是否有增益。

推荐首批任务类型：
1. 医学文献检索与证据摘要
2. 临床问题问答
3. 医疗文本结构化摘要
