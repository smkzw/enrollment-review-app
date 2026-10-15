# Codex Execution Plan: phase5-mtplx-whole-candidate-comparison-20260901

Objective: 在同一冻结 EX-06 输入上运行完全隔离的 MTPLX 整候选，复用生产方案解构合同与完整门禁，记录时效、调用、来源闭包和问题分类；禁止跨模型拼接，禁止恢复 D001。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读核对冻结输入、GLM 负向证据与生产 MTPLX 传输合同，提出最小整候选验收入口和不可变性检查。 | `runs/execution/phase5-mtplx-whole-candidate-comparison-20260901/worker_01.md` |
| `worker_02` | 实现或复用隔离 MTPLX 整候选验收脚本，完成短连通性预检、真实调用、调用台账和完整门禁；只允许写入新验收目录。 | `runs/execution/phase5-mtplx-whole-candidate-comparison-20260901/worker_02.md` |
| `worker_03` | 独立设计并运行确定性核验，检查来源闭包、候选隔离、门禁问题分类、冻结哈希和 D001 暂停边界，拒绝以 API 成功代替语义质量。 | `runs/execution/phase5-mtplx-whole-candidate-comparison-20260901/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

- 冻结输入 SHA-256 与合同一致，D001 仍停在第 19 包后。
- MTPLX 整候选已完成真实调用；模型身份正确，未分段、未跨供应商拼接。
- MTPLX 用时 1082.56 秒，生产门禁重放仍有 12 个阻断问题，不接受为语义结果。
- 同源 GLM、MTPLX、DeepSeek 候选均由当前生产门禁离线重放；证据完整性通过，但无候选可发布。
- 执行者报告仅作过程证据；最终结论以 Codex 重放、聚焦回归和路由审计为准。
