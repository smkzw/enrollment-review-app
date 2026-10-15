# Execution Context: phase4-evidence-ocr-v2-slice44

Created: 2026-08-19 22:56:48
Objective: 按已冻结的 Slice 4.4 契约串行实现证据定位、OCR 风险核对、校对覆盖层、完整处理修订与权威活动指针；先完成并验收 WP-44A 领域合同、0010 无损迁移和追加仓储
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 4 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `pi` / `cms-smk` / `deepseek-v4-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `AGENTS.md` and `.trellis/workflow.md`.
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/prd.md`.
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/design.md`.
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/implement.md`.
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/research/slice44-detailed-contract-review.md` is the frozen Slice 4.4 detail contract.
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` and `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md` define the phase boundary.
- Current Phase 4.1-4.3 contracts, migrations `0008` through `0009`, repositories, and tests are immutable regression anchors. Existing uncommitted changes belong to the active rearchitecture and must not be reset, reformatted broadly, or overwritten.
- No raw protocol or subject clinical material is required or authorized for Slice 4.4 implementation.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.
- Execute work packages strictly in order `WP-44A -> WP-44B -> WP-44C -> WP-44D`. Only one worker may write at a time. A later worker starts only after Codex has independently reviewed the earlier package and recorded acceptance.
- Preserve source OCR, page artifacts, prior snapshot events, and existing `0009` processing revision payload/hash byte-for-byte. Add only append-only or nullable sidecar state.
- Consolidate the two `ReviewEpisode` definitions into one runtime contract, but retain the legacy `evidence_snapshot_id` field without changing its meaning. It is never a fallback for the new current-version projection.
- New active snapshot and complete processing revision pointers are paired: both null or both non-null. Never backfill them from time, ID order, status, or legacy fields.
- A base processing revision is never activatable. Candidate process state is separate from an immutable complete revision.
- OCR risk scanning may create review prompts only. It must not alter clinical facts, protocol rules, inclusion/exclusion logic, or weaken `AND` into `OR`.
- Locator bounding boxes require same-source coordinate evidence and occurrence proof. Do not fabricate coordinates or red boxes.
- Do not modify or delete existing clinical reports, legacy projects, screenshots, or source documents.

## Allowed Write Surfaces

- `WP-44A`: `app/domain/contracts/`, `app/storage/`, `tests/v2/domain/`, `tests/v2/storage/`, and this execution module's report/metrics/review records only.
- `WP-44B`: deterministic evidence engines/services/workflow plus focused tests; no API or frontend changes.
- `WP-44C`: `app/api/v2/`, subject/current projections, and focused API tests; no frontend changes.
- `WP-44D`: `frontend/src/`, `frontend/e2e/`, and focused frontend tests/screenshots. Continuous original-document scrolling and final red-box viewer remain Slice 4.5.
- Cross-surface edits require a concrete dependency and must be reported before broadening.

## Acceptance Evidence

- Each package supplies a precise changed-file list, focused tests, Ruff, production-code Pyright where applicable, and `git diff --check`.
- `WP-44A` additionally proves upgrade from exact `0009`, row counts and child foreign keys preserved, old payload/hash unchanged, `PRAGMA foreign_key_check` and `integrity_check` clean, no guessed pointer backfill, and downgrade refusal when `0010` history exists.
- Codex performs an independent fresh-context review before releasing the next package.
- Slice 4.4 completes only after full V2 backend regression, frontend checks for affected surfaces, migration regression, and execution records are accepted.

## Work Items

1. WP-44A：收敛唯一 ReviewEpisode 运行时合同，新增成对活动指针、base/complete 修订辨别与处理候选合同
2. WP-44B：实现 occurrence-aware 定位、OCR 风险旁路核对、校对投影、完整修订和原子激活/回滚
3. WP-44C：实现页、校对、完整修订、激活、引用资料等后端接口与 current 指针投影
4. WP-44D：实现中文原生 OCR 核对闭环前端并完成宽屏交互验证

These are dependency-ordered work packages, not parallel assignments.

## 2026-08-20 WP-44A Acceptance Checkpoint

- WP-44A is accepted after independent fresh-context verification; WP-44B is now the only released write package.
- Final anchors: focused `225 passed`; full V2 `1361 passed, 2 subtests passed`; scoped Ruff/Pyright and diff check passed.
- New complete revisions must select every current in-scope metadata head, correction head, referenced-document head and resolution head. Historical reads validate the exact frozen IDs and payload hashes but do not require those IDs to remain current.
- A correction occurrence is one base revision + OCR page + raw text hash + original character range. It has one root and a single-successor chain; distinct non-overlapping occurrences remain valid.
- Complete revision root, persisted ordered pages and all associations are one savepoint and are re-read before return. Any validation failure removes the entire new complete revision even if the caller later commits unrelated work.
- Locators bind the exact selected PageArtifact/OCRPage/source layer/text hash. Page excerpts must replay in that source; no source proof means no valid locator and no red box.
- Remaining residual: true simultaneous multi-connection correction-root insertion was not exercised, but SQLite enforces a matching partial unique index at the database boundary.

