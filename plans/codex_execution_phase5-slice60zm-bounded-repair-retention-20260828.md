# Codex Execution Plan: phase5-slice60zm-bounded-repair-retention-20260828

Objective: 基于D001第68包v7-v9保存响应与当前ProtocolControlAgentRunner，定位按结构单元修订授权仍会丢失正确语义的根因，设计可复用、失效关闭、不可泄露金标准的候选/处置细粒度修订状态保留机制；本轮先做独立分析和实现建议，不调用真实模型，不运行受试者、OCR、浏览器或视觉测试。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 独立只读核对v7-v9每次保存响应和attempt记录，形成候选、处置及字段级漂移表，说明现有mutable_structure_unit_ids为何无法保护已正确内容，并给出可复现的最小反例。 | `runs/execution/phase5-slice60zm-bounded-repair-retention-20260828/worker_01.md` |
| `worker_02` | 独立审阅ProtocolControlAgentRunner、wire身份推导、修订错误范围和restore逻辑，设计最小通用候选/处置保留合同，重点处理跨多个来源单元候选、候选拆分/合并、schema失败无可水合基线及稳定身份问题。 | `runs/execution/phase5-slice60zm-bounded-repair-retention-20260828/worker_02.md` |
| `worker_03` | 独立设计确定性回归与验收边界：哪些字段允许局部替换、哪些必须原样保留、何时拒绝自动合并并转需核对，以及如何用保存响应离线验证而不把临床金标准注入Agent。 | `runs/execution/phase5-slice60zm-bounded-repair-retention-20260828/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
