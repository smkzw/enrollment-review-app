# Codex Execution Plan: phase5-slice57-recompute-ui-latest-route

Objective: 在已验收的事实修订合同与仓储上完成 Slice 5.7 剩余工作：确定性影响范围、持久增量重算服务/API及中文宽屏修订界面，并覆盖重启、取消、迟到回包、重复回调和局部失败；不进入入排结论。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 影响范围：沿定位、文档、事实引用、规则索引和历史Profile反向索引证明局部闭包，无法证明时明确回退整个审核节点。 | `runs/execution/phase5-slice57-recompute-ui-latest-route/worker_01.md` |
| `worker_02` | 执行与接口：基于持久Job/Step/Checkpoint/Lease/PreparedStepResult原子生成新实体、修订记录和新Profile，覆盖恢复、取消、迟到结果、重复回调与局部失败。 | `runs/execution/phase5-slice57-recompute-ui-latest-route/worker_02.md` |
| `worker_03` | 用户界面：在Patient Profile提供中文原生事实修订预览、理由、来源、影响范围和历史回看，并完成宽屏浏览器验证。 | `runs/execution/phase5-slice57-recompute-ui-latest-route/worker_03.md` |

依赖顺序固定为 `worker_01 -> Codex 聚焦验收 -> worker_02 -> Codex 聚焦验收 -> worker_03`。不得并行开发尚未冻结的接口，也不得把 Phase 5.8 的独立测试者当作执行者。

## Implementation Contract

- 修订是追加式领域事件，不是 SQL `UPDATE`；原 OCR、候选、旧实体和旧 Profile 永不覆盖。
- 局部影响范围必须由显式反向索引闭包证明；只要任一必要链断裂，就向用户显示“将重新整理本审核节点全部事实”并使用节点级范围。
- 新实体、修订记录、新 Profile 与任务检查点必须在租约写栅栏内原子提交。失败或取消时上一活动 Profile 不变。
- 前端使用“修订事实记录”“核对原文”“重新整理受影响信息”等中文临床工作语句，不使用“修正 AI”“覆盖结果”、后端枚举或入排主结论。

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

Codex 逐工作项复核真实 diff、合同、迁移和故障语义，运行聚焦测试后才放行下一项。终局要求后端全量、前端全量/构建、最大化 1080P/2K/4K Playwright、真实浏览器视觉检查、取消/恢复/迟到提交故障注入、`git diff --check`、Trellis validate 和执行工作流 audit。可视化执行完成后另建可视化会商验收；Phase 5.8 测试者仍不启动。
