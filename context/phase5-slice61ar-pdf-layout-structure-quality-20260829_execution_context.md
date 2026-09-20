# Execution Context: phase5-slice61ar-pdf-layout-structure-quality-20260829

Created: 2026-08-29 07:57:12 CST
Objective: 修复原生文字型研究方案 PDF 的结构质量：在不改源文件、不写死项目规则、不破坏已验收页码/文本范围/bbox/哈希契约的前提下，区分空白页与扫描页，恢复稳定的版面阅读顺序、标题层级和表格结构，使真实 SAR/D001 方案可用于全文覆盖清单和后续控制点解构；用确定性测试与真实方案证据验收。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `night`; resolved once at packet creation in `Asia/Shanghai`.
Effective worker chain: `codebuddy-cli/glm-5.3-flash:max -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> openai-codex/gpt-5.6-luna:xhigh`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `codebuddy` / `codebuddy-cli` / `glm-5.3-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只读审计现有 pdf_native/pdf_structure、StructureBlock 契约、真实 SAR PDF/DOCX 差异和 PyMuPDF/pdfplumber 能力，提出最小通用实现方案、风险与验收矩阵；不得修改文件。
2. 实现通用 PDF 页面分类与版面结构恢复，重点处理多栏阅读顺序、表格区域/单元格、标题排版证据、空白页与扫描页分流；保留精确来源定位和失败关闭，不使用项目特异文本规则。
3. 补齐 PDF 结构质量的确定性回归测试与真实方案核验脚本/证据，覆盖双栏、表格、标题、短页、空白页、扫描/混合页、旋转页、确定性和源文件不变，并检查下游结构分发兼容性。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
