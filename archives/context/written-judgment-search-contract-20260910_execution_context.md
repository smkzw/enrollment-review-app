# Execution Context: written-judgment-search-contract-20260910

Created: 2026-09-10 03:59:44 CST
Objective: 实现研究者书面判断跨文件检索的最小候选合同和纯覆盖核验，不接临床采信
Task type: `E03`
Risk: `high`
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

- Read docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md section about confirmed missing written judgment; plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md section 2; app/domain/contracts/page_review.py, facts.py, evidence_expectations_v2.py; app/domain/page_review_evidence_sources.py; app/projections/written_judgment_evidence.py. Review output is not authority: previous proposal to inspect only measurement pages was rejected.
- This dispatch uses primary zcode/GLM-5.3-Flash:max only. No fallback, especially no local platform activation. Product runtime remains GLM/Gemini. No real data, network, credentials, tool installation, uvx, other agents, or database changes.
- Allowed writes ONLY new app/domain/contracts/judgment_search.py, app/domain/judgment_search_coverage.py, tests/v2/domain/test_judgment_search_coverage.py. If any exists inspect and report before overwriting. Standard library/Pydantic existing patterns; apply_patch only when available, report limitation. No app exports/wiring/model calls in this step.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 独立模块与合成测试：冻结页域、双读逐页检索结果、缺页/失败/歧义/跨身份拒绝；只作为后续产品来源检索候选，不能直接产生专业判断缺口

Implement a small CANDIDATE-only contract (not a proof DTO): a frozen search scope binds FactAuthority, requirement identity and source-page identities (document version, page artifact, page number, image SHA256); content-addressed canonical scope hash. Nonempty scope; unique page identities; ordered deterministic members; cannot silently exclude unreadable or unknown-date documents. Scope is supplied later by a repository-backed builder; this pure module MUST NOT claim it proved the scope covers all eligible clinical sources.

Each independent main-A/main-B result references the exact scope hash and lane/provider/model identity, and exactly one result per searched page. Per page has BOTH handwritten and printed-analysis search dispositions: found / not_found / unreadable / ambiguous. Found requires source-bound exact excerpt plus page identity (bbox optional); non-found must not carry a fabricated excerpt. These are model SEARCH candidates only, no eligibility decisions, no clinical significance judgment, no professional_judgment output, no timestamps inferred from upload. Never collapse absent page entry into not_found.

Pure summarize function compares scope and both candidate results: reject mismatched scope, duplicate/extra page, wrong page hash, duplicate lane, same provider+model counted twice, contradictory shape; missing pages, failures/ambiguity or one missing lane are incomplete, not missing judgment. When every page in SUPPLIED scope has two valid independent records and both channels explicitly not_found, return only all_supplied_pages_searched_without_candidate (or comparably literal internal status), with source_scope_verified=False/product_acceptance=False invariants. If any found candidate on ANY page/file, return candidates_present, preserve found and gaps, NEVER treat it as requirement satisfied or applicable. Mixed found/none is not consensus approval. No arbitrary acceptance booleans from callers. Avoid overengineering generic rule engines or new mutable repositories.

Tests include two files, printed analysis found on a page other than measurement page blocks all-not-found; incomplete second channel; omitted page; unreadable; one lane only; same model masquerading as second; scope/page hash mismatch; duplicate page; empty scope; stable identity order; all supplied pages explicitly not_found still NOT proven professional judgment absence. Reject judgment/eligibility extra fields. Names must clearly say candidate/coverage, not certified or accepted clinical proof.

Run only new synthetic tests and smallest relevant existing contract tests with .venv/bin/python. Return exact tests and explicitly state repository-built complete source scope, independent product searches, persistence, applicability and clinical absence producer are NOT wired and remain required. No product clinical behavior changes claimed.

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
