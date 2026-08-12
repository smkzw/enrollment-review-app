# 后端开发规范

## 适用范围

本规范同时描述旧系统现实和V2目标边界。`app/router/`、`app/pipeline/`与`app/models.py`属于旧实现，只允许修复旧系统运行问题；V2新增代码进入明确的领域层、工作流层、存储层、Agent适配层和投影层，不继续扩大旧Markdown审核器。

| 规范 | 内容 |
|---|---|
| [目录结构](./directory-structure.md) | 模块职责和依赖方向 |
| [数据库](./database-guidelines.md) | SQLite/WAL、迁移、事务和不可变历史 |
| [错误处理](./error-handling.md) | 用户可理解的错误与任务恢复 |
| [质量要求](./quality-guidelines.md) | 临床逻辑、证据、测试与审查 |
| [运行记录](./logging-guidelines.md) | Job/Agent审计与敏感信息边界 |

## 开发前检查

1. 阅读当前Trellis任务的 `prd.md`、`design.md`、`implement.md`。
2. 搜索现有实体、状态、常量和相似逻辑，不复制旧正则补丁。
3. 明确本次变化属于语义Agent、确定性计算、持久状态还是用户投影。
4. 列出证据来源、可回滚点和会受影响的ReviewRun/投影。

## 完成检查

- 结构化合同和迁移通过；
- 临床判断可回到EvidenceSpan；
- 不用LLM自由文本决定逻辑、阈值、汇总或行动转移；
- 失败和部分完成不会伪装为成功；
- 相关单元、属性、回归和真实流程检查完成。
