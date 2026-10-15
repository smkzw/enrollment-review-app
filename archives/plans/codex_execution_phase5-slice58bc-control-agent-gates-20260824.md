# Codex Execution Plan: phase5-slice58bc-control-agent-gates-20260824

Objective: 实现全方案结构单元逐项处置、其他方案控制候选语义解构、跨章节关系与发布停止门禁；保持官方IN/EX和流程必做项身份不变，不接触真实项目写路径。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 新增处置批次、候选语义草稿与系统水合所需领域合同，并实现按标题路径和来源闭包确定性分批的规划器。 | `runs/execution/phase5-slice58bc-control-agent-gates-20260824/worker_01.md` |
| `worker_02` | 实现其他方案控制专用的严格结构化Agent输入输出、中文提示词、无引用wire水合与同会话定向修复，不复用官方IN/EX成员合同。 | `runs/execution/phase5-slice58bc-control-agent-gates-20260824/worker_02.md` |
| `worker_03` | 实现全文处置完整性、来源闭包、期别、节点作用、时间锚点、义务AND/OR、跨来源关系与冲突停止门禁，并补充反例和真实D001只读对照测试。 | `runs/execution/phase5-slice58bc-control-agent-gates-20260824/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

Run workers serially. After each worker, inspect actual diffs and focused tests before dispatching its dependent. Final acceptance requires focused tests, complete `tests/v2/protocols`, compileall, diff check, Trellis validation, execution audit and review gate. No rendered/browser claim is in scope because this module has no UI change.
