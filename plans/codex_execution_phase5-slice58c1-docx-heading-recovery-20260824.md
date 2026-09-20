# Codex Execution Plan: phase5-slice58c1-docx-heading-recovery-20260824

Objective: 恢复DOCX自定义中文标题样式与层级，使全文方案控制清单保留真实上位章节证据，并以D001只读复测区分结构性假未知和真正期别语义不确定。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 扩展DOCX结构块及提取器，解析styles.xml中的样式名和可继承outline level，保持旧构造兼容并新增通用回归。 | `runs/execution/phase5-slice58c1-docx-heading-recovery-20260824/worker_01.md` |
| `worker_02` | 让全文覆盖清单只依赖结构化outline level优先识别标题并重建标题路径、表题及表格行归属，避免把编号列表误当标题，新增反例。 | `runs/execution/phase5-slice58c1-docx-heading-recovery-20260824/worker_02.md` |
| `worker_03` | 让期别图的标题上下文使用结构化outline元数据，运行D001只读前后对照并补充通用结构回归；不得将未知默认共享或写项目特例。 | `runs/execution/phase5-slice58c1-docx-heading-recovery-20260824/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
