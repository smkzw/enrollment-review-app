I'll start by acknowledging the Trellis context and then conduct the read-only review.

Trellis SessionStart ✓

Let me read the required source files.

# Conference Output: enrollment-reading-view-review-20260916 - evidence_single_object

## Output

**Role:** `evidence_single_object` · **Mode:** read-only, no source edits, no product/model calls, no clinical originals read, no benchmark/cost claims.
**Method:** direct source inspection of the declared read set plus the immediate consumers/guards reachable from it (`app/`, `frontend/src/`). I did not run tests (read-only pass) and did not read clinical material.
**Labeling below:** `FACT` = read from source at the cited line · `INFER` = my reasoning over that source · `REC` = recommendation · `UNCERT` = cannot verify in this pass.

---

### 0. Verification of the packet's own premises (before findings)

| Premise | Status | Evidence |
|---|---|---|
| `reading_view.py` is only used by an isolated experiment | `FACT`, with a correction | Zero importers in `app/` and zero references in `tests/` (two targeted greps for `reading_view\|ReadingView\|make_reading_view` over `app/` and over `tests/` returned only `app/evidence/reading_view.py` itself). Nothing in this worktree calls it — not even an experiment harness. Treat any experiment usage as **external, unverifiable from the repo**; do not cite it as product evidence. |
| Module is not formally activated | `FACT` | Same greps; no contract/ORM/repository/job reference anywhere. I will not report it as activated. |
| Explicit direction only; no auto-orientation | `FACT` | `reading_view.py:77-78` rejects anything that is not an explicit int in `(0,90,180,270)`; there is no orientation inference and no EXIF handling anywhere in the module. |
| Page-review observations' bbox has a live consumer | `FACT: no` | Only `region.excerpt` is consumed anywhere (`page_review_visual_locators.py:86`, `page_review_pending.py:62`, `targeted_page_review_detail.py:88,102`, `page_source_association.py:57`). The frontend consumes `bbox` **only from locators** (`EligibilityWorkbenchPage.tsx:455-456`, requiring `precision === "bbox" && authenticity === "authenticated"`). |
| Quarter-turn math is correct | `FACT` (arithmetic only) | See Finding F-3. This is **not** clinical acceptance. |

---

### 1. Ranked findings

#### F-1 (blocking) — A rotated page can be neither submitted nor persisted without breaking one of two existing integrity guards, both of which protect exactly the invariant the proposal wants to keep

- `FACT` `app/llm/page_review_harness.py:106-115`: `PageReviewInput.__post_init__` requires `page_image_sha256 == sha256(bytes actually sent)`, else `ValueError("页图像哈希与实际输入不一致")`.
- `FACT` `app/storage/page_review_repository.py:58-73`: `_verify_page` requires `record.page_image_sha256 == PageArtifactRecord.page_image_sha256`, else `ScopeViolationError("页级判读与页产物的资料版本、页码或图像哈希不一致")`.
- `FACT` `app/services/page_review_job_service.py:116-125` freezes `page_image_sha256 = artifact.page_image_sha256` into the job payload; `app/services/page_review_job_executor.py:97` reads exactly those bytes from the content-addressed store.
- **Reproducible defect (a):** send the rotated bytes with the source hash → fails at `page_review_harness.py:115`.
- **Reproducible defect (b):** set `page_image_sha256` to the view hash → fails at `page_review_repository.py:73`.
- `INFER`: therefore "keep the page artifact immutable + add a derived view identity" is **not** a `reading_view.py`-local change. The connected change set necessarily reaches the read input contract, the record contract, the repository verifier, and the job version dict.
- `REC`: never relax either guard. Add an explicit optional view binding to `PageReviewInput` (view present ⇒ source hash must match *and* sent-bytes hash must equal `view_image_sha256`), and add a **new** repository cross-check (`view.source_page_artifact_id == record.page_artifact_id`, `view.source_image_sha256 == page.page_image_sha256`) instead of loosening `_verify_page`.

#### F-2 (highest-impact, silent-corruption) — The coordinate contract is undeclared even in the base case, and nothing bounds `region.bbox`; a rotated read would persist view-space coordinates as source coordinates, permanently and undetectably

