# Codex Execution Plan: phase5-sar31001-real-acceptance-20260901

Objective: 在不恢复D001旧任务、不修改原始临床资料且不引入项目特异共享规则的前提下，准备SAR 31001新隔离输入并给主线程提供可执行的V2单例真实验收依据。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读梳理当前V2应用从原始SAR方案DOCX创建III期项目、导入单例资料、冻结修订、运行事实规范化与读取Patient Profile的实际API和服务启动顺序；输出精确命令与失败信号，不修改文件。 | `runs/execution/phase5-sar31001-real-acceptance-20260901/worker_01.md` |
| `worker_02` | 仅使用现有phase5_acceptance输入清单工具，从SAR 31001原始目录创建20260901全新隔离副本与可验证清单；不得修改原始资料、不得复用旧验收产物、不得启动D001或模型服务。 | `runs/execution/phase5-sar31001-real-acceptance-20260901/worker_02.md` |
| `worker_03` | 只读审查代表受试者真实验收所需的输出、发布权威链、逐事件来源定位、时间轴风险标记和旧运行污染门禁；给出主线程必须验证的最小清单，不作最终医学入排结论。 | `runs/execution/phase5-sar31001-real-acceptance-20260901/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
