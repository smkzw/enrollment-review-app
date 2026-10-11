I'll start with the assigned context and plan only, then do a bounded read-only pass on the R06 source-inheritance paths.Retrying with the local file reader for the assigned context and plan.Next I’ll inspect the publication service, repository same-run checks, and the later-run source-preservation test.I'll search the publication and repository code for same-run validation and source-inheritance paths next.I have enough evidence for the failure mode and inheritance-proof design; composing the bounded worker report now.# Execution Output: r06-source-inheritance-20260913 - worker_01

## Boundary And Context Check

- Read only authorized inputs: `context/r06-source-inheritance-20260913_execution_context.md`, `plans/codex_execution_r06-source-inheritance-20260913.md`, plus SoT sources `app/services/fact_publication_service.py`, `app/storage/fact_repositories.py`, `tests/v2/services/test_fact_publication_service.py`, and adjacent contracts/correction paths.
- No application/file edits, DB access, model calls, network, installs, or test execution.
- Shared dirty tree left untouched.
- This report is evidence for Codex, not acceptance or production write authority.

## Work Performed

### Evidence: same-run repository gate

`_PublishMixin._validate_publication_group` (`app/storage/fact_repositories.py` ~865–920) currently forces every published provenance item onto the **current run**:

1. Primary gate via `_validate_common` must have `gate.run_id == run_id` and accepted `TRANSACTIONAL_PUBLISH`.
2. Every `gate_ids` member must have `gate.run_id == run_id`.
3. Every `source_candidate_ids` member must have `candidate.run_id == run_id`.
4. `gate_ids` ↔ `source_candidate_ids` must be 1:1.
5. `locator_ids` must equal the locator union of those candidates only.

`ClinicalFactV2Repository.create` (~1174–1224) then re-derives requirements / record_time / assertion_basis / source_strength from that same candidate set.

### Evidence: later-run source loss in publication service

`FactPublicationService._publish_facts` (~406–433) only uses **current-run** accepted candidates:

- `source_candidate_ids` / `gate_ids` = `_publication_ids(group, gates)`
- `locator_ids` = `_locator_union(group)`
- `supported_requirement_ids` = `_requirement_union(group)`
- `existing` is used only for lane-conflict rejection and `_next_revision`, **not** provenance merge

So a later run that republishes the same `stable_identity` under the same authority always appends `revision = head+1`, but drops prior verified locators / candidates / gates / requirements.

Events/exposures mirror the same current-run-only provenance assembly (`_publish_events` ~496–525, `_publish_exposures` ~558–589).

### Evidence: failing contract already encoded as strict xfail

```619:717:tests/v2/services/test_fact_publication_service.py
@pytest.mark.parametrize("same_lane", [
    False,
    pytest.param(True, marks=pytest.mark.xfail(
        strict=True,
        reason="R06: later publication drops earlier verified source and requirement closure",
    )),
])
def test_later_run_preserves_fact_identity_and_sources(...):
    ...
    assert set(original.locator_ids) <= set(current.locator_ids)
    assert set(original.supported_requirement_ids) <= set(current.supported_requirement_ids)
    assert set(original.source_candidate_ids) <= set(current.source_candidate_ids)
    assert set(original.gate_ids) <= set(current.gate_ids)
```

`same_lane=False` remains a positive control for profile-lane conflict rejection.

### Correction / authority invariants that must survive

- Publication already excludes superseded entities via `FactCorrectionRepository.list_by_authority` (`fact_publication_service.py` ~201–215).
- Corrections are append-only lineage with no branch (`fact_correction_repository.py` ~169–204).
- Fact identity excludes locators (`ClinicalFactV2` docstring / validator); multi-source merge is expected to keep locator closure.
- Event/exposure locator closure is fact-bound (`_require_locators_within_facts`, ~1061–1071; P5-R06 comment at file header).

### Alternatives compared

| Approach | Verdict |
|---|---|
| **A. Explicit inheritance proof** (recommended) | Keep same-run validation for current provenance; allow prior provenance only when proven from non-superseded same-authority/same-identity chain head. Matches test contract without relaxing cross-run attachment. |
| B. Naive union of any same-authority candidates/gates | Reject. Bypasses correction supersession, allows cherry-picking, weakens source closure. |
| C. Keep candidate/gate IDs current-run only; inherit locators only | Reject vs current test/contract: asserts `source_candidate_ids`/`gate_ids` subsets too. |
| D. Soften repository to “same authority” for all provenance | Reject. Destroys current-run final-gate invariant and replay integrity. |

### Minimal implementable design (no code applied)

**Definition — current provenance set**

- All accepted final-gate candidate/gate pairs from the **current** `run_id` that form the published identity group.
- Must continue to pass today’s same-run checks.

**Definition — inherited provenance set**

- Exact `source_candidate_ids`, `gate_ids` (or `[gate_id]` fallback), `locator_ids`, and `supported_requirement_ids` from the **prior non-superseded head** entity with:
  - same `authority`
  - same `stable_identity`
  - `prior.revision + 1 == new.revision`
  - prior entity id present in publication `existing*` after supersession filter
- No subsetting / no adding foreign prior IDs.

**Definition — explicit inheritance proof**

Carry a publish-time proof object (service → repository), e.g.:

- `prior_entity_id`
- `prior_revision`
- `inherited_candidate_ids`
- `inherited_gate_ids`
- `inherited_locator_ids`
- `inherited_requirement_ids` (facts only)

Repository proof checks before create:

