# Quality Guidelines

> 后端质量以临床逻辑正确、可追溯、可恢复和跨项目泛化为核心。

## Overview

V2 必须把方案事实、证据事实、候选解释、确定性判定和用户动作分开。质量门禁不能只证明流程能跑通，还要证明布尔逻辑、时间窗、单位、例外条件、证据完整性和阶段边界正确。

## Forbidden Patterns

- 在系统级代码写入特定项目、中心或受试者 ID 的修补规则。
- 让 LLM 直接产生最终总体结论、自动关闭待办或覆盖人工 override。
- 用正则或理由文本关键词修补“和/或”、实验室指标、梅毒例外等语义错误。
- 缺失条目、解析失败、冲突证据或未知值默认判为通过。
- 用 Markdown、mtime、缓存文件或单个 `overall_verdict` 作为事实源。
- API 路由直接访问多个存储实现并拼装领域结论。
- 捕获所有异常后返回成功或空数组。

## Required Patterns

- RuleExpression、EvidenceRequirement、EvidenceSpan、ReviewEpisode 和 ActionItem 均有版本化契约。
- Agent 只提出结构化候选；确定性 evaluator/gate 负责最终状态、rollup 和待办动作。
- 所有副作用节点幂等；长任务有 durable Job、检查点、重试范围和取消状态。
- 修改持久数据使用 revision/乐观锁；过期候选不能覆盖新状态。
- 证据必须指向文件、页码及可用的 bbox/text range/excerpt，定位能力降级要明确记录。
- 用户界面文案由稳定状态和结构化字段生成，不解析模型自由文本。
- 新 V2 写路径与 legacy 存储物理隔离；旧项目仅作为只读回归锚点。

## Testing Requirements

- 单元测试：领域值对象、四值逻辑、AND/OR/NOT、子规则 rollup、时间窗、单位换算、日期精度。
- 属性/变异测试：重点验证把 AND 改 OR、阈值运算符变化、未知值传播时测试必然失败。
- 契约测试：JSON Schema、API 请求/响应、Agent 输入输出、PromptVersion 与 SchemaVersion 匹配。
- 临床回归夹具：脱敏覆盖实验室不同指标、否定词、联合条件、例外条件、阶段锚点和溯源提醒。
- 恢复测试：节点重试、任务中断恢复、重复提交幂等、revision 冲突、过期结果拒绝。
- 集成测试使用系统实际运行时；当前 legacy 基线为 `/usr/bin/python3`，131 项通过、1 项跳过。

## Code Review Checklist

- 是否把临床语义放进结构契约，而不是项目特异文本规则？
- 未知、冲突和缺失是否仍保持不确定，而非被误判通过？
- Agent 是否越过 gate 直接写最终状态？
- 证据引用能否回到原文件具体位置？
- 重试、重复执行和并发修改是否幂等且不丢历史？
- 是否有针对根因的测试，并覆盖相邻共享逻辑？
- 是否在真实运行时执行测试，而非另一套缺依赖的 Python？
