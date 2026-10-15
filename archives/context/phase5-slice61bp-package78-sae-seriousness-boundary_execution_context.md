# Execution Context: phase5-slice61bp-package78-sae-seriousness-boundary

Created: 2026-08-30 01:56:47 CST
Objective: 为D001 II活动131包计划第78包建立模型外临床语义边界：完整理解SAE定义、任一严重性标准、住院/延长住院的因果限定，以及研究者综合判断可不作为SAE的住院情形；只建立真实来源闭包、通用门禁建议和确定性测试，不修改源方案、不并入正式矩阵、不运行受试者审核或临床语义模型。
Task type: `finite_code_task`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `night`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `codebuddy-cli/glm-5.3-flash:max -> codebuddy-cli/deepseek-v4-flash:max -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> openai-codex/gpt-5.6-luna:xhigh`

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

1. 只读核对body.p995-p1006与第79包body.p1007-p1014、AE/TEAE定义及收集窗口、方案内SAE报告和特殊肝功能SAE章节、现有流程目录和正式矩阵；明确每项定义/严重性标准/住院除外的语义职责、Patient Journey分类影响、与入排标准的边界及后续包所有权，不修改文件。
2. 基于第78包冻结计划创建最小真实来源闭包配置、父级临床核对清单和确定性测试；阻断把SAE定义、严重性标准或住院除外改写为筛选/基线入排门槛，保留任一严重性标准的OR语义、住院由AE导致的因果限定、研究者综合判断及第79包连续列表边界；只编辑本切片新增工件及必要共享测试，不调用模型、不改正式矩阵。
3. 独立审查第78包和现有控制矩阵，寻找SAE定义倒灌入排、死亡结果与死亡原因混淆、危及生命反事实扩大、轻微功能干扰误判严重残疾、任意住院即SAE、研究者综合判断被自动豁免、跨包列表截断和后续ADR/SUSAR提前吞并等反例；给出可执行验收条件，不修改实现。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
