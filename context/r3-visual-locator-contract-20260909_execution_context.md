# Execution Context: r3-visual-locator-contract-20260909

Created: 2026-09-09 05:57:40 CST
Objective: 增加明确的视觉定位来源类型及纯投影，原图哈希与摘录文本哈希严格分立；不改旧修订，不接存储与发布。
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

- Read app/domain/contracts/enums.py, evidence_locator.py, app/domain/page_review_evidence_sources.py, app/services/page_review_visual_sources.py, their focused tests, and docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md latest visual-source section. Existing unrelated files read-only. No network, credentials, DBs, clinical raw files, other workspaces or model calls.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只修改app/domain/contracts/enums.py和evidence_locator.py，新增app/projections/page_review_visual_locators.py与tests/v2/domain/test_page_review_visual_locators.py；其他只读。

## Completion And Cleanup

## Implementation And Acceptance Contract

Write only the four assigned paths with apply_patch. This is an unconnected additive contract/projection, not permission to persist, publish or change processing revisions. Preserve existing behavior and serialization when the new optional field is absent.

Add explicit LocatorSourceLayer.PAGE_REVIEW_VISUAL = page_review_visual. Add a compact typed visual provenance field to EvidenceLocatorArtifact, optional and excluded when absent, mandatory only for the new layer and forbidden for other layers. It must bind source_set_id, coverage_id, existing processing revision ID, source target ID, selected page_review_id and page_image_sha256. Existing source_text_sha256 MUST equal actual sha256 of the exact selected reading excerpt, never image hash. Require source target agrees with target_id; require PAGE_EXCERPT, DEGRADED with clear native Chinese reason, no bbox/sidecar/coordinate/text-range/ocr ID/effective projection. Keep processing binding in the typed provenance (do not loosen existing effective_text-only field rules). Content hash is not proof of provenance: document repository will later rebuild source sets to validate this record against actual persisted readings.

Implement pure project_visual_locators(source_set) using PageVisualEvidenceSourceSet validated serialization as input. For each accepted fact/handwriting source, create one locator per original reading excerpt/reading ID, preserving exact original strings. Keep both differing excerpts; no synthetic combined sentence or invented fact. Stable locator IDs must include source set, source target, reading and excerpt hash; use existing canonical_hash and locator_anchor_hash. Timestamp from source set (deterministic rebuild service already freezes it). No OCR match required, no confidence=1 fiction. Source set and original reading remain unchanged. Do not duplicate service materialization or build storage. Empty set yields no locators.

Tests: original text locators serialized unchanged; visual absent provenance rejected; provenance on text rejected; excerpt hash tampering rejected even recomputing anchor; target mismatch; bbox/ocr/sidecar rejected; pure fact/handwriting projection includes both readers, distinct source IDs, deterministic identity and original strings, no input mutation. Run new test and existing locator contract tests discovered by rg, only synthetic. Report exact outcomes and remaining mandatory storage/gate/UI integration honestly. No external/model calls or fallback.

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
