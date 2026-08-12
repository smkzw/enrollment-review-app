# Logging Guidelines

> 运行日志用于本机诊断；临床证据、审核轨迹和任务状态使用结构化业务记录保存。

## Overview

- Python 服务沿用标准 `logging`，逐步统一为结构化字段；不得用 `print` 充当持久日志。
- `JobEvent`、`AgentCall`、`PromptVersion`、人工 override 和证据引用属于数据库审计记录，不属于普通文本日志。
- 日志不是前端数据源。用户看到的是任务状态、失败原因和恢复动作，而不是技术日志。
- 所有长任务用稳定的 `job_id`、`node_id`、`correlation_id` 串联 OCR、Agent、评估和报告步骤。

## Log Levels

- `DEBUG`：本地开发诊断、候选数量、分支选择；默认关闭，不记录临床原文。
- `INFO`：服务启动、Job/节点状态变化、重试、版本加载、迁移完成。
- `WARNING`：可恢复的 OCR/Agent 失败、契约拒绝、证据定位降级、过期结果被拒绝。
- `ERROR`：节点最终失败、数据持久化失败、无法恢复的契约或基础设施错误；必须带异常堆栈和关联 ID。

## Structured Logging

每条重要日志尽量包含：

```text
timestamp, level, event, correlation_id, job_id, node_id,
project_id, subject_id(可脱敏), episode_id, revision,
model_id, prompt_version, schema_version, duration_ms, retry_count, status
```

- `model_id`、提示词和 schema 记录哈希或版本号，不把完整提示词重复写进日志。
- 供应商用量、耗时和错误分类进入 `AgentCall`；临床原文仍保存在受控证据记录中。
- 日志文件轮转并限制保留，不能继续无界增长。

## What to Log

- 实际 Python/Node 运行时版本、服务端口和迁移版本。
- Job 创建、节点开始/完成/失败/重试/取消及检查点。
- OCR 页数、成功/失败页、质量指标和定位能力等级。
- Agent 请求的模型、参数、PromptVersion、SchemaVersion、耗时、用量和校验结果。
- 确定性 gate 的规则数量、冲突数量、rollup 状态及 stale 范围。
- 人工 override 的操作者、时间、原状态、新状态、理由和被替代 revision。

## What NOT to Log

- API key、令牌、环境变量值和认证头。
- 完整病历、受试者姓名、身份证号、电话、住址或整页 OCR 文本。
- 完整方案、附件内容和本机绝对临床资料路径。
- 完整 LLM 提示词或响应；只存受控的 AgentCall 关联、版本和必要摘要。
- 把“通过/不通过”作为自由文本日志后再由前端解析。
