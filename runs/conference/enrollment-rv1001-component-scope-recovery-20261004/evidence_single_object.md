# Conference Output: enrollment-rv1001-component-scope-recovery-20261004 - evidence_single_object

## Output

### Role, method, and limitations

- **Declared fallback:** `pi` / `openai-codex` / `gpt-6.1-sol`, role `evidence_single_object`.
- This is my independent bounded advisory pass. No Grok Build session or Grok inference was performed; no other participant’s perspective was incorporated.
- Verification performed: read-only SHA256 commands and inspection of affected definitions and synthetic tests.
- No edits, report-file writes, test execution, application execution, clinical-file reads, database access, credentials, network/provider calls, recursive delegation, or visual acceptance.
- Findings below distinguish observed code from static counterexamples and unresolved dependencies. Counterexamples were **not executed**.
- No final Codex acceptance or clinical/regulatory authority is claimed.

### Frozen evidence

All five supplied SHA256 values matched current bytes:

| File | SHA256 |
|---|---|
| `app/services/protocol_scope_review_service.py` | `8f53cdb16df62ec3be5beb21363a2d2c3083bb5fd758b25dabb4d8c5b7b0f3b7` |
| `app/protocols/official_scope_review.py` | `31ad4c1339430d195bb8cc1e4c4099a6de663807ccb08d6d6f2eadacf61118f4` |
| `app/protocols/deconstruction_gate.py` | `96e7bfac758bc61decead2338ccf0076d806754a1022c0a22b6d1800b5bf3beb` |
| `tests/v2/protocols/test_official_scope_review.py` | `1e0a5245841ee69b26206988d0b75b43ab81eac9e39fac1aace1db8e368bbe03` |
| `app/agents/protocol_semantic_transport.py` | `1b33cee27a819dfc212331a6e695ffcfafbe23b214042c1ca94a2eabcdb18207` |

Required contract dependencies were inspected completely and independently fingerprinted; no supplied frozen values existed for them:

- `app/domain/contracts/protocol_scope_review.py`: `22f1405cf90180c7b64541bda763115760ae14a85c74a20b3903ed77ff0d8abf`
- `app/llm/logical_call_budget.py`: `4c4bfa14fe4a472f7679bcc4e98d1b2f7cc15781fd71b674a44ff0947051fe31`

The mandatory runtime memory summary was also read. It was not used as evidence for current-code behavior. No additional production files were opened.

### Assessment

**Component-local rejection handling is structurally fail-closed in the inspected gate path. SAME-allowance recovery is not fully proven by this service: it verifies task-ID equality and request membership, but not continuity of the authoritative latest allowance. Original run-allowance continuity is not checked.**

A valid sibling receives scope clearance only after replaying both receipts, verifying whole-target coverage, checking model consistency, and requiring distinct session IDs. The rejected sibling still produces a publication-blocking issue. This is an engineering scope clearance, not publication of the sibling or any patient decision.

### Findings

#### F1 — High: task-ID equality and request membership do not prove an unreset original allowance

**Evidence**

`app/services/protocol_scope_review_service.py:50–68` checks:

- saved/current `logical_task_id` equality;
- saved options against current options, excluding messages;
- receipt wire hash against allowed request variants;
- matching hash/token reservation in both saved and current request lists.

It does **not** compare allowance ceilings, `contract_sha256`, complete ledger continuity, or the current object against an authoritative latest persisted record.

`app/llm/logical_call_budget.py:27–43` validates continuity when `saved` is supplied. Construction with `saved=None` creates an empty ledger. `app/agents/protocol_semantic_transport.py:463–465` accepts a supplied budget through `share_call_budget`.

**Static counterexample — inference, not executed**

1. Original allowance `T`, two requests, records successful source reservation `H`.
2. Its source response contains snapshot `[H]`.
3. A later proposal dispatch reserves `F` and fails. The original allowance is now exhausted: `[H, F]`.
4. A replacement budget is constructed with the **same** task ID and ceilings, without restoring the latest ledger. Only `H` is copied into it.
5. Source restoration sees matching task IDs and `H` in both snapshots.
6. Preflight sees one remaining request in replacement `[H]`, allowing another proposal despite exhaustion of original `[H, F]`.

The existing “foreign allowance” case rejects a **different task ID**; it does not cover this same-ID reset.

**Impact**

The service proves reservation membership in the supplied current budget, not that this is the original, unreset allowance. A trusted caller may supply that guarantee, but this pass cannot establish it from the inspected entry point.