1. Load prior entity; kind/authority/`stable_identity` match.
2. Prior not superseded.
3. `published.revision == prior.revision + 1`.
4. Inherited ID sets **exactly equal** prior entity published sets (anti cherry-pick).
5. Current-run subset still validated with existing same-run rules.
6. Published totals = sorted unique union(inherited, current).
7. **Primary `gate_id` must remain a current-run accepted gate** (`gate_id ∈ current gate_ids`), even if inherited gates are present. Critical because `_validate_common` binds primary gate to `run_id`.
8. Locator closure equals union of **all** (inherited+current) candidate locator sets.
9. Source strength = max(prior published strength, current derived strength) under existing rank table.
10. Assertion basis / record_time use one deterministic merge policy (recommended: keep current-run representative for primary assertion unless inherited representative is required for locator membership; do not silently invent basis). Prefer documenting: representative remains `min(current-run candidates by candidate_id)` while inherited candidates only contribute closure/requirements/strength, **or** validate assertion_basis against full set with `min(all candidates)` — Codex must choose; full-set min better matches today’s create() but can flip basis text across runs when older candidate_ids sort first.

**Service change surface (minimal)**

In `_publish_facts` (and symmetrically events/exposures if Codex expands scope):

1. Select prior head from `existing` for identity.
2. If none → current behavior.
3. If present and semantics equal → attach inheritance proof and emit merged provenance fields.
4. Keep `run_id` = current run; keep immutable append (`revision` head+1 only).

**Serialization compatibility**

- No required contract schema change: reuse existing `source_candidate_ids` / `gate_ids` / `locator_ids`.
- Optional audit field `inherited_from_entity_id` is nice-to-have, not required to clear the xfail.

### Affected event/exposure consumers

1. `ClinicalEventV2Repository.create` / `MedicationExposureV2Repository.create` — locator must remain inside referenced fact locator closure; fact inheritance **expands** closure and prevents false P5-R06 rejects when later facts would otherwise drop earlier locators.
2. `_require_fact_candidate_reference_closure` — uses fact `source_candidate_ids`; inherited fact candidate IDs keep older event candidate references closable if same-run event candidates still cite them.
3. Conflict-group member provenance decoding paths that read member `source_candidate_ids`.
4. Correction impact / profile regeneration consumers that reverse-index by locator/entity — dropping locators on later revisions silently shrinks impact closure; inheritance preserves it.
5. Same bug pattern exists in `_publish_events` / `_publish_exposures`; fact-only fix clears the existing xfail, but event/exposure later-run source loss remains unless included.

### Positive / negative test checklist

**Positive**

1. Existing `test_later_run_preserves_fact_identity_and_sources[same_lane=True]` becomes non-xfail: identity stable, revision+1, prior locators/candidates/gates/requirements ⊆ current.
2. Same-run multi-candidate merge still works (`test_merged_locator_closure`).
3. Same-run replay unchanged (`_replay_if_published` candidate-set equality).
4. Later run with **no** prior head publishes current-only provenance.
5. Later run inherits then adds new locator → closure strictly grows, strength non-decreasing.
6. Event whose locators sit in inherited fact locators still publishes under `_require_locators_within_facts`.
7. After correction supersedes prior head, later auto-publish inherits from **new non-superseded head only**, never from superseded target.

**Negative**

1. `same_lane=False` still raises profile-lane conflict; prior fact unchanged.
2. Cherry-pick inherited subset (omit one prior locator/candidate) → repository reject.
3. Attach prior candidate/gate from different identity or different authority → reject.
4. Attach prior provenance without proof / with wrong prior revision (not head) → reject.
5. Primary `gate_id` set to inherited prior-run gate → reject.
6. Current-run gate not accepted `TRANSACTIONAL_PUBLISH` → reject (unchanged).
7. Inherit from superseded entity id → reject.
8. Locator list ≠ union(inherited candidates ∪ current candidates) → `FactLocatorReferenceError`.
9. Event borrowing locator from same-node **non-referenced** fact still rejected (P5-R06 unchanged).
10. Naive cross-run candidate with same authority but never on prior head → reject.

## Artifacts And Evidence

- Design only; no code/DB artifacts written.
- Key anchors:
  - `app/services/fact_publication_service.py`: `_publish_facts` 406–433; supersession filter 201–215; `_next_revision` 161–163
  - `app/storage/fact_repositories.py`: `_validate_publication_group` 865–920; fact `create` 1174–1245; `_require_locators_within_facts` 1061–1071
  - `tests/v2/services/test_fact_publication_service.py`: strict xfail R06 at 619–624; assertions 709–718
  - `app/storage/fact_correction_repository.py`: supersession / lineage 169–204, 341–342
  - `app/domain/contracts/facts.py`: `ClinicalFactV2` provenance fields 370–435

## Commands And Observations

- `wc -l` / `rg` over publication service, repositories, tests, correction contracts (read-only).
- Observation: R06 is already named in the strict xfail reason; root cause is service current-run-only assembly **plus** repository same-run provenance enforcement, not missing test intent.
- `pi-worker` invocation failed in this environment; continued with direct Read/Shell `rg`.

## Blockers Or Missing Environment

- None for read-only design.
- Codex decision needed before implementation:
  1. Assertion-basis merge policy: full-set `min(candidate_id)` vs current-run-only representative.
  2. Scope: facts-only (clears existing xfail) vs also events/exposures in the same change.
  3. Whether to add optional `inherited_from_entity_id` audit field.

## Rerun Requests Or Next Step

1. Codex chooses the three decisions above.
2. Implementation pass (separate execution): service merge + repository inheritance proof; remove/narrow the strict xfail; add negative proof tests from the checklist.
3. Allowed verification after implementation (Codex-authorized): focused `tests/v2/services/test_fact_publication_service.py` only — not done in this worker pass.
