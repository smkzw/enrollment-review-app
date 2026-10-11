Independent read-only review pass. Loading the conference context and main-venue plan first.Main-venue plan is mostly stubs; auditing the designated source files against the four review axes.Worker path failed; reading the design section and executor/harness/tests directly.I have enough evidence for the four review axes. Drafting the independent conference report next.

# Conference Participant Output: r3-targeted-durable-review-20260906 - general_single_object

## Boundary Check

- Role: `general_single_object` / `pi` / `cursor` / `default`; read-only engineering audit only.
- Worked only inside the runner-bound workspace `.`.
- Read set used: conference context, main-venue plan (mostly TODO stubs), designated app/domain/service/API/test sources, and design authority `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` (§2026-09-06 targeted proposal + §16 investigator-missing confirmation).
- Did **not** edit application/source files, did **not** write `runs/conference/.../general_single_object.md`, did **not** call models, did **not** read product data / credentials / raw clinical documents.
- No clinical, UI, browser, or regulatory acceptance claimed.
- Trellis task-creation consent is out of scope for this conference pass; no Trellis task was created.

## Independent Work Product

### Objective audit (what must be true)

User-approved / design-backed invariants for this frozen change:

1. **Durable round ceiling = 2 business rounds** (transport/length retries separate).
2. **Source/context binding**: page image, episode, original reconciliation/conflict, routes/effort, prompt identity.
3. **No automatic fact acceptance / no rewrite of original reconciliation or coverage**.
4. **Failure ≠ missing investigator written judgment**; investigator-missing is a nonblocking report finding only when reads/coverage are valid; this packet claims **factual-conflict reread only**, not clause/report judgment flow.

### Finding matrix (evidence → inference → recommendation)

| ID | Severity | Evidence | Inference | Recommendation |
|---|---|---|---|---|
| F1 | **High (productization / future misuse)** | `compare_targeted_reads` always returns `candidate_auto_accept: False` (`app/domain/targeted_page_review.py:56-57`). Focused reads **skip** `save_review` (`page_review_job_executor.py:155-159`). Durable test asserts original coverage unchanged and targeted job has no coverage checkpoint (`test_targeted_page_review_jobs.py:84-85`). But round-1 full agreement yields `requires_user_review=False` (`targeted_page_review_executor.py:74-75`) while still emitting `agreed_candidate_targets`, and final `compare:2` is just `{**previous, "round_skipped": True}` (`:55-56`). | Persistence “no auto-accept” is currently enforced by **non-write + boolean**, not by a typed outcome that forbids treating agreement as accepted facts. A later UI/report consumer can easily misread `!requires_user_review && agreed_candidate_targets` as “resolved/accepted”. | Add an explicit durable outcome discriminant on compare checkpoints, e.g. `outcome_kind ∈ {conflict_preserved_read_failed, conflict_pending_user, candidate_agreement_unaccepted}` and keep `candidate_auto_accept=false` as redundant hard guard. Never map agreement to coverage/reconciliation mutation without a separate approved policy packet. |
| F2 | **High (boundary separation)** | Design §16: model failure / incomplete coverage must **not** be reported as verified investigator-judgment absence. Targeted path only prompts “不补写研究者判断” (`page_review_harness.py:505-507`) but still accepts full `PageReviewPayload.clause_signals` into `auxiliary_review` (`page_review_harness.py:610-611,665` + executor checkpoint). Compare logic ignores clause_signals and only handles factual targets; there is **no** `read_failures` vs `investigator_judgment_absent` type, and **no** test asserting that separation. Context itself says clause/report judgment flow is not implemented. | Separation is mostly **by omission + prompt text**, not by contract. The dangerous failure mode is downstream: someone later scans auxiliary `clause_signals` / “未见判断” text from a failed or one-sided reread and treats it as §16-qualified investigator-missing. | Freeze a machine-checkable rule: targeted job outcomes may emit only factual conflict outcomes + `read_failures`; **forbid** promoting auxiliary `clause_signals` / investigator-absence claims into report findings. Prefer stripping or ignoring `clause_signals` under `review_focus`, or tagging records `auxiliary_factual_reread=true` with consumer deny-list. Add a unit test: lane failure ⇒ `read_failures` present, no investigator-missing finding. |
| F3 | **Medium (ops / durable ceiling side door)** | Idempotency key is only `r3_targeted_page_review:{reconciliation_id}` (`targeted_page_review_jobs.py:84-86`). Executor fails closed on route/prompt drift with `TARGETED_REVIEW_CONTRACT_CHANGED` (`targeted_page_review_executor.py:29-32`), but a **completed** job is what re-enqueue returns (`test_targeted_page_review_jobs.py:87-89`). | Round budget is well capped **inside one job**, but contract/model fingerprint is **not** part of idempotency. After route/prompt change, operators can be stuck with a stale completed auxiliary job and cannot start a new 2-round budget without manual store intervention. | Include `TARGETED_REVIEW_VERSION` + `base_prompt_version` + route identity hash in idempotency key / supersede rule when fingerprint differs; keep same-fingerprint replay no-op. |
| F4 | **Medium (cueing vs declared independence)** | Round 2 builds `candidate_excerpts` from both lanes’ raw `region.excerpt` for pending fields (`targeted_page_review_executor.py:60-64`) and sets `candidates_visible` (`page_review_harness.py:509-513`). Design allows second-round excerpts if visibility is marked, and warns not to treat prompted convergence as blind evidence. | Implementation matches “excerpts allowed + visible flag”, but excerpts are **answer-like raw snippets from both models**, not anonymized disagreement packs. This increases convergence bias and weakens later claims of independent confirmation. | Keep as eval-only cueing: store excerpts under an explicit `cue_kind="prior_excerpts_visible"`; consider anonymized/diff-only packs before any product claim of “两路独立核实后一致”. Do not upgrade `agreed_candidate_targets` after visible cues to a stronger evidence tier than blind round 1. |
| F5 | **Low/Medium (audit clarity)** | On round-1 `read_failures`, compare keeps all targets pending and sets `read_failures` (`targeted_page_review_executor.py:67-70`); round 2 short-circuits (`:55-56`). Good clinically. Final checkpoint may still carry `round_number=1` inside a `compare:2` receipt after skip. API returns only job submit state (`page_review.py:25-42`), no targeted status projection for `read_failures` / pending / agreed. | Failure preservation is correct in the executor, but observability is checkpoint-tribal; easy for humans to confuse “models still disagree” with “reread failed”. | Publish a read-only targeted status DTO with mandatory fields: `round_budget=2`, `rounds_executed`, `read_failures`, `pending_targets`, `agreed_candidate_targets`, `candidate_auto_accept=false`, `requires_user_review`, `original_reconciliation_id`. |
| F6 | **Process** | Main-venue plan file is almost entirely `TODO`; design section title still says “隔离验证，未接入” while API/runtime wiring exists. | Chair packet under-specified; stale design label can mislead reviewers about production posture. | Codex should refresh plan checklist against this freeze and annotate design header as “code wired for factual conflicts; judgment/report path not claimed”. |

