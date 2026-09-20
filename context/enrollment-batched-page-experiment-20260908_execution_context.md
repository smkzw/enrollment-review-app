# Execution Context: enrollment-batched-page-experiment-20260908

Created: 2026-09-08 07:05:48 CST
Objective: 实现默认关闭的产品多页读片实验适配，复用现有提示及页级校验，仅允许新增独立模块与聚焦测试，不读病例或密钥，不调用被测模型，不修改默认流程。
Task type: `E03`
Risk: `medium`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `zcode/glm-5.3-flash:max -> opencode-go/muse-spark-1.3-contributor:xhigh -> mtplx/qwen3.8-flash-next-mtplx-optimized-speed:medium -> openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `zcode` / `zcode` / `GLM-5.3-Flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- Read app/llm/page_review_harness.py, app/domain/contracts/page_review.py, app/domain/contracts/page_review_context.py, app/llm/page_review_context_layout.py, app/projections/page_review_prompt_pack.py and corresponding existing tests as needed. These files are read-only for this worker.
- Allowed edits ONLY app/llm/page_review_batch_experiment.py and tests/test_page_review_batch_experiment.py. Use apply_patch, preserve all other dirty work. Native tests through ENROLLMENT_ENV_FILE=/dev/null .venv/bin/python -m pytest -q tests/test_page_review_batch_experiment.py. No real model/network calls; no clinical files, artifacts, output, credentials, home configs, database reads. No dependencies or default wiring changes.
- Design: this is a product-usable opt-in experiment, not default adoption. Original full ClausePack, page bytes, schema and clinical prompt constraints must remain; generic batch framing is the sole experiment. Preserve nonclinical page IDs/source provenance and explicit partial failures; no page cross-attribution. Report interface and limits so owner can build frozen benchmark driver separately.
- Route execution is zcode/GLM-5.3-Flash:max only for this packet. No fallback this run; local benchmark remains separately owned. Required prior connectivity on this same route succeeded; runner health-check again before dispatch. Wait up to7200 seconds without periodic redispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 新增app/llm/page_review_batch_experiment.py与tests/test_page_review_batch_experiment.py：把同一节点的一组PageReviewInput经现有build_page_review_messages构造，共用完整ClausePack和Schema，一次图文请求要求按page_artifact_id返回每页原PageReviewPayload；不得自行生成临床题目。复用read_page对拆分响应逐页校验，记录批ID和不同prompt_version/recordID。拒绝混审核节点、重复页或返回未知页；缺页明确失败，不静默丢弃；保留每页失败和有效部分。截断仅按现有规则翻倍一次，不降额度，不修改采样；不能重写已有read_page大文件。使用注入completion和合成数据单测证明页归属、部分失败、未知/重复页、额度与身份。不要读取artifacts/output或任何病例/.env/OMP/Hermes配置。最终报告代码路径、测试、限制。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
