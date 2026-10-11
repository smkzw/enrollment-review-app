# Execution Context: phase5-selective-vision-observation-sidecar-20260831

Created: 2026-08-31 21:17:09 CST
Objective: 为选择性视觉核验建立不可变观察侧车持久化合同、仓储和证据服务后置钩子；只消费已生成的页产物与OCR质量，不改变OCR原文、缓存、租约、方案语义或D001任务。
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

- `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260831_SELECTIVE_VISION_PAGE_TRIAGE_ACCEPTED.md`
- `app/evidence/selective_vision_review.py`
- `app/llm/independent_vlm.py`
- `app/domain/contracts/ocr.py`、`app/domain/contracts/evidence_processing.py`
- `app/storage/ocr_models.py`、`app/storage/ocr_repositories.py`
- `app/storage/migrations/versions/0018_fact_correction_commits.py`
- `app/services/evidence_processing_executor.py`
- 相关现有仓储、迁移和服务测试。D001 与原始临床资料只作禁止边界，不得读取、修改或恢复。

## Risk Boundaries And Write Ownership

- `worker_01` 完全只读。
- `worker_02` 是唯一生产代码写入者，可修改或新增：`app/domain/contracts/` 中一个聚焦合同文件及导出、`app/storage/` 中对应模型/仓储/导出、`app/storage/migrations/versions/0019_*.py`、`app/services/` 中一个聚焦后处理服务及导出。不得修改任何测试。
- `worker_03` 只能新增本切片独立测试文件：`tests/v2/storage/test_migration_0019.py`、`tests/v2/storage/test_selective_vision_observation_repository.py`、`tests/v2/services/test_selective_vision_observation_service.py`。不得修改生产文件或既有测试。
- 生产写入采用单写者；worker不得轮询或编辑其他worker正在写入的文件。Codex在全部worker结束后统一复核与修正。
- 不接入 `EvidenceProcessingExecutor` 的 OCR 核心步骤；后处理必须由显式服务入口调用，且不改变原处理修订、OCRPage、风险扫描或激活状态。
- 不把远端失败持久化为成功观察；若需要记录失败，只能使用明确失败状态且不得含模型伪输出。
- 不保存密钥、图像数据URL、绝对主机路径或完整请求载荷；观察正文必须保留来源声明，模型、提示版本、页身份和输入图像哈希必须可追溯。
- 不恢复D001，不修改旧检查点，不接触前端、方案语义、规则判定或临床事实发布。
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只读审阅现有证据合同、SQLAlchemy模型、仓储、迁移和证据处理服务，提出最小观察侧车身份、外键、幂等、失败状态与服务接入边界，不修改文件。
2. 作为唯一生产代码写入者，实现通用视觉观察侧车合同、SQLAlchemy模型、0019迁移、仓储及显式证据服务后处理接口；不得修改测试、OCR执行器核心语义、方案模块、前端或D001工件。
3. 仅新增独立测试文件，覆盖0019迁移、仓储追加/幂等/来源闭包、服务显式调用、原生文字跳过、失败关闭且不改OCR；不得修改生产文件。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