- `FACT` `app/domain/contracts/page_review.py:56-58`: `PageRegion` = `{excerpt, bbox?}` — **no coordinate space, no page dimensions, no frame**.
- `FACT` `app/domain/contracts/evidence.py` `BoundingBox`: only `x0,y0 ≥ 0`, `x1,y1 > 0`, `x1>x0`, `y1>y0` — **no upper bound**, so normalized (0..1) coordinates validate cleanly and are silently meaningless.
- `FACT` the system prompt (`app/llm/page_review_harness.py:420-466`) never defines bbox units, origin, or bounds; the only related sentence is `page_review_harness.py:432` ("图像位置另由 region 表达"). The schema is the sole driver of bbox emission.
- `FACT` observations with bbox are persisted verbatim in the append-only payload (`page_review_models.py:12-38`, `page_review_repository.py:75-111`), and identity is content-addressed with `_same_or_conflict` refusing a different payload for the same id (`page_review_repository.py:46-51`) → a wrong-space record is **immutable in place**.
- `FACT` all current consumers read only `region.excerpt` (list in §0) → a wrong-space bbox is currently **unobservable**.
- `INFER`: rotation does not create a new defect class here; it *amplifies* a pre-existing one and converts it into a clinically material one the moment any consumer reads `page_reviews.payload_json` bboxes.
- `REC`: make the space explicit and enforced **before** enabling rotation: (i) declare that `region.bbox` is in the presented image's pixel space, top-left origin, bounded by that image's dimensions; (ii) validate the upper bound against the presented image's dimensions (the guard the module already has at `reading_view.py:54-55`) and treat a violation as one repairable format error; (iii) for the first activation, **forbid bbox under a view read** (see F-6) so no unconverted coordinates can ever be persisted.

#### F-3 (verified-good, with one caveat) — The quarter-turn mapping and encoder mapping are arithmetically correct; the flaw is the *absence of declared space/verification*, not the math

- `FACT` `reading_view.py:58-63` mapping vs continuous-edge derivation (`INFER`, done by me):
  - 90° CW: view (x,y) → source (y, h−x) ⇒ edges `(y0, h−x1, y1, h−x0)` ✓ matches line 59.
  - 180°: `(w−x1, h−y1, w−x0, h−y0)` ✓ line 61.
  - 270° CW: view (x,y) → source (w−y, x) ⇒ edges `(w−y1, x0, w−y0, x1)` ✓ line 63.
- `FACT` `reading_view.py:84-86`: PIL `ROTATE_*` are counter-clockwise, so `90→ROTATE_270` and `270→ROTATE_90` are correct.
- `FACT` `reading_view.py:83-94`: 0° returns the original bytes unchanged (byte-identical, hash-equal) — good; but `view_id` still differs from any source identity, which matters for F-8.
- `UNCERT` no test in the repo covers any of this; my check is source-level arithmetic, **not** clinical acceptance, and I cannot confirm it against real pages.

#### F-4 (high) — Two rotations now exist with no declared composition rule, and the view takes its dimensions from decoded bytes rather than the persisted page dimensions

- `FACT` `app/storage/ocr_models.py:109-115`: `PageArtifactRecord` already stores `page_width`, `page_height`, `rotation`, `renderer_version`, `decoder_version`.
- `FACT` `app/evidence/coordinates.py:28-31` states explicitly that 90/270 page-dimension swapping is **already contained in the frame** and must not be re-applied.
- `FACT` `app/storage/evidence_locator_repositories.py:369-390` (`_verify_frame`) requires any bbox locator's frame to equal the artifact's `page_width/page_height/rotation/transform_version` exactly.
- `FACT` `app/evidence/reading_view.py:35-46` identity has no `rotation`/frame/space field, and `make_reading_view` derives dims from `Image.open(...).size` (`reading_view.py:82,91`), **not** from `PageArtifactRecord.page_width/page_height`.
- `INFER`: if the renderer's stored dims are already display-oriented (as `coordinates.py` implies), then a view of a page that is itself render-rotated composes two rotations. Without an explicit rule (and an assertion `view.source_width/height == artifact.page_width/height`), the identity can be internally consistent yet inconsistent with the product's only coordinate frame.
- `REC`: the view identity must (a) declare `coordinate_space = page_image_pixels` in the artifact's own image space, (b) assert dims equality with the PageArtifact when bound, and (c) state the composition rule for `artifact.rotation` × `clockwise_degrees` without ever re-applying either.

#### F-5 (medium) — `ReadingView` has no post-construction invariants, so an inconsistent view can be constructed directly and silently return transposed coordinates

