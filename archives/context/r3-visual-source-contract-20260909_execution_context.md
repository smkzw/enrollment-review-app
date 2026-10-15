# Execution Context: r3-visual-source-contract-20260909

Created: 2026-09-09 04:59:55 CST
Objective: 建立独立的R3视觉事实来源合同与纯物化器，严格绑定原页和双读已采信事实/手写，不依赖OCR字面相等；本包仅合同模块和测试，不接正式写入。
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

- Read docs/REARCHITECTURE_FINAL_DESIGN_20260812.md sections 3.3, 4.2 and 7.2; app/domain/contracts/page_review.py, app/domain/contracts/facts.py, app/domain/contracts/evidence_locator.py, app/projections/page_review_sources.py and relevant reconciliation implementations/tests. All existing application files are read-only for this packet.
- Current product models are GLM-5.3-Flash and Gemini-3.7-Flash, not local models. This engineering worker must not call clinical models, inspect credentials, databases or raw clinical records, or use network tools.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 实现app/domain/page_review_evidence_sources.py及tests/v2/domain/test_page_review_evidence_sources.py；其他app文件只读。

## Precise Implementation Contract

Only the two assigned files may be created/edited, using apply_patch. Implement an immutable, content-addressed visual-source contract and pure materializer. No database writes, no changes to existing revisions, no product wiring yet. Source text and image hashes must remain separate; never put an image hash in a text-hash field. Bind to coverage, reconciliation, source document/page/image, ClausePack and existing snapshot/processing authority. Retain original excerpts and source review IDs, response hashes and model identities.

Materialize only accepted fact observations and accepted handwriting, never clause signals, NONE, conflicts or single-reader content. Require two distinct main readers and actual matching evidence for the accepted target; identical model identities in two lanes are not independent. Validate coverage/page/image/document/ClausePack consistency and reject stale or inconsistent input. Inspect existing reconciliation and association semantics before implementing: do not invent a second incompatible reconciliation algorithm. If an upstream validated association is required, make that an explicit input/precondition with binding checks, not a claim that a key alone proves agreement.

Visual excerpts do not need to be substrings of OCR. Their precision is page_excerpt; model-proposed boxes must not become authenticated coordinates. Preserve literal excerpts and provenance, do not synthesize clinical facts or conclusions. Do not create a replacement processing revision: that would require re-binding coverage and is outside scope. The new contract is additive and unconnected until owner integration review.

Use existing dependencies and standard library. Tests use synthetic fixtures only. Cover stable content addressing, raw excerpt preservation, changed excerpt/image/hash, duplicate model, wrong page/document/coverage, conflicts and single-source rejection, accepted facts/handwriting, and exclusion of clause-only evidence. Run only the assigned test file with the existing project Python environment; report exact command and outcomes. No installation, recursion or other dispatch. Return remaining integration requirements honestly.

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
