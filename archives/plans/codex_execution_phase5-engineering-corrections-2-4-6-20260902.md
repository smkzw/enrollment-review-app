# Codex Execution Plan: phase5-engineering-corrections-2-4-6-20260902

Objective: 按2026-09-01工程纠偏清单，以Ponytail最小改动完成生产依赖归位、方案语义传输中性命名、方案PDF入口下线及主仓旧前端副本清理，并保持受试者证据PDF路径不变

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 将openai与pymupdf从dev依赖移入主依赖，更新锁文件，并验证uv sync --no-dev环境可导入生产路径依赖 | `runs/execution/phase5-engineering-corrections-2-4-6-20260902/worker_01.md` |
| `worker_02` | 将deepseek_protocol_transport.py更名为中性protocol_semantic_transport.py，提供最小兼容迁移并更新生产引用和测试 | `runs/execution/phase5-engineering-corrections-2-4-6-20260902/worker_02.md` |
| `worker_03` | 仅下线研究方案PDF上传与结构分派入口，删除方案侧pdf_structure公开入口和相关测试，保持受试者证据PDF处理不变 | `runs/execution/phase5-engineering-corrections-2-4-6-20260902/worker_03.md` |
| `worker_04` | 核对并删除主检出目录中明确列入纠偏清单的两个未跟踪旧前端API副本，记录worktree设计书与实施计划为权威版本 | `runs/execution/phase5-engineering-corrections-2-4-6-20260902/worker_04.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
