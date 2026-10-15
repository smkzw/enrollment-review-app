# Codex Execution Plan: phase5-slice58p-mixed-paragraph-atomization-20260826

Objective: 通用、可回源地拆解期别混合的方案复合段落，保留共享筛选/基线控制并隔离期别专属安排，在真实 D001 II 重建与确定性回归后更新 Phase 5.8d 持久记录。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 实现工作：只修改协议结构/全文清单相关后端模块，复用现有结构和来源合同，实现非项目特异的复合段落原子化，保持稳定身份、原文片段和来源范围。 | `runs/execution/phase5-slice58p-mixed-paragraph-atomization-20260826/worker_01.md` |
| `worker_02` | 测试工作：只修改 tests/v2/protocols 下相关测试，覆盖共享控制、II/III 专属安排、混合句、来源回放、确定性身份和不重复计数。 | `runs/execution/phase5-slice58p-mixed-paragraph-atomization-20260826/worker_02.md` |
| `worker_03` | 验证与记录工作：只在新 artifacts 目录和 Phase 5.8d 任务记录中生成真实 D001 II 重建、package 79 复核、差异/QC 与恢复检查点，不修改临床源文件，不启动受试者或浏览器测试。 | `runs/execution/phase5-slice58p-mixed-paragraph-atomization-20260826/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