**Bounded remedy**

Recover against the authoritative latest persisted ledger for the original allowance; fail closed if that ledger is missing. Validate immutable allowance identity, ceilings, contract identity, and append-only continuity. A receipt’s source-time snapshot is historical evidence, not the latest authority on remaining requests.

Comparing current state only to that historical snapshot would still miss later consumed requests.

**Question for Codex**

What authorized caller/storage invariant prevents reconstruction of the same task ID with a truncated ledger? Please provide the relevant bounded definitions if this guarantee is intentionally external to the service.

---

#### F2 — High: original run allowance can be replaced or omitted during restoration

**Evidence**

- Restoration reads only `metadata["logical_call_budget"]`: service `:51–68`.
- Preflight checks whatever run budget is currently attached and skips `None`: service `:79–86`.
- Transport records both budget snapshots: `protocol_semantic_transport.py:467–470`.
- Actual dispatch reserves both attached budgets: transport `:479–481`.

**Static counterexample — inference, not executed**

Keep the legitimate original scope budget with source reservation `H`. Replace an exhausted original run budget with a fresh run budget, or set it to `None`. The service does not compare saved and current run identity, contract, or reservation history. It can proceed under the replacement/absent run allowance if the scope budget has room.

**Impact**

Scope-budget identity alone does not prove that the proposal remains inside the original overall authorization.

**Bounded remedy**

When the source receipt records a run budget, require restoration of that same authoritative run allowance and validate its identity, contract, ceilings, and ledger continuity. Explicitly distinguish “originally no run budget” from “original run budget missing during recovery.”

**Question for Codex**

Is retaining the original run budget mandatory for this recovery contract? Safe provisional interpretation: yes whenever the source call recorded one; missing or foreign run state blocks recovery.

---

#### F3 — Medium: the recovery test does not exercise real reservation timing or proposal allowance consumption

**Evidence**

In `test_saved_source_read_resumes_only_the_remaining_proposal_in_original_allowance`:

- The synthetic wrapper obtains a response **before** reservation: tests `:515–525`.
- `ScopeReader.start` raises the second-call timeout before reservation: tests `:83–86`.
- The resumed reader is an ordinary `ScopeReader`: tests `:536–538`.
- Ordinary `ScopeReader.start` neither reserves a budget nor emits budget-binding metadata: tests `:83–114`.
- Success assertions check prompt count and receipt stage, not final allowance consumption: tests `:564–569`.

Real transport instead reserves before dispatch, including failed/unknown upstream attempts: transport `:765–773`; budget `:45–58`.

The real-transport test at `:316–341` covers an ordinary two-read flow and exhausted restart, not saved-source restoration.

**Inference**

The synthetic test’s “proposal timeout then one remaining call” does not represent a timeout after actual proposal dispatch with a two-request allowance. Such a dispatch consumes the second reservation; real recovery must then block.

Adding streaming flags to a synthetic hash also does not exercise `_send_completion` during restoration.

**Bounded remedy**

In a separately authorized execution/edit round, exercise real transport with an offline injected client:

1. Restore after source persistence **before proposal dispatch**: exactly one proposal dispatch, with both original ledgers advancing.
2. Restore after proposal dispatch timeout: zero further dispatches.
3. Attempt same-ID ledger truncation and run-budget substitution: zero dispatches.

These distinguish recoverable host interruption from an already-spent, unknown upstream attempt.

---

#### F4 — Medium, conditional: all-rejected answers abort before replacing prior clearance

**Evidence**

The service raises when every item is rejected:

- restored source: service `:69–71`;
- newly returned stage: service `:106–110`.

Manifest attachment and replacement of previous clearance happen later: service `:113–123`.

By contrast, completed unresolved outcomes reach replacement, as represented in tests `:258–278`.

**Static counterexample — inference, not executed**

Start with a previously cleared draft. Obtain a schema-valid new reading in which every component fails component validation. The service raises before returning an updated disposition-bearing draft. The previous draft retains its old review reference.

**Uncertainty**

This is not proof that a production caller republishes the old clearance. Caller behavior was not inspected. It is a gap in establishing that newer rejected outcomes cannot leave old clearance active.

**Bounded remedy / decision**

Codex should define whether an all-rejected reading is:

- a completed rejection outcome that supersedes current clearance; or
- an aborted review that must separately mark the current work unit blocked.

Historical revisions should remain unchanged under either choice. The safe provisional path is to prevent reuse of old clearance for the work unit receiving the newer rejected result.

### Verified structural protections

