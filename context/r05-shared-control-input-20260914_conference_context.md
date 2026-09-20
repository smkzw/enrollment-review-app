# Conference Context: r05-shared-control-input-20260914

Created: 2026-09-14 02:41:09 CST
Objective: 只读审阅跨章节要求从正式发布到双读条款包的新接线，查历史哈希、来源节点、忽略要求和语义失真；不测试、不调用产品模型或数据库
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `zcode/zcode/glm-5.3:max -> grok/grok-build/grok-4.6:high -> pi/cursor/cursor-grok-4.6:high -> pi/openai-codex/gpt-5.6-sol:medium`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r05-control-status-read-20260914`
- Execution evidence status: `linked`
- Excluded route identities: `codebuddy/codebuddy-cli/deepseek-v4.1-flash`
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md section17.3; app/domain/contracts/protocol_controls.py full relevant four-layer catalog definitions; app/protocols/protocol_control_gate.py final publication validation; app/services/protocol_control_execution.py payload and final checkpoint semantics. These are the source contracts, not worker reasoning.
- Review current affected artifact: app/protocols/control_catalog_materialization.py; app/domain/contracts/control_catalog_publication.py; app/storage/control_catalog_repository.py; app/services/protocol_control_catalog_publication.py; app/services/protocol_control_status.py; optional control references in protocol_publication_service.py/workbench/API. app/domain/contracts/clause_pack.py, app/projections/clause_pack.py, page_review_prompt_pack.py, app/services/published_clause_pack.py, page_review_job_service.py, page_review_execution.py, page_review_coverage_selection.py, page_review_visual_sources.py; app/llm/page_review_format_repair.py and build_page_review_messages in page_review_harness.py; review_context_assembly.py, contracts/review_context_v2.py and frozen_review_calculation.py. Follow direct dependencies only.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: Read-only source review of this publication-to-reading vertical slice. Identify P0/P1/P2 bugs with exact file/line and source-contract evidence, propose minimal fixes. Check exact source item/node bridge, source/checkpoint/version/attempt identity, immutable hash and v1 serializer compatibility, v2 prompt fidelity without fake official numbering, dual-reader reconstruction/cache agreement. Assess whether classifying control relation signals as dropped deterministic aggregation is an acceptable read-stage boundary (NOT claiming semantic atoms proven). Give next minimal common-requirement/evaluation integration design preserving applicability/trigger/obligation/exception, modality, node roles and missing-investigator-judgment distinctions. Do not recommend flattening four-layer controls to exists predicates or project-specific mappings.
- Out of scope: no writes whatsoever (runner persists final report), no tests including synthetic assertions, no DB, source clinical files, models, browser, network, package installs, create_app or servers. User defers staged tests; source review is not clinical acceptance. Owner is not claiming full R05 completion: final control evaluation/shared expectations and frontend orchestration are absent, and frozen_review_calculation explicitly refuses nonempty controls rather than silently omitting them. Do not treat these declared pending modules as newly discovered implementation bugs, but analyze safe integration requirements. No worker private reasoning or prior reviewer report required. No delegation. Owner freezes these files during review. Return concise findings and next concrete integration contract; no PASS for the whole product.

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.

## Conference Pass Rule

This packet uses one serial Codex-led conference object. Each declared role receives one complete prompt and may use multiple internal tool turns. Codex decides whether a same-session follow-up is needed after reviewing the result; follow-ups do not create a new conference or change the route identity.

## Timeout Policy

- Participant soft wait: 60 minutes.
- Large-task participant wait: 120 minutes.
- Chair hard wait: 120 minutes.
- Failure rule: Do not fail a model for slow response alone; fail only on terminal error, provider exhaustion/rate limit after controlled retry, empty/truncated retry output, or no useful progress after the high-budget same-session recovery loop. A catalog/auth/transport health preflight timeout or malformed response is diagnostic and must still allow one live route attempt; explicit user routes also proceed when the catalog is stale or incomplete, while a genuinely missing CLI or native transport boundary may block. If a resumable session exists after a step/size boundary, continue it before fallback; repeated identical output/tool evidence triggers the no-progress breaker.
- Pass/turn boundary: one conference prompt is one conference pass. The
  `--max-turns` value controls internal Agent tool-calling turns and is never
  set to 1 for substantive conference execution; generated participant and
  chair commands use the route budgets recorded by the guard.

## Risk Boundaries

- External Agents are advisory; Codex remains final authority.
- Codex owns visual/browser/PPT/PDF/rendered checks, live authority checks, final clinical/regulatory conclusions, and production writes.
- Do not mark a slow model failed solely due to latency.

## Loop Log

- 2026-09-14 02:41:09 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