## 2026-08-20 WP-44B Acceptance Checkpoint

- WP-44B is accepted after three passes in one fresh-context `gpt-5.6-sol:high` verifier session. Native child dispatch hit the active usage limit; the declared CLI compatibility route used the same model/effort and no substitution.
- The first rejection exposed overlapping occurrence loss, referenced-document chain-root selection, inability to distinguish deterministic discovery from user confirmation, missing default activation idempotency and a repository API that allowed orphan/cross-state activation history.
- The second rejection exposed a deeper repository bypass: an already-active snapshot could switch to a stale READY candidate while leaving the candidate state READY. The unique repository unit-of-work now validates candidate expected revision and atomically writes ActivationEvent, paired episode pointers and candidate ACTIVE transition. Candidate transition failure rolls back snapshot activation as well through the service transaction.
- Referenced-document registration and resolution use unique chain heads; user confirmation preserves deterministic origin plus explicit user-review provenance. Confirm/revise/dismiss reasons are immutable and nonblank. Risk seed denominators are frozen at 26 critical kinds, 13 clean pages, 10 risk pages and 23/23 eligible-page coverage.
- Final anchors: focused `209 passed`; full V2 `1455 passed, 130 warnings, 2 subtests passed`; scoped Ruff/Pyright and diff check passed. Independent final pass returned `ACCEPT` with no open P0/P1/P2.
- WP-44C is the only released write package. It may add V2 API/current projections and focused API tests only; no frontend changes. WP-44D and Slice 4.5 visual work remain blocked.

## 2026-08-21 WP-44C Acceptance Checkpoint

- WP-44C is accepted after a two-pass review in the same fresh-context `gpt-5.6-sol:high` verifier session. The first pass rejected three P1 issues: a new key reactivating the current pair escaped as 500, a provided referenced-document resolution could bind another subject's document version, and the API mapper recognized storage exceptions through upload-service re-exports.
- The application boundary now translates known upload failures into stable application errors; `app/api/v2/errors.py` imports neither upload services, storage modules nor SQLAlchemy. Re-activation of the current pair returns structured `409 CURRENT_VERSION_UNCHANGED` without growing activation, idempotency or episode history.
- A provided referenced-document resolution is accepted only when its document version matches the registration project/subject/review episode and is a member of that episode's current active snapshot. Both the service and repository enforce this, including direct repository bypass tests.
- Final anchors: focused `39 passed`; API/services `335 passed`; full V2 `1537 passed, 130 warnings, 2 subtests passed`; scoped Ruff, project-venv Pyright and diff check passed. The verifier independently reran 180 focused tests, 335 API/service tests and the same full V2 suite, then returned `ACCEPT` with no open P0/P1/P2.
- WP-44D is now the only released write package. It may implement the Chinese review-loop frontend and its focused tests/screenshots. Slice 4.5 continuous source-document scrolling and complete true-red-box experience remain blocked.

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.

## 2026-08-21 WP-44C-R/WP-44D 终局恢复点

- 状态：同一 fresh-context `gpt-5.6-sol:high` 独立验收会话最终 `ACCEPT`，Slice 4.4 完成。
- 持久构建：校对、风险核对和显式构建原子建立 `staged` 候选与持久任务；候选冻结全部输入记录；HTTP 不同步构建；后台执行支持租约、重启恢复和 READY/ACTIVE 幂等重放。
- 前端恢复：候选编号写入本地恢复锚点；暂时连接失败继续退避轮询；404 仅在旧锚点仍有效时删除。新候选一经命令返回即令旧恢复/旧轮询失效，已用“旧候选晚到成功”和“旧候选晚到 404”两条反例证明不会覆盖或删除新候选。
- 用户语言：冲突区域统一使用“系统当前记录”，不展示“服务端”等工程术语；409 保留用户本次输入。
- 最终证据：后端全量 `1543 passed, 130 warnings, 2 subtests passed`；前端 `41 files / 336 tests`；生产构建通过；证据工作台 Playwright 三档宽屏 `6 passed`；Ruff、项目虚拟环境 Pyright、`git diff --check` 通过。
- 未完成边界：Slice 4.5 的连续原始资料滚动、真实坐标到页图的缩放映射和红框尚未实现。无真实坐标时继续只显示中文降级定位，不画伪红框。
- 下一安全动作：读取设计书和实施计划的 P4-AC01 至 P4-AC13，形成 Slice 4.5 文件/页/文本/原图统一选择状态与证据呈现工作包，再开始代码变更。
