I'll re-read the patched modules and check validation, dataflow, and reconstruction against the owner decisions.Next I’ll inspect the reconstruction metadata additions and whether they change historical job hashes.I have the reconstruction and type-boundary evidence; next I’ll confirm one route-field mismatch against `route_identity()` and then return the labeled verdict.# Conference Output: r05-method-adoption-contract-20260914 - evidence_single_object

## Output

Same-session source follow-up. No edits, tests, DB, network, or issuance. Previous claim that `publish_frozen_review` is a clinical/professional enrollment signoff is **withdrawn**: saving this AI-assisted review run is not investigator enrollment signoff and does not mean the subject is eligible.

**Source verdict: PASS** for the stated validation-only patch (typed binding evaluation, no auto-approval, reconstruction hashes preserved, no API/issuance). One narrow **FAIL** in new route typing. Receipt completeness and user-consent authentication remain **UNVERIFIED** by owner decision, not by this patch claiming them.

---

### Evidence

| ID | Status | Observation |
|---|---|---|
| E1 | **PASS** | Typed kind is `evaluation_kind="binding_semantic_correspondence"` only (`review_method_adoption.py:64-66`). Reader loads `evaluation_manifest`, not page-read scores (`review_method_evidence.py:8-14`). `ARTIFACT_KINDS` adds `evaluation_manifest` / `method_approval` / `approval_source` (`artifacts.py:20-23`). |
| E2 | **PASS** | Metrics are generic `name/definition/value/unit/unavailable_reason`; missing value cannot be stored as zero (`review_method_adoption.py:47-61`). No mandatory `union_recall` / extraction fields. |
| E3 | **PASS** | Candidate vs qualification identities are separate fields and separate route maps (`review_method_adoption.py:24-37, 40-43`). `model` is `Text`, no name whitelist. |
| E4 | **PASS** | Publication is `frozen-review-publication/v2` (`frozen_review_publication.py:30`). It parses stored approval+manifests and compares **current** `PUBLICATION_VERSION`, `EVALUATOR_VERSION`, and the auth’s consumer version (`:73-82`). Old ephemeral `{version, evaluator, consumer_versions, evaluation_evidence}` hash is gone. |
| E5 | **PASS** | Qualification consumer parses the manifest and compares reconstituted candidate/qualification contract/prompt/summary/routes plus consumer algorithm (`qualified_binding_selection.py:269-283`). |
| E6 | **PASS** | `candidate_method` is only returned from reconstruction (`binding_qualification_support.py:708-714, 1039`). Payload equality still uses the old key set (`:961-976`). It is not written into job payload or summary hash. |
| E7 | **PASS** | False adoption flags unchanged (`qualified_binding_selection.py:448-450`). No writer for approval/gates in these files. `review_method_evidence.py:1` never creates approval. No API import of these symbols. |
| E8 | **PASS** | Approval source is existence-read only (`review_method_evidence.py:27`). Same-family methods across manifests in one approval are rejected (`:36-39`); within one manifest, duplicate families/metric names are rejected (`review_method_adoption.py:76-80`). Naive timestamps rejected (`:81-82, 99-100`); eval created after approval rejected (`review_method_evidence.py:34-35`). |
| E9 | **PASS** | Import graph is acyclic: `review_method_adoption` is a leaf; `review_method_evidence` does not import publication/consumer; consumer and publication import the reader. `app/domain/contracts/__init__.py` does not import the new module. |
| E10 | **FAIL** | `EvaluatedRoute.fallback_base_url: str \| None` (`review_method_adoption.py:21`) vs frozen job identity `route_identity()` which always copies `PageReaderRoute.fallback_base_url: str = ""` (`page_review_job_service.py:68-73`; `page_review_harness.py:93`). Consumer uses strict dict equality (`qualified_binding_selection.py:282-283`). JSON `null` validates then can never match current job routes (`""`). |
| E11 | **UNVERIFIED** | Candidate receipts still check only `model` and `reasoning_effort` (`binding_qualification_support.py:411-416`). Payload `candidate_routes` equality is not receipt `route_identity` completeness. Qualification still uses `require_route_receipts=True` (`:1015`). |
| E12 | **UNVERIFIED** | `approval_source` bytes are not an authenticated consent object (`review_method_evidence.py:27`). `scoring_report_sha256` is still untyped `raw_response` (`:13`). |

---

### Inference

The previous pose-as-approval hole (any `raw_response` SHA) is **closed on the method-evidence path**: publication and the qualification consumer now require parseable `evaluation_manifest` bytes. That was the defect this patch was supposed to fix.

Layer split matches the owner decision: human approval body is `ReviewMethodApproval` behind `review-method-adoption`; per-job `QualificationAdoptionAuthorization` is still caller-supplied and still requires a stored ACCEPTED gate (`qualified_binding_selection.py:112-121`). Issuance and service-reconstructed per-job tickets are **not in this patch**.

`candidate_method` is additive runtime metadata. Historical reconstruction equality does not see it, so this is not a regression on old job/summary hashes.

E10 is a **new** contract/dataflow error, not pre-existing next work: the new type allows a value the live frozen identity never produces.

Saving a frozen review remains an AI-assisted official **run record**, distinct from (a) method adoption for calculation and (b) professional enrollment signoff. Do not treat `assessment-publication-gate` `ACCEPTED` as either.

---

### Recommendation

- Treat this patch as **validation-only PASS**. Do not mark the adoption chain complete. Do not enable HTTP. Do not issue gates/artifacts in this round.
- Before issuance: store `fallback_base_url` as the same `str` `route_identity()` writes (empty string, not null), or normalize `None`↔`""` at compare time. That is a typing fix, not a new threshold and not a user-decision gate.
- Next implementation (already scheduled, not a regression): explicit approval issuance; owning service reconstructs per-job authorizations; publication should stop requiring a client-assembled authorization blob.
- Do not encode 0.95 / silent-miss floors into this validation code. Metrics stay named observations. Additional thresholds wait for final evaluation as already planned.
- Do not call candidate route metadata equality a completed receipt proof (E11). Do not call `approval_source` user-consent authentication (E12).

---

### Uncertainty

- No tests/runtime in this pass: JSON datetime UTC round-trip and `canonical_hash(approval.model_dump(mode="json"))` vs stored bytes were not executed (**UNVERIFIED**, not a source contradiction).
- Whether predicate and control share one manifest or two is allowed by `methods` + approval-level unique families; no gold exists yet.
- Physical A/B deployments, gold hashes, and observed metric values do not exist; this patch correctly does not invent them.

---

### Pre-existing next work vs this-patch regression

| Item | Classification |
|---|---|
| No approval issuer; no per-job service reconstruction; caller still supplies `QualificationAdoptionAuthorization` | Pre-existing next work |
| Candidate receipt still lacks full `route_identity` | Pre-existing next work; **must not** be treated as proved by `candidate_method` equality |
| `accepted=false` on qualification/selection/calculation | Unchanged, not a bug |
| `fallback_base_url` `None` vs `""` | **Regression/defect in this patch’s new type** (E10) |
| Replacement of untyped `raw_response` eval SHA by typed manifest | This patch, **PASS** |
| `PUBLICATION_VERSION` v2 / request hash change | This patch; no issued receipts to migrate |

---

### Objections / decision points for Codex

1. E10 should be fixed when writing the issuer, not by blocking this validation patch or by waiting for evaluation numbers.
2. Overall chain is **not** complete: validation without issuance is exactly the owner scope.
3. No further bounded question required for construction to continue on the disabled validation path.