- `FACT` `reading_view.py:20-29`: frozen dataclass with no `__post_init__`; only `make_reading_view` (`:73-78`) validates.
- `FACT` `source_bbox` (`:52-66`) trusts `self.width/self.height` for its range check and derives the output from `self.clockwise_degrees`; nothing ties those to `source_width/source_height` or to the bytes.
- `INFER`: direct construction with `clockwise_degrees=90` and unswapped dims yields wrong source coordinates with no error; the same holds if `image_bytes` does not match `view_image_sha256`'s pre-image.
- `REC`: promote to a frozen pydantic `ContractModel` (the codebase convention) or add `__post_init__` checks: dims/rotation invariant; `sha256(image_bytes) == view_image_sha256`; 0° ⇒ identical bytes and dims.

#### F-6 (medium-high, design) — "Convert before any consumer" is the wrong *first* step here: there is no consumer, and honest degradation is the codebase's existing policy

- `FACT` the view-space bbox has **no** consumer (§0), while the product's coordinate policy is fail-closed elsewhere: `evidence_locator_service.py:258-264` ("诚实降级为文本范围", "绝不生成伪精确红框") and `page_review_visual_locators.py:11-17,41-47,95-105` deliberately emit `bbox=None, coordinate_frame=None, precision=page_excerpt, authenticity=degraded`.
- `INFER`: forbidding bbox for view reads is not a regression against policy — it is the same policy applied to a new input. It also removes a real coupling hazard: conversion inside `evaluate_page_review_response` would entangle the format-repair fingerprint path (`page_review_harness.py:722-741`, `page_review_format_repair.py:164-189`), which computes both comparisons from the raw response text and must be given the view argument identically on both calls.
- `REC` (Phase 1): a v7 validator requires `region.bbox is None` whenever `reading_view is not None`; the schema sent to the model drops `bbox` using the existing mutation pattern (`page_review_harness.py:646-653`). Raw view-space coordinates remain in the `raw_response` artifact (`page_review_job_executor.py:139`) with `response_sha256 = canonical_hash(raw)` unchanged (`page_review_format_repair.py:159-161`). Phase 2 (conversion via the already-correct `source_bbox`) is added only when a consumer actually needs boxes.

#### F-7 (high, compatibility) — A contract bump to `page-review/v7` is not additive: it invalidates historical coverage selection and re-reconciliation

