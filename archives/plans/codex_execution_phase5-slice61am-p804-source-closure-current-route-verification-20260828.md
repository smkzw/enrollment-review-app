# Codex Execution Plan: phase5-slice61am-p804-source-closure-current-route-verification-20260828

Objective: 在不修改临床工件、不运行语义模型、不发布控制点的前提下，使用最新执行路线独立验收 p804 同源来源闭包修订合同、主线程 runner 路径补漏及真实 v8 离线边界；确认它是通用合同且没有把工程通过误写为临床通过。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读核查共享实现：追踪 CONDITIONAL_EXEMPTION_SCOPE_SPLIT 从发布门禁、修订错误映射、runner 授权到 bounded restore/validate 的完整路径；重点验证 source closure 与 atom-level obligation span 互斥、闭包外来源冻结及无 D001 特异硬编码。 | `runs/execution/phase5-slice61am-p804-source-closure-current-route-verification-20260828/worker_01.md` |
| `worker_02` | 独立检查聚焦测试与完整协议层回归：运行明确的确定性测试，审查新增测试是否真实经过 runner 路径并覆盖合并、拆分、跨来源吸收、来源丢失、乱序和失败关闭；不得以测试数量替代断言质量。 | `runs/execution/phase5-slice61am-p804-source-closure-current-route-verification-20260828/worker_02.md` |
| `worker_03` | 只读复核真实 v8 A4/A5 离线来源闭包恢复证据：确认 p805 越界变化被恢复、p804 仍未被旧响应正确闭合，明确工程合同可用与临床内容仍拒绝的边界，并给出是否具备进入独立会商的证据判断。 | `runs/execution/phase5-slice61am-p804-source-closure-current-route-verification-20260828/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
