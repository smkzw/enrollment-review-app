# Execution Context: phase5-slice61aq-native-pdf-structure-entry-20260829

Created: 2026-08-29 04:02:32 CST
Objective: 在不调用临床模型的前提下，为V2方案解构建立项目无关的原生文字PDF结构化入口：用户直接上传PDF后进入与DOCX相同的冻结StructureBlock/ProtocolExtractionSnapshot/来源定位链；扫描或文本层不足时失效关闭为需要核对；原PDF直接用于页面文本与定位，不伪装成DOCX结构，也不引入项目特异规则。
Task type: `finite_code_task`
Risk: `high`
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

1. 只读审计现有DOCX结构、PDF原生坐标、方案工作流与来源定位合同，给出最小兼容设计、风险和验收反例，不修改代码。
2. 实现项目无关的原生文字PDF到统一StructureBlock和ProtocolExtractionSnapshot的确定性解析器与格式分派，保存页码/文本范围所需稳定身份，扫描或文本层不足时返回结构化异常，不调用OCR或模型。
3. 把PDF结构入口接入方案解构执行器、重放harness和上传格式边界，补充合成/真实只读回归、格式分派、原PDF渲染复用、扫描失效关闭和路径/哈希/确定性测试。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