These are code observations, not executed acceptance results.

| Requirement | Evidence and conclusion |
|---|---|
| Whole-target coverage survives component-local validation | `official_scope_review.py:140–144,267–270` require the full expected component set. `OfficialScopeReading.unique_targets`, contract `:63–68`, rejects duplicates. |
| Both receipts precede sibling release | Replay iterates exactly two stages with `zip(..., strict=True)`, validator `:295–305`. Component rejection is deferred until after receipt replay and model/session checks, `:306–311`. |
| Rejected sibling remains blocked | Rejection is a distinct exception/code, validator `:30–35,310–311`. Gate converts it to a blocking issue at `deconstruction_gate.py:2879–2889`. |
| Rejection remains distinct from source uncertainty | `OfficialScopeRejectedError` and `OfficialScopeUnresolvedError` have separate codes. Genuine unresolved/disagreement handling occurs at validator `:312–316`. |
| Full publication remains blocked | `_issue` defaults to `阻止发布`, gate `:117–137`; aggregation rejects blocking/check-required issues, `:1939–1944`. Valid sibling scope clearance does not override this. |
| Missing/extra receipts cannot release a sibling | Strict two-stage iteration fails before a stage set is returned, validator `:295–321`. Missing receipt keys likewise fail closed in replay. |
| Frozen prompt and source binding | Exact request envelope and messages are checked, validator `:245–252`. Basis binds source/proposal state, validator `:38–101,288–292`. |
| Requested/reported model and terminal state | Receipt validation requires final `stop`, model agreement, and message-hash agreement, validator `:253–262`. Cross-stage requested model consistency is checked at `:306–307`. |
| Distinct sessions | Required at validator `:308–309`; real `start` creates fresh UUID-based session IDs, transport `:1075–1079`. This proves separate local histories, not independent model reasoning. |
| Actual streaming reservation | Transport adds streaming options, reserves, then dispatches, `:763–773`. Receipts record the reserved full-options hash, `:855–866`. |
| Different-ID copied allowance | Service `:62–67` rejects it. Same-ID reset remains F1. |
| Exhausted supplied allowance | Service `:83–86` and budget `:49–51` block further requests. This relies on authentic latest ledger state. |
| Changed source/model | Frozen request/basis and current-option comparisons reject changes represented in those fields. Actual provider identity remains receipt-based, not independently attested. |

### Byte-integrity uncertainty

**Evidence**

`read_scope_receipt` parses bytes supplied by `read`, checks request/response fields, and validates the reading. It does not itself recompute a digest from the artifact reference: validator `:243–264`.

Corruption tests overwrite receipts with structurally invalid JSON objects: tests `:172–176,491–502`. Those cases establish intended structural rejection, not detection of every parseable byte alteration.

**Uncertainty**

`ArtifactStore.read` was outside the authorized production read list and was not inspected. Therefore I cannot establish the unconditional statement **“corrupt receipt bytes never release any component.”**

**Conditional counterexample**

If the reader returns modified bytes without digest verification, a parseable alteration that preserves required metadata and produces a valid reading can pass this layer. If the reader verifies content-addressed bytes, that alteration should instead fail before parsing.

**Bounded question and safe path**

Does the authorized reader verify the stored bytes against each reference’s digest on every read, including manifests, requests, and responses? Please explicitly authorize the relevant `ArtifactStore.read` definition for a follow-up if a byte-level conclusion is required. Until then, require a hash-verifying reader and qualify the integrity claim accordingly.

### Decisions requested from Codex

1. Identify the authoritative latest ledger and the invariant preventing same-ID resets.
2. Require original run-allowance continuity when recorded by the source call.
3. Define whether all-rejected completed readings supersede clearance directly or trigger a separate current-work-unit block.
4. Supply or authorize the byte-verifying reader contract.

**Most important objection:** request membership plus task-ID equality is weaker than SAME-allowance recovery. The safe alternative is recovery from the original authoritative latest ledgers, without reconstructing, truncating, or replenishing them.

### Unperformed checks and continuation point

- No synthetic tests or static counterexamples were executed.
- No actual application, streaming/provider request, persistence transaction, restart, or concurrent recovery was exercised.
- Caller-side authorization and persistence ownership were not inspected.
- Artifact byte-digest enforcement was not inspected.
- No clinical meaning, patient decision, visual correctness, or final acceptance was assessed.

A targeted same-session follow-up can resolve the ledger-authority and byte-integrity questions once Codex supplies the bounded definitions. No report file or sibling output file was created.
