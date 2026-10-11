# Execution Context: phase4-evidence-ocr-v2-slice42

Created: 2026-08-19 14:32:33
Objective: 完成Phase 4 Slice 4.2：受试者审核节点范围内的补充资料/完整资料快照上传预览、确认幂等、候选快照与持久任务，以及康哲site宽屏证据工作台骨架
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `pi` / `cms-smk` / `deepseek-v4-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `AGENTS.md`、`.trellis/tasks/08-19-phase4-evidence-ocr-v2/{prd.md,design.md,implement.md}`。
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`、`plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`。
- `.trellis/spec/backend/`、`.trellis/spec/frontend/`、`.trellis/spec/guides/`。
- 康哲设计 `site` 轨：`/Users/smkzw/.cc-switch/skills/kangzhe-design/design_specs/{ROUTER.md,core.md,track_site.md}`；现有 React/Vite 产品继续使用框架，但品牌、排版、交互和验收合同必须遵守该轨。
- Slice 4.0/4.1 已验收代码、测试与 `CHECKPOINT_20260819_SLICE41_PAUSED.md`。不得回改 `0008_evidence_ingestion`；上传预览使用追加迁移 `0008a_evidence_upload_previews`。
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.
- 不读取或写入仓库外真实临床资料；只使用合成测试文件和清洁测试数据库。
- 不实现 OCR、EvidenceProcessingRevision、ActivationEvent、临床事实、Patient Profile 或入排判断。
- 不安装新依赖；优先复用现有 FastAPI、SQLite/Alembic、持久 Job、React/Vite 和运行时解码模式。
- 用户确认前不得创建正式快照或 Job；取消必须清理暂存文件。确认必须在同一事务创建或复用候选快照、初始 Job、幂等记录和确认记录。
- 全量上传不继承旧成员；补充资料从上一有效快照继承。后续节点不得改写早期节点，跨项目/受试者/审核节点一律拒绝。
- 右侧原始资料区此 Slice 只建连续页容器骨架；没有真实页产物/坐标时必须明确等待处理且不得画红框。

## Work Items

1. 实现上传预览领域合同、0008a迁移、暂存文件指纹/格式探测、差异分类、取消清理、补充/完整集合计算及确认事务服务，并建立确定性迁移/服务测试
2. 实现上传预览/查询/取消/确认及快照查询V2 API，连接持久Job与幂等记录，补齐中文错误信封、作用域与并发冲突API测试
3. 实现subjects evidence深链、运行时解码、补充/完整方式预览交互和三栏宽屏证据工作台骨架，按康哲site设计与中文临床语境补齐Vitest/Playwright无辅助任务测试

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
