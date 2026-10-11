Continue the same Worker 01 session and remain within the original Worker 01 authorized write paths. Parent Codex rejected the current v4 contract after source-level clinical acceptance found that `trigger_expression` and one global `exception_expression` cannot express which trigger branch an exception is allowed to waive.

This is a systemic correctness defect, not a D001-specific wording issue. For example, a latent-tuberculosis treatment exception must never waive active tuberculosis branches, and a shortened Chinese-medicine washout or completed leflunomide elimination path must never waive unrelated medication/treatment exposure branches. The approved architecture requires a complete exception tree with ALL/ANY/NOT semantics and no weakening of AND/OR logic.

Repair the generic contract, deterministic validators, Chinese Markdown rendering, and focused tests. Requirements:

1. Introduce stable identity for trigger DNF branches and a structured, source-backed way for every exception branch/path to declare exactly which trigger branch or branches it may waive. Choose the smallest coherent generic design; do not hardcode D001, tuberculosis, Chinese medicine, or leflunomide.
2. A row with exceptions must fail publication/strict validation when exception scope is missing, references an unknown trigger branch, references an applicability/obligation branch, or accidentally scopes to all triggers without explicit source support.
3. Preserve explicit ALL/ANY semantics inside both trigger and exception expressions. If NOT is needed by the approved architecture, represent it deterministically rather than as free-text negation. Do not infer absence from missing evidence.
4. Ensure stable identities survive JSON round-trip and are visible in machine serialization but not leaked as programmer identifiers in the Chinese reviewer Markdown. The Chinese view must state which clinical trigger branch each exception applies to in native clinical language.
5. Bump the schema version because existing v4 artifacts cannot safely preserve this meaning. Do not silently accept old v4 as equivalent.
6. Add regression tests proving at minimum:
   - an exception scoped to trigger branch A cannot waive branch B;
   - multiple exception alternatives can be scoped to the same trigger branch;
   - distinct scoped exceptions can target distinct trigger branches;
   - unknown/missing/broadly ambiguous scope is rejected;
   - JSON/Markdown identity and visible-language checks still pass;
   - existing time, evidence, source-closure, official numbering, phase and DNF checks remain intact.
7. Re-run the focused protocol-control suite and adjacent 5.8a-c protocol regressions. Record exact commands and outcomes. Do not edit the D001 artifacts in this Worker 01 pass.

Use `apply_patch` for edits. Return a complete report with changed files, contract migration impact, deterministic evidence, any remaining semantic limitation, and the exact next action required from Worker 02.