- `FACT` `page_review.py:22,239` current `PAGE_REVIEW_CONTRACT_VERSION = "page-review/v6"` with a `Literal[...]` gate and version-dispatch validators (`:263-288`).
- `FACT` `app/domain/page_reconciliation.py:47-48` rejects any record whose version ≠ current ("历史页记录版本仅供回看，请按当前版本重新判读后对账").
- `FACT` `app/services/page_review_coverage_selection.py:81` rejects a historical whole coverage on version or prompt mismatch ("请重新判读当前资料；历史记录仍保留").
- `FACT` `app/services/page_review_visual_sources.py:85-87` re-reconciles **persisted** records and requires the recomputed id to equal the stored id, so a version bump cannot silently re-derive old visual sources.
- `FACT` `app/services/page_review_recovery.py:64-68` builds `binding = {**page, ...}` from the job payload page dict and calls `getattr(record, key)` **with no default** for every key → a view key named differently from the record field raises `AttributeError` (not a clean "not reusable").
- `INFER`: the choice is deliberate invalidation (re-read required for existing projects — consistent with the codebase's fail-closed stance) versus an additive non-gating field (which risks mixing reading bases inside one coverage).
- `REC`: bump deliberately, put the view key in the payload under the **exact record field name** (`reading_view`), and rely on the existing version machinery (`page_review_execution_versions()` at `page_review_job_service.py:42-47`, `PAGE_REVIEW_JOB_CONTRACT = r3-page-review-job/v10`, and `page_review_job_executor.py:47-52` → `R3_EXECUTION_VERSION_CHANGED`) rather than inventing new orchestration.

#### F-8 (medium) — Task-identity consequences and 0° identity duplication

- `FACT` `page_review_harness.py:753-776` (identity hash) and `:745-752` (prompt version) determine `page_review_id`; adding a view component makes two views of one page two distinct, correctly-versioned review ids — which is the desired "different reading basis ≠ overwrite" property.
- `FACT` `page_review_job_service.py:173` idempotency key = `canonical_hash(payload)`; `:190-210` resume requires payload equality → the view must live in the payload to make job identity honest.
- `FACT` 0° returns byte-identical images yet still yields a distinct view identity (`reading_view.py:83-94`, `:35-50`).
- `REC`: treat 0° as **no view** (`reading_view = None`) so the identity space stays single and comparable; materialize a view only for a non-zero, explicitly chosen direction.

#### F-9 (medium) — `view_image_sha256` is a derived hash with no re-derivation guarantee (no encoder/renderer version in the identity)

- `FACT` non-zero views are re-encoded as PNG (`reading_view.py:88-90`); the identity has no encoder version, unlike the artifact convention `renderer_version`/`decoder_version` (`ocr_models.py:113-114`).
- `FACT` artifact kinds are a closed allowlist (`app/evidence/artifacts.py:19-23,58-62`), so persisting view bytes requires adding a kind; storing them under `page_image` would conflate the view with the source page image.
- `REC`: prefer identity + recipe (source hash, quarter-turn, contract version) **plus** an explicit `view_renderer_version` so the derived hash is verifiable later; do not add a new artifact kind until bytes must be stored.

#### F-10 (uncertainty to close cheaply) — EXIF/JPEG orientation and renderer dims

- `INFER`/`UNCERT`: `Image.open` does not apply EXIF orientation, while browsers auto-orient displayed JPEGs; if any page artifact is an EXIF-rotated JPEG, the model's view coordinates and the on-screen image disagree independently of this feature. I cannot check whether page artifacts carry EXIF without reading clinical originals (out of scope).
- Cheap closure (no clinical data): assert `decoded_size(page_image_bytes) == (artifact.page_width, artifact.page_height)` on one real project page, and record whether `image.info` carries EXIF orientation.

---

### 2. Objections to the concrete proposal as written

1. **"Persist a derived reading-view identity"** understates the blast radius. Because of F-1, the identity must appear in the read input, the review record, the repository cross-check, and the job payload/version dict, or it cannot exist at all. It is not a `reading_view.py` addition.
2. **"Convert to original-page coordinates before any source locator consumes them"** has no consumer today (F-6) and cannot be validated by any current test or acceptance path. Doing it first adds a fingerprint/reconciliation coupling for zero present benefit. Forbidding bbox under a view is smaller, honest, and consistent with the product's no-fake-box policy.
3. **The premise "explicit source/coordinate contract" is not yet true** — not for views and not for the base case (F-2). Rotation would amplify an existing undeclared-unit defect. Declaration and upper-bound validation must precede rotation, and both are needed for unrotated reads too.
4. **"Never replace source page identity with a view ID"** is already mechanically enforced for coverage (`PageReviewRecordORM.page_artifact_id` FK to `page_artifacts`, `page_review_models.py:16`; `_verify_page`; `expected_page_artifact_ids` closure at `page_review.py:450-460`) — but **not** for `page_image_sha256`, which flows into `PageReviewVisualProvenance.page_image_sha256` (`page_review_visual_locators.py:123-130`) and into the record's content identity. The guard must be stated and enforced at that field.
5. **Do not treat the rotation math (or a successful isolated experiment) as readiness.** The module has zero in-repo consumers and zero tests; the arithmetically correct mapping is one precondition, not evidence that a rotated read is clinically safe, and per the review boundary this is not clinical acceptance.

---

### 3. Concise proposed integration sequence (minimal connected change set)

Ordered so that no step can persist wrong evidence; each step names the file(s) and its verification.

**P0 — Pre-flight facts (no product change).** Assert decoded image size == `PageArtifactRecord.page_width/page_height` and determine page-image format/EXIF on one real project page. If they differ, stop and fix the space definition first (F-4, F-10). *No source edit.*

**P1 — Make the view a contract, still with zero consumers (lowest risk).**
`app/evidence/reading_view.py`: frozen `ContractModel` (or `__post_init__`) enforcing dims-vs-rotation, `sha256(image_bytes) == view_image_sha256`, 0° byte equality; add `coordinate_space`, `view_contract_version`, `view_renderer_version` to the identity; keep `make_reading_view` refusing inference. *Verify:* synthetic-image round-trip for 0/90/180/270, edge/corner boxes, out-of-range rejection, invariant violations — no clinical data.

**P2 — Read input + prompt/schema.**
`app/llm/page_review_harness.py`: `PageReviewInput` gains `reading_view: ReadingViewIdentity | None = None`; `__post_init__` branches (view absent ⇒ today's check unchanged; view present ⇒ source hash/dims/page-id agreement and sent-bytes hash == view hash). `PageVisionInput.source_ref` stays `page_artifact_id` (never the view id). Add an explicit sentence that the presented image may be a rotated reading view and that `region.bbox` is in the presented image's pixel space with a top-left origin; drop `bbox` from the outgoing schema for view reads (existing mutation pattern `:646-653`); bump `PAGE_REVIEW_PROMPT_VERSION`.

**P3 — Record contract + persistence.**
`app/domain/contracts/page_review.py`: `page-review/v7` with `reading_view: ReadingViewIdentity | None` (`exclude_if None`), v1–v6 dispatch untouched. Phase-1 coordinate honesty: validator requires every `region.bbox is None` when a view is present. `app/storage/page_review_repository.py`: keep `_verify_page` intact; add the view cross-check. Payload-only field ⇒ no DB migration.

**P4 — Job/task identity freeze.**
`app/services/page_review_job_service.py`: page entries gain `reading_view` under that **exact** key; bump `PAGE_REVIEW_JOB_CONTRACT` → `v11` and add the view version to `page_review_execution_versions()`. Direction enters as an explicit per-page `clockwise_degrees` (+ optional bounded `direction_source`) with no inference; 0° = no view; "direction not reviewed" stays a workflow gap, never a silent upright default.

**P5 — Deferred: bbox conversion (only when a consumer needs boxes).** Apply `ReadingView.source_bbox` at record construction (or in the v7 validator), threading the view into both `evaluate_page_review_response` and `valid_observation_fingerprints` so an out-of-range box becomes one repairable format error; the persisted box is then provably in the artifact's `PAGE_IMAGE_PIXELS` space that `_verify_frame` accepts.

**Explicit non-goals:** no orientation auto-detection; no new generic orchestration; no locator/visual-locator contract changes; no benchmark or token/cost claims; no clinical acceptance.

---

### 4. Decision points for Codex

| # | Decision | Recommendation |
|---|---|---|
| D1 | Phase-1 bbox policy under a view: forbid vs convert now | **Forbid** (no consumer; matches honest-degradation policy; avoids fingerprint coupling) |
| D2 | View bytes: identity+recipe vs persisted content-addressed bytes | **Identity + recipe + `view_renderer_version`**; new artifact kind only when bytes must be stored |
| D3 | `page-review/v7` bump accepting that historical coverages become ineligible | **Accept deliberate invalidation** (consistent with existing fail-closed gates) — choose explicitly, since it triggers "re-read" for existing projects |
| D4 | 0° semantics: no view vs a 0° view identity | **No view** |
| D5 | Direction provenance: `clockwise_degrees` only vs + `direction_source` | **Add a bounded `direction_source`**; keep "not reviewed" as a separate gap |

### 5. Bounded questions (answerable in a same-session follow-up)

- **Q1 (blocking for P1/P3):** Is `PageArtifactRecord.page_width/page_height` stored in display orientation, and does the decoded page image size equal it exactly? I cannot read clinical originals; a single non-clinical fixture or the renderer call site settles the view identity's dims invariant.
- **Q2:** Was the owner's direction decision made per page or per document? This decides whether `clockwise_degrees` sits in each `payload["pages"][i]` or in a per-document map, and which keeps `plan_page_reread`'s key-for-key `getattr` binding (`page_review_recovery.py:64-68`) clean.
- **Q3:** Do you authorize the Phase-2 signature change to `evaluate_page_review_response` / `valid_observation_fingerprints` if conversion ships now instead of Phase 1?
- **Q4:** Is a `page-review/v7` bump acceptable given it invalidates historical coverage selection and re-reconciliation (F-7)? If not, the alternative is an additive non-gating field — which I would need you to accept explicitly, because it permits mixed reading bases inside one coverage.
- **Q5:** Do you want the exact file-level patch plan for a single bounded step (e.g. P1 only) as a same-session follow-up?

### 6. Uncertainty and limits

- Read-only: no tests executed, no models called, no clinical originals read, no product artifact written. The runner-managed report path was not written.
- The quarter-turn verification is source-level arithmetic; it is **not** clinical, visual, or production acceptance, and no benchmark/cost conclusion is drawn.
- The isolated experiment's invocation of the module is not present in this worktree; I make no claim about what it did.
- Pillow PNG-encoder byte determinism across versions is unverified (drives F-9).
- EXIF/renderer-dimension exposure (F-10) is unverified and needs the P0 check.
