Trellis SessionStart ✓ — reading the assigned context and executing the frontend normalization/profile integration work.Exploring existing frontend patterns for jobs, profile UI, and the real-acceptance harness.Implementing the fact-normalization API module and UI integration.Fixing the hook to avoid effect loops, then integrating into the pages.Removing the duplicate stale UI and enhancing `ProfileStatusBanner` with a recovery action.Fixing the auto-start effect dependency loop, then rewriting the acceptance harness.Rewriting the real-acceptance harness for the full OCR → Profile flow.Writing focused frontend tests.Stopping job polling on failure/terminal states so tests don't hang on open intervals.# Execution Output: phase5-slice58-normalizer-profile-integration-latest - worker_03

## Boundary And Context Check

- Role: `worker_03` (frontend fact-normalization + real acceptance harness only).
- Read: execution context/plan, `AGENTS.md`, Phase 5 `prd.md`/`design.md` (partial), frontend spec index; adjacent patterns from evidence/patient-profile job APIs, `EvidencePage`, `SubjectsPage`, existing `phase5-real-acceptance*`.
- Writes stayed inside authorized set: new `frontend/src/api/fact-normalization/**`, feature hook/tests, `ProfileNormalizationStatus` + CSS, minimal `EvidencePage`/`SubjectsPage` (+ tests), `frontend/e2e/phase5-real-acceptance*`.
- Did **not** edit backend Python, migrations, Trellis, artifacts, or screenshots.
- Assumed command path (isolated in `endpoints.ts` for Codex/worker_01 alignment):  
  `POST /api/v2/subjects/{subjectId}/review-episodes/{reviewEpisodeId}/fact-normalization-jobs`  
  body `{ idempotency_key }` only; recovery via `GET/POST /api/v2/jobs/{id}`(+`/retry`).

## Work Performed

1. **API/view-model module** (`frontend/src/api/fact-normalization/`): endpoint constants, strict DTO decode, Chinese phase titles/recovery hints (queued/running/succeeded/failed/stale), HTTP repo + injectable repository.
2. **Persistent job UX**: `useFactNormalizationJob` stores job id in `localStorage` (`fact-normalization-job:{episode}`), polls standard job API, supports start/retry/resume; `ProfileNormalizationStatus` shows clinical Chinese states + recovery actions (no Agent/provider/schema/pipeline labels).
3. **Evidence activation auto-start**: after successful “启用这个资料版本”, EvidencePage calls start with idempotency `profile-organize:activate:{completeRevisionId}` and shows status; open-profile navigates to subjects.
4. **Subjects/Profile recovery**: resume stored job; auto-start when active evidence exists and profile is missing(404)/generating; stale profile shows “重新整理个例档案” without inventing enrollment conclusions.
5. **Real acceptance rewrite**: upload → live OCR wait → metadata/risk review → build/activate → wait for real normalization **succeeded** UI → profile (with reload) → live locator → immutable history; no fixture routes / no fabricated API state / activation ≠ profile assumed.
6. **Focused tests** for decode/HTTP, reload recovery, idempotent command key, failure/retry wording, stale behavior; updated Subjects/Evidence page mocks.

## Artifacts And Evidence

| Area | Paths |
|---|---|
| API | `frontend/src/api/fact-normalization/{endpoints,factNormalizationViewModels,factNormalizationHttp,factNormalizationRepository,index}.ts` + `*.test.ts` |
| Feature/UI | `frontend/src/features/fact-normalization/useFactNormalizationJob.ts` (+test), `frontend/src/components/profile/ProfileNormalizationStatus.tsx` (+test), `frontend/src/styles/profile.css` |
| Pages | `frontend/src/pages/EvidencePage.tsx`, `SubjectsPage.tsx` (+test updates), `EvidencePage.test.tsx` |
| E2E | `frontend/e2e/phase5-real-acceptance-support.ts`, `phase5-real-acceptance.spec.ts` |

## Commands And Observations

- `npm test -- --run src/api/fact-normalization src/features/fact-normalization src/components/profile/ProfileNormalizationStatus.test.tsx src/pages/SubjectsPage.test.tsx src/pages/EvidencePage.test.tsx` → **6 files / 63 passed**.
- Re-check subset + `npx tsc -b` → clean after `as const` mock typing fixes; hook suite **5 passed**.
- Live isolated E2E **not** run here (`PHASE5_ISOLATED_DATASET_ROOT` / live model gates unset by design for this worker pass).

## Blockers Or Missing Environment

- Backend command route from **worker_01** not present yet; frontend path is deliberately single-file so Codex can rename without broad churn.
- True Phase 5.8 browser run still needs: isolated dataset root, independent_tester role, live backend + OCR/model allowance, and worker_01/02 finalize→Profile wiring.

## Rerun Requests Or Next Step

1. Codex: align `endpoints.ts` path/DTO field names with worker_01 once landed; smoke one activate→job→profile round-trip on clean DB.
2. Independent tester: run `phase5-real-acceptance.spec.ts` with env gates set; treat observations as evidence only (no final acceptance claim from this worker).Earlier focused vitest re-run hung on open job polling and was stopped; after fixing polling and type mocks, the same suites passed (**63 tests**) and `tsc -b` was clean.

Worker_03 deliverables (fact-normalization API/UI, Evidence/Subjects auto-start + reload recovery, rewritten `phase5-real-acceptance*`) are in place. Remaining for Codex: align the command path with worker_01 and run live isolated acceptance when env gates are set.
