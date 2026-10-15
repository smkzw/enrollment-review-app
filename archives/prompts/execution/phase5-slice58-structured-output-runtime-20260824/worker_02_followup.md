Delegated mode. Continue the SAME worker_02 execution session. Keep the original hard boundaries, authorized implementation scope, model identity (`gpt-5.6-luna`, effort `max`), and report schema. This is a consolidated remediation pass after independent read-only review; do not start a conference and do not perform final real-project acceptance.

Codex independently accepted the direction of the compact non-recursive wire contract, but found the following systemic closure defects. Repair all of them coherently, not as D001-specific patches:

1. Strict repair batch identity
   - Both the main semantic-repair loop and `revise_protocol_draft_from_feedback` must pass an exact deterministic `expected_batch_id` into compact repair parsing/validation.
   - Generate one canonical repair batch id from the ordered target parent rule codes and use the same value in prompt, parser, and tests.
   - A response for a different target rule set must be rejected before it can modify a candidate.

2. Exact source ownership closure
   - `_batch_prompt_payload` must expose only source span IDs that belong to the selected parent-rule batch; do not send the global allowed-source list.
   - Candidate components, warnings, and unresolved-item `source_refs` must all be subsets of this selected closure.
   - Do not allow ownerless process/procedure spans merely because they exist globally. A shared span may be used only when it is explicitly in at least one selected parent rule's source set.
   - Reject cross-batch and ownerless source references with focused tests.

3. Compact feedback revision
   - `revise_protocol_draft_from_feedback` must not serialize/send the full frozen 36-rule/91-source input for a targeted repair.
   - Reuse the selected target-rule payload and source closure. Preserve only the common metadata actually required to validate phase/version/catalog identity.

4. Bounded transport and truncation handling
   - Set the OpenAI-compatible client retry behavior explicitly so SDK retries cannot multiply a 600-second request (`max_retries=0` unless current local evidence proves a smaller explicit bound is necessary).
   - Keep application-owned retry semantics observable and bounded.
   - Treat a provider response with `finish_reason == "length"` as a transport failure requiring the existing bounded repair/retry path; never parse or accept it as complete JSON.
   - Add focused transport tests proving retry configuration and length handling. Do not broaden into a new job scheduler in this pass; record any remaining whole-job deadline concern precisely.

5. Remove undeclared domain loss
   - Remove the compact wire schema's hidden 128-node/children cap unless you also establish the same invariant in the authoritative domain contract and deterministic gate. Prefer removing the wire-only cap so valid domain expressions remain representable.

6. Cross-batch provenance integrity
   - Do not silently attribute later batches to the first batch's `created_by_agent_call_id`.
   - Choose the smallest coherent contract: require all batch candidates in one semantic run to carry the same logical call id and reject mismatch, or establish one deterministic server-owned logical call id at orchestration scope and apply it consistently. Preserve backward compatibility and add a regression test.

7. Coverage quality
   - Add true compact multi-batch tests where history is actually compacted.
   - Cover wrong repair batch id, ownerless/cross-batch sources, feedback payload reduction, absence of the 128 limit, provenance mismatch, SDK retry setting, and `finish_reason="length"`.
   - Re-run focused protocol tests, compile checks, and diff checks. Do not claim the LibreOffice failures are fixed unless you actually address them within authorized scope.

Before editing, inspect the independent review at `runs/execution/phase5-slice58-structured-output-runtime-20260824/worker_03.md` and the current diff in the authorized files. Preserve unrelated existing changes. Return a full revised execution report in the required schema; the runner will persist it to the new round-two report path.
