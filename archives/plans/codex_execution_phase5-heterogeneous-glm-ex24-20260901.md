# Codex Execution Plan: phase5-heterogeneous-glm-ex24-20260901

Objective: 以项目无关结构距离选择的只读 D001 EX-24 为异质规则样本，运行产品内置 GLM-5.3-Flash high 整候选并由当前生产门禁与 Codex 临床复核验收；严禁恢复 D001 第20包、修改冻结输入、跨提供方拼接或写入项目特异共享规则。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审计 parent-rule-selection-v2.json、冻结合同、来源包哈希和共享选择器反过拟合边界，确认 EX-24 是结构距离与最低挑战度共同选择的结果。 | `runs/execution/phase5-heterogeneous-glm-ex24-20260901/worker_01.md` |
| `worker_02` | 运行 heterogeneous-glm-ex24-20260901/run_heterogeneous_glm.py，以 zhipu-coding-plan/glm-5.3-flash:high 完成一次隔离整候选，保留模型身份、原始响应、时延、完整门禁和前后哈希。 | `runs/execution/phase5-heterogeneous-glm-ex24-20260901/worker_02.md` |
| `worker_03` | 在新候选落盘后独立重放当前完整门禁，逐字核对开放列举、例外作用域、来源闭包、复核阶段和跨项目硬编码风险，不把模型自报或旧门禁结果当验收。 | `runs/execution/phase5-heterogeneous-glm-ex24-20260901/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
