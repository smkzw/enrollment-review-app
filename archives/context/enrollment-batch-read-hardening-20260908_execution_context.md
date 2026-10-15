# Execution Context: enrollment-batch-read-hardening-20260908

Created: 2026-09-08 09:15:34 CST
Objective: 修订默认关闭的多页实验模块，保证与逐页对照的额度、冻结图片和失败记录可靠；不做真实模型调用
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

- Read app/llm/page_review_batch_experiment.py, app/llm/page_review_harness.py, app/llm/independent_vlm.py, app/domain/contracts/page_review.py, tests/test_page_review_batch_experiment.py and tests/v2/llm/test_page_review_harness.py. Related import signatures may be read inside app only. No patient or configuration discovery.
- Write only app/llm/page_review_batch_experiment.py and tests/test_page_review_batch_experiment.py. Use apply_patch. Preserve unrelated changes.
- Verify using ENROLLMENT_ENV_FILE=tests/fixtures/isolated.env .venv/bin/python -m pytest -q tests/test_page_review_batch_experiment.py. This is the only allowed env fixture; never read .env. All completions injected, no live calls.
- Initial batch budget must be route.max_tokens, allowing 65536 for the real experiment; do not multiply by page count. Keep one length doubling and record budget limitation, no invented provider cap. Change experiment version for changed behavior. Preserve original clinical prompt/ClausePack and default-off boundary.
- No fallback enabled for this dispatch; local queue and contributor data boundaries remain untouched. Report limitations, not overall clinical acceptance.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只修改app/llm/page_review_batch_experiment.py与tests/test_page_review_batch_experiment.py。初始批额度用route.max_tokens而非乘页数，截断仅翻倍一次。调用前验证所有图片哈希和page身份，按现有read_page方式处理429等待但不换模型，不改默认harness。合成测试覆盖预检、额度、重试、缺页和混页。禁止读病例、env、artifacts、个人harness配置，禁止网络和递归委派。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