### What looks solid (should not be “fixed” away)

- **Round ceiling**: steps only for rounds `(1,2)` (`targeted_page_review_jobs.py:75-82`); `PageReviewFocus.round_number: Literal[1,2]` (`page_review_focus.py:14`); API forbids client `round_number` (`page_review.py:25-28`, API test 422).
- **Blind round 1**: rejects preloaded excerpts/ids (`page_review_focus.py:32-33`); harness `candidates_visible is False` when empty (`test_targeted_page_review.py:71`).
- **Source binding**: enqueue checks job type/completion, authority subject/episode, page index, reconciliation id, page artifact, clause pack, image sha, explicit conflicts (`targeted_page_review_jobs.py:40-68`); harness rechecks image sha + episode + MAIN/high only (`page_review_harness.py:496-503`).
- **No original rewrite**: focused path does not `save_review` / save coverage; durable test locks this.
- **One-lane failure does not clear conflict**: failure branch restores pending targets and records `read_failures`; round 2 skipped on failures.
- **Transport retries ≠ extra business rounds**: step `max_attempts=2`, harness one length doubling; durable test shows 2 model calls if round 1 agrees, 4 if not.

### Highest-impact defect / uncertainty

**Highest impact:** F1+F2 together — the freeze correctly avoids writing facts today, but the **outcome taxonomy is too weak** to protect the user boundary once anything consumes checkpoints/API. Agreement is under-typed; investigator-missing is prompt-only and not deny-listed against auxiliary payloads.

**Concrete remediation (design-level, no code edits in this pass):**

1. Introduce a closed `TargetedReviewOutcome` contract persisted on `compare:*` checkpoints.
2. Map executor branches explicitly:
   - any `read_failures` → `conflict_preserved_read_failed` (never investigator-missing)
   - pending after round 2 → `conflict_pending_user`
   - agreement → `candidate_agreement_unaccepted` with `candidate_auto_accept=false` and **no** coverage mutation
