# Execution Metrics: phase5-cross-protocol-glm-acceptance-20260901

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `cursor` | `default` | completed | 约 5 分钟 | 文件/哈希只读核对 | 确认冻结边界；指出选样规范需由 Codex裁定 |
| `worker_02` | `cursor` | `default` | completed | 约 18 分钟 | 产品运行器；GLM 2 次调用 | EX-18 候选落盘；模型调用 585.89 秒 |
| `worker_03` | `cursor` | `default` | completed, stale | 约 6 分钟 | 门禁重放与代码扫描 | 结束早于新候选落盘，不用于最终验收 |

## Codex 验收指标

- GLM 调用：2 次，同一会话；488.765 秒 + 97.076 秒。
- 候选规模：1 条父规则、8 个组件、8 项筛选期资料要求、0 项基线资料要求。
- 来源闭包：9/9 个引用均在冻结允许来源内。
- 当前门禁：12 项检查中时间语义检查失败；8 个缺少基线最终复核的问题。
- 聚焦回归：169 passed。
