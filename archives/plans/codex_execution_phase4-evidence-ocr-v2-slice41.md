# Codex Execution Plan: phase4-evidence-ocr-v2-slice41

Objective: 按已批准Phase 4计划完成Slice 4.1：证据快照领域合同、仓储、0008迁移及受试者/审核节点基础API，并以确定性测试证明作用域与不可变性

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 冻结受试者、审核节点、来源对象、逻辑资料版本、元数据修订、证据快照及成员合同 | `runs/execution/phase4-evidence-ocr-v2-slice41/worker_01.md` |
| `worker_02` | 实现证据快照仓储、作用域门禁、前序链无环、显式替代、集合哈希与重复集合no-op | `runs/execution/phase4-evidence-ocr-v2-slice41/worker_02.md` |
| `worker_03` | 实施0008迁移及升降级/备份测试，并补齐受试者与审核节点基础API和合同测试 | `runs/execution/phase4-evidence-ocr-v2-slice41/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

2026-08-19：三个顺序工作项均完成。Codex 在检查者修订前独立运行 V2 全量回归，结果为
`900 passed, 58 warnings, 2 subtests passed`，并验证目标文件 Ruff 与 `git diff --check`。
随后新鲜独立 `gpt-5.6-luna:max` 检查者修复不可变事件/成员解码、并发去重、迁移降级保护和
API 作用域问题，终局报告为 `914 passed, 58 warnings, 2 subtests`、目标 Ruff 通过、限定
Pyright 0 error、编译及 `git diff --check` 通过。检查者拥有本切片放行权，裁决为接受。

本次暂停没有在检查者修订后由 Codex 再次重跑 914 项全量测试；恢复 Slice 4.2 前先做一次
目标回归和全量 V2 复测，确认工作树未漂移。尚未实现上传、正式 OCR 持久化、处理修订激活或回滚。