3. Under `review_focus`, either drop `clause_signals` from auxiliary records or mark them non-authoritative for report/judgment projection.
4. Extend idempotency with contract fingerprint (F3).
5. Add tests currently missing: failure short-circuit; no investigator-missing emission; agreement does not set any accept/write flag; API/status exposes discriminant.

### Challenge to assumptions

- Assumption “`candidate_auto_accept: False` is enough” is **necessary but not sufficient** without a positive outcome enum and consumer contract.
- Assumption “not implementing judgment flow ⇒ separation satisfied” is only safe if auxiliary artifacts cannot be mistaken for judgment evidence; current `clause_signals` retention challenges that.
- Assumption “design §proposal still ‘未接入’” is **false for code**; treat docs as stale, code as the freeze under review.
- Assumption “round skip on agreement means clinically resolved” is **not** authorized by the auto-accept policy freeze.

## Evidence And Assumptions

### Evidence touched

- `app/domain/contracts/page_review_focus.py`
- `app/domain/targeted_page_review.py`
- `app/services/targeted_page_review_jobs.py`
- `app/services/targeted_page_review_executor.py`
- `app/services/page_review_job_executor.py`
- `app/services/page_review_runtime.py`
- `app/llm/page_review_harness.py` (focus prompt / identity)
- `app/api/v2/page_review.py`
- `tests/v2/services/test_targeted_page_review_jobs.py`
- `tests/v2/llm/test_targeted_page_review.py`
- `tests/v2/api/test_page_review.py` (targeted cases)
- `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` (2026-09-06 proposal + §16)
- Owner test claim from context (“96 passed, 5 warnings”) **not re-executed** in this pass.

### Assumptions

- Codex freeze scope is factual targeted reread only; clause/report investigator-missing projection remains unimplemented and must not be silently inferred as done.
- Immutable reconciliation IDs / coverage predecessor model remain as currently implemented.
- No hidden writer outside these files persists agreed auxiliary facts (search found no other `agreed_candidate` consumers in `app/`).

### Uncertainty

- Whether product intends round-1 agreement to suppress user confirmation entirely (design text can be read that way) while still forbidding auto-accept; needs Codex policy clarification (Q1 below).
- Whether any not-yet-merged report projector will read `auxiliary_review.clause_signals` (Q2).

## Risks, Gaps, And Verification Needs

1. **Missing tests:** lane-failure → round2 skip + conflict preserved; no false investigator-missing; status/API discriminant; contract-fingerprint supersede.
2. **No targeted job status API** — submit-only surface increases misuse risk of raw checkpoints.
3. **Do not treat owner unit pass count as clinical or judgment-boundary acceptance.**
4. **Verification Codex should own later:** consumer search for `auxiliary_review` / `agreed_candidate_targets`; confirm no profile/facts writer path; optional controlled failure-path job replay in non-prod.

### Objections / decision points for Codex

1. Is `agreed_candidate_targets` allowed to clear `requires_user_review` without a separate human/report policy object?
2. Should focused reads be schema-constrained to facts-only (no authoritative `clause_signals`)?
3. Should idempotency incorporate route/prompt fingerprint now, or is ops manual supersede acceptable for this freeze?
4. Please correct design doc “未接入” label if this freeze is considered code-complete for factual conflicts.

### Bounded questions for Codex (blockers for stronger conclusions)

- **Q1:** For this freeze, is round-1/round-2 **candidate agreement** supposed to remain user-visible as “辅助一致、仍未采信”, or is silent suppression of user review intentional? *Matters because `requires_user_review=false` on agreement is the main future auto-accept footgun. Provisional path: treat agreement as `candidate_agreement_unaccepted` only.*
- **Q2:** Is any in-flight report/clause consumer authorized to read targeted `auxiliary_review.clause_signals`? *Matters for F2. Provisional path: deny-list until judgment packet exists.*

## Recommended Next Step

1. Codex chairs synthesis against F1/F2 first; do not spend edit budget on cosmetic refactors.
2. If Codex concurs, authorize a **narrow contract follow-up** (outcome enum + focused clause_signal policy + failure test) — still no auto-accept writer.
3. Refresh main-venue plan TODOs and design “未接入” wording to match the factual-only freeze.
4. Keep investigator-missing nonblocking behavior in the **clause/report** packet, explicitly disconnected from targeted read_failures.
5. I can take a same-session follow-up to draft the outcome contract shape or test matrix only if Codex authorizes that scope; still no application edits unless an edit round is opened.
