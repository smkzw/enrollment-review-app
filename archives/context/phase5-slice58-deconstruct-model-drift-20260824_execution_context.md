# Execution Context: phase5-slice58-deconstruct-model-drift-20260824

Created: 2026-08-24 00:49:29
Objective: 修复 Phase 5.8 真实隔离验收暴露的方案解构模型配置漂移，使新数据库使用当前可用的专属方案解构模型并以聚焦回归和真实运行证明。
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `codex-subagent` / `codex` / `gpt-5.6-luna`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `AGENTS.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/{prd.md,design.md,implement.md}`
- `.trellis/spec/backend/{index.md,quality-guidelines.md,error-handling.md}`
- `app/config.py`
- `app/agents/deepseek_protocol_transport.py`
- `app/llm/client.py`
- `tests/v2/agents/` and focused configuration tests under `tests/v2/`
- the live oMLX `/v1/models` response at `http://127.0.0.1:8001`
- isolated failure evidence under `artifacts/phase5-acceptance/20260823/data/`
- Do not add production paths without explicit Codex authorization.

## Write Boundaries

- `worker_01`: read-only audit; no source or test edits.
- `worker_02`: may edit only `app/config.py`, `app/agents/deepseek_protocol_transport.py`, `app/agents/protocol_deconstructor.py`, `app/services/protocol_deconstruction_executor.py`, and focused existing/new tests that directly verify deconstruction backend selection, endpoint/key handling, current default model, strict output-schema selection, bounded failure diagnostics, and explicit environment overrides.
- `worker_03`: read-only independent check of the resulting diff and focused tests; no source or test edits.
- Preserve all unrelated dirty-worktree changes; do not revert, reformat, or clean files outside the declared boundary.

## Confirmed Failure Mechanism

- The isolated Phase 5.8 run declared `DECONSTRUCT_BACKEND=omlx` but `_resolve_transport()` still required `DEEPSEEK_API_KEY` and always constructed `DeepSeekProtocolAgentTransport` against `DEEPSEEK_BASE_URL`.
- `DECONSTRUCT_MODEL` also inherited the obsolete review default `Qwen3.6-27B-oQ8-mtp`; current oMLX exposes `Qwen3.8-27B-oQ8e-fp16-mtp`.
- The repair must address the full backend-selection contract. An environment-only workaround or model-name-only change is not acceptable.

## Real Rerun Finding After The First Repair

- Parent Codex confirmed live `/v1/models` includes `Qwen3.8-27B-oQ8e-fp16-mtp` and the isolated backend started without a DeepSeek key.
- oMLX logs prove the D001-II run reached that model. Four calls returned non-empty bodies with `finish_reason=stop`, but both durable job attempts ended `SEMANTIC_DRAFT_MISSING`.
- The current oMLX transport asks only for `json_object` even though the code owns distinct `ProtocolSemanticDeconstructionCandidate` and `ProtocolSemanticRuleRepair` schemas. The executor discards the runner's actionable schema/gate issues when `final_draft` is absent.
- Continue in the same execution session. Prefer an explicit output-kind contract from caller to transport; do not infer schema kind by brittle prompt substring matching. Keep DeepSeek's existing compatible behavior unless its provider contract is independently proven to support the strict schema. Never relax the domain schema merely to make the model pass.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 审计方案解构配置来源、注册路径和 oMLX 当前模型目录，界定共享 REVIEW_MODEL 继承导致的系统性漂移。
2. 以最小共享层修改将方案解构默认模型与旧审核模型解耦，保持环境变量显式覆盖和现有临床逻辑不变。
3. 补充配置合同和方案解构传输路径回归，执行聚焦测试并给出真实隔离重跑前的风险清单。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
