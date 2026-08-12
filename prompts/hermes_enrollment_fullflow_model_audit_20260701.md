You are Hermes running inside a Codex-controlled workflow.

First, fully read and comply with `/Users/smkzw/.hermes/SOUL.md`. In your output, include one sentence saying whether you read the full file. Do not claim this unless you actually read it.

Hard boundaries:
- Work only inside `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app`.
- Do not read or modify production paths.
- Do not edit files unless Codex explicitly authorizes an edit round.
- Do not browse web, run tests, open browsers, inspect images, or perform visual/PPT/browser acceptance unless explicitly assigned.
- Write exactly one output file: `runs/hermes_enrollment_fullflow_model_audit_20260701.md`.

Read these files only:
- `context/enrollment_fullflow_model_audit_20260701_context.md`

Task:
Review the task context and produce a concise execution plan for Hermes' bounded role only. Identify what Codex must verify directly before any final acceptance.

Output schema:
1. `# Hermes Task Plan: enrollment_fullflow_model_audit_20260701`
2. `## Boundary Check`
3. `## Hermes-Safe Work`
4. `## Codex-Owned Verification`
5. `## Proposed Next Prompt Or Execution Slice`
6. `## Escalation Triggers`

Quality gates:
- Do not claim access to sources not listed in the context.
- Do not make final clinical/regulatory/visual/current-web claims.
- Keep the plan scoped to Hermes execution, not Codex final review.
