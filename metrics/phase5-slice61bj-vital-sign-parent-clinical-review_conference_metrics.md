# Conference Metrics: phase5-slice61bj-vital-sign-parent-clinical-review

| Role | Requested route | Effective route | Status | Session |
|---|---|---|---|---|
| `general_single_object` | `cms-router/minimax-m3:xhigh` | `opencode-go/muse-spark-1.2-contributor:xhigh` | completed_fallback | `01a04dcf-d305-7000-97f8-626aead20bd1` |

主路由在真实会话前因目录选择器大小写不匹配被预检拒绝；守卫按冻结回退链完成一轮只读审阅。Codex独立核验并处置了参与者推断，没有把参与者意见直接当成验收结论。

Date: 2026-08-29

| Role | Provider | Model | Status | Duration | API calls | Tokens | Result |
|---|---|---|---|---:|---:|---:|---|
| `general_single_object` | `opencode-go` | `muse-spark-1.2-contributor` | completed_fallback | 126.269s controller wall | 1 successful session | ~4,798 output | accepted after Codex resolution |

## Timeout And Retry Evidence

主路由健康预检返回模型目录身份大小写不匹配，未建立可恢复会话；守卫仅执行一次声明回退。回退会话正常终止，无超时、无重复派发、无同会话补写。

## Quality Decision

参与者报告提供有效挑战，但不拥有父级临床验收权。Codex采纳建议强度、双节点、治疗期隔离和不重复发布意见，拒绝把四类生命体征拆成五类检查及把恢复归因于未发生的服务环境修改。
