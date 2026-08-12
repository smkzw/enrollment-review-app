# Error Handling

> V2 后端错误必须可恢复、可审计，并以医学监查员能理解的中文呈现。

## Overview

- 领域失败、输入无效、外部模型失败和系统故障必须分层处理，不得混成一个“审核失败”。
- LLM/Agent 输出只是候选结果；解析失败、字段缺失或语义冲突必须进入校验或重试，不能默认成“通过”。
- 后端保留技术诊断信息，前端默认只展示问题、影响和下一步操作，不展示堆栈、供应商原文或内部代码。
- 批量任务允许单个受试者失败后继续处理其他受试者，并在 Job 中保留失败节点和可重试范围。

## Error Types

| 类型 | 示例 | 处理原则 |
|---|---|---|
| `DomainError` | 方案版本不匹配、审核阶段缺少锚点日期 | 返回明确的中文修正动作，不写入错误结论 |
| `ValidationError` | RuleExpression 或 EvidenceSpan 不符合契约 | 拒绝候选结果，记录校验问题，必要时重试 Agent |
| `ConflictError` | 乐观锁版本过期、人工 override 与新任务并发 | 不覆盖新数据，返回最新 revision 和冲突范围 |
| `DependencyError` | OCR、LLM、文件解析器暂时不可用 | 保留 Job 检查点，限定节点重试 |
| `NotFoundError` | 项目、受试者、证据定位不存在 | 返回用户可理解的资源名称和返回路径 |
| `InfrastructureError` | 数据库、文件系统、未预期异常 | 记录关联 ID，前端提示稍后重试或检查本机服务 |

## Error Handling Patterns

1. API 层只负责协议转换，不在路由里吞异常或推导临床结论。
2. Domain/Workflow 层抛出有稳定语义的错误；Storage/Agent 适配器把第三方异常转换为项目错误类型。
3. 仅在能够恢复或补充上下文时捕获异常；禁止 `except Exception: pass` 和空结果兜底。
4. Agent 响应先做结构校验、规则完整性校验和语义一致性检查，再进入确定性评估器。
5. Job 节点失败必须记录 `retryable`、失败范围、上次成功检查点和建议操作；重试应幂等。
6. 任何异常都不得把“不通过”“证据不足”或“需研究者判定”静默改成“通过”。

## API Error Responses

V2 API 使用稳定错误信封：

```json
{
  "error": {
    "code": "ANCHOR_DATE_REQUIRED",
    "title": "缺少基线日期",
    "detail": "该条款按随机前时间窗判断，目前没有可用的基线日期。",
    "recovery_action": "选择计划基线日期后重新评估该阶段。",
    "correlation_id": "..."
  }
}
```

- `code` 供程序和测试使用，用户界面不默认显示。
- `title`、`detail`、`recovery_action` 必须是自然中文，避免“schema”“pipeline”“provider”等技术词。
- 证据相关错误可附资源 ID 和页面定位，但不得泄露本机绝对路径。

## Common Mistakes

- 根据理由文本中的关键词事后修正判定，而不是修复结构化逻辑和确定性评估器。
- 把模型响应缺少条目当作该条目通过。
- 把单个文件 OCR 失败升级成整个批次失败，或整批重跑已成功节点。
- 在 UI 中展示原始异常、日志式指令或模型供应商错误。
- 捕获乐观锁冲突后直接覆盖当前版本。
