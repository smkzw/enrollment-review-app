# Execution Context: r05-policy-predicate-links-20260914

Created: 2026-09-14 13:18:47 CST
Objective: Add explicit source requirement to atomic predicate attribution through existing protocol production and qualification consumers, preserving historical hashes and never guessing attribution.
Task type: `E03`
Risk: `high`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `pi/cursor/default -> codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> pi/openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `pi` / `cursor` / `default`
- Review owner: Codex directly reviews worker outputs and final artifacts.

## Source Of Truth

- Read app/domain/contracts/rules.py EvidenceRequirement/RuleComponent/RuleSet, app/services/binding_qualification_support.py, app/domain/contracts/predicate_binding.py, their actual protocol construction/projection consumers, and docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md section 17. Trace definitions before editing.
- Authorized edits: relevant existing app/domain/contracts, app/agents, app/projections, app/protocols, app/services files needed for explicit official requirement-to-predicate references. No unrelated changes. Preserve all existing dirty work. Do not create another job or pipeline. No tests or test edits at this construction stage; py_compile and source checks allowed.
- Optional explicit predicate references must be nonempty/unique/within the containing component when supplied; absent legacy data stays unattributed, never infer from singleton or fact_type. Exclude workflow/control origin misuse. Preserve absent-field serialization and historical identities. New semantic protocol output must carry the source links from its own interpretation, not Codex-authored medical answers. Trace actual schema/prompt builder and projection so the field is not dropped. Cross-component and trigger/exception ID membership must be validated deterministically.
- Qualification may recognize explicitly attributed published policies; do not call them clinically proven or activate automatic adoption. Preserve all multiple applicable policies, no arbitrary first/one-only shortcut. Preserve raw response and old job identity semantics; bump relevant new-input schema/prompt version only where genuinely required and explain compatibility.
- No recursive delegation of any kind (including pi-worker), no model calls, no private configs, no DB writes/importing application startup, no package installation, no browser, no source clinical files. Do not edit task/plan/global files; return report to runner. Use apply_patch for manual edits.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. Trace and implement explicit optional predicate references on official EvidenceRequirement end to end through protocol schema prompts projection validation and qualification. No models, database writes, runtime tests, or automatic adoption. Preserve legacy serialization when absent.

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
