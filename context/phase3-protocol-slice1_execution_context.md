# Execution Context: phase3-protocol-slice1

Created: 2026-08-14 12:14:52
Objective: 实现Phase 3切片1：可追溯方案文档结构提取、渲染派生物、来源定位契约与真实方案验证
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `pi` / `opencode-go` / `deepseek-v4-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- Architecture and acceptance contract: `.trellis/tasks/08-14-phase3-protocol-deconstruction/{prd.md,design.md,implement.md,research.md}`.
- Existing V2 domain/storage baseline: `app/domain/contracts/`, `app/storage/`, and `tests/v2/`.
- Read-only MG-K10-SAR protocol: `/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx`.
- Read-only D001 protocol: `/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx`.
- The two protocol files may be read, hashed, and rendered only into disposable V2 test output. They must never be modified, renamed, moved, or used as an application write target.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 新增方案来源、结构快照、渲染派生物和来源片段领域契约及SQLite迁移
2. 实现DOCX结构提取、受控LibreOffice渲染manifest和结构到渲染页对齐
3. 用MG-K10-SAR与D001做候选对比、真实只读回归、迁移回滚和契约测试

## Codex Review Findings Before Work Item 2

- Worker 1 output is provisional until Codex accepts it. Work item 2 may refine the Phase 3 ingestion contracts, ORM, and migration when the extractor proves a missing structural invariant.
- An extraction snapshot must preserve a verifiable complete-content artifact or canonical block set plus hash and storage reference; counts alone cannot prove an excerpt belongs to that file hash.
- A source locator must represent nested table paths, not only one row/column pair.
- Content-identical source artifacts must deduplicate by SHA-256; a separate upload/job record may preserve repeated user actions later.
- Degraded or failed rendering must retain a structured reason. Exact excerpts must be verifiable against the extraction snapshot.
- Do not install Docling into the project by default. Any candidate spike must stay isolated and be removed if it has no decisive advantage over python-docx/OOXML plus LibreOffice.

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
