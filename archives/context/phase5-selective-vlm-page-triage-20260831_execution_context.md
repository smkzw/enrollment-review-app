# Execution Context: phase5-selective-vlm-page-triage-20260831

Created: 2026-08-31 20:27:38 CST
Objective: 为独立GLM-5.3-Flash视觉模型建立通用、按页面风险选择的最小业务接入：原生文本优先，只有扫描、复杂表格、结构异常或OCR低置信页进入视觉核验；保留来源定位、失败关闭、费用时延可控和业务路由隔离，不恢复D001。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `day`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `cursor/default -> google-antigravity/gemini-3.7-flash:high -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> opencode-go/muse-spark-1.2-contributor:xhigh -> openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `pi` / `cursor` / `default`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` and `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md` Phase 4/5 boundaries.
- `app/llm/independent_vlm.py` and `tests/v2/llm/test_independent_vlm.py`: accepted Coding Plan transport and source-fidelity contract.
- `app/evidence/page_processor.py`, `app/services/evidence_processing_executor.py`, `app/domain/contracts/ocr.py` and `app/domain/contracts/enums.py`: current page/OCR evidence flow.
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260831_ZHIPU_CODING_PLAN_VLM_LIVE_ACCEPTED.md`: latest accepted state and next safe action.
- Do not add production paths without explicit Codex authorization.

## Write Ownership

- `worker_01` is read-only.
- `worker_02` is the sole production writer. It may add one focused module under `app/evidence/` or `app/services/` and make the smallest necessary export/config edit. It must not edit tests, existing OCR execution semantics, protocol deconstruction, clinical rules, replay artifacts, or frontend files.
- `worker_03` may only add `tests/v2/evidence/test_selective_vision_review.py`. It must not modify production files or existing tests.
- Shared files have one writer only. If the declared boundary is insufficient, stop and report instead of editing another role's files.

## Product Contract

- Native DOCX/PDF text remains primary and is never resent page-by-page merely because a VLM exists.
- Vision review is eligible only for a page-level reason established from structure/quality metadata: scan/image-only page, complex visual/table layout not represented by native text, native extraction anomaly, or OCR/evidence risk requiring visual confirmation.
- The decision is content-neutral: no study id, disease, drug, score, visit, criterion number, or project-specific keyword.
- A vision response is an evidence-review observation with stable source identity, never an enrollment decision or corrected OCR overwrite.
- Provider failure is explicit and closed; it must not silently fall back to another semantic or OCR route.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只读审阅Phase 4/5设计、当前证据处理链与独立VLM合同，提出最小页面风险判定合同、输入输出和禁止边界，不修改文件。
2. 作为唯一生产代码写入者，在证据处理/共享服务边界实现通用的选择性视觉核验规划与调用适配；不得修改测试文件、OCR执行器语义或D001工件。
3. 仅修改新的独立测试文件，为页面风险选择、原生文本跳过、扫描/表格/结构异常/低置信进入、失败关闭、来源保真和无项目特异硬编码建立确定性测试；不得修改生产文件。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
