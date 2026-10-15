Trellis SessionStart ✓ — reading the assigned context and plan, then executing only the worker_02 remediation item.Next I’ll inspect the profile correction components and related tests to locate draft loss, Chinese copy, and fixture semantics.Checking tests and fixtures against the immutable revision/locator semantics.Implementing draft preservation (keep dialog mounted while evidence is open), unifying Chinese copy, and aligning fixtures with immutable locator/revision semantics.Updating fixtures and tests next.Cleaning up the history test and aligning remaining Chinese copy; adding a unit test for draft parking.# Execution Output: phase5-slice57-visual-findings-remediation-latest - worker_02

## Boundary And Context Check

- Read: `context/phase5-slice57-visual-findings-remediation-latest_execution_context.md`, `plans/codex_execution_phase5-slice57-visual-findings-remediation-latest.md`, conference finding `runs/conference/phase5-slice57-visual-final-latest/visual_pi_k3_256k.md` (F5/F1/F2/F7/F8 grounding).
- Extra reads limited to authorized frontend sources/tests for the assigned item.
- Wrote only worker_02 authorized paths: `SubjectsPage.tsx`, `ProfileFactCorrectionDialog.tsx`, `ProfileCorrectionHistory.tsx`, `factCorrectionDisplay.tsx`, corresponding unit tests, `frontend/e2e/profile-correction.spec.ts`.
- Did **not** edit backend, Trellis, route/report files, screenshots, `profile.css`, or `OriginalEvidenceViewer.tsx`.
- Did **not** claim final visual/clinical acceptance.

## Work Performed

1. **Draft/preview preservation (F5)**  
   - `openCorrectionEvidence` no longer unmounts the correction workspace.  
   - Dialog stays mounted; `evidenceOpen` parks the overlay (`visibility: hidden` / `pointer-events: none`, Escape unbound while parked).  
   - Closing evidence restores focus to the in-dialog “查看原文” trigger; closing correction also clears any open evidence.

2. **Chinese copy unification**  
   - Impact count label: `历史档案版本` → `受影响历史档案`.  
   - Node-scope notice: `历史档案版本保持不变` → `既有档案版本保持不变` (avoids clashing with version-number language).  
   - History loading/error copy aligned to “本次修订生成的档案版本”.  
   - Kept `本次修订形成档案第 N 版。` — matches non-negotiable semantics that `profileRevisionId` is the **generated** Profile.

3. **Immutable revision/locator fixtures**  
   - Correction history binds to `profile-revision-3` (generated), not pre-correction rev-2.  
   - Cited locator `loc-bp-1` stays page 1 / new excerpt; pre-correction uses distinct `loc-bp-pre` (page 7).  
   - Titles normalized to native Chinese (`血压 130/85 mmHg` / `血压 120/80 mmHg`); title/value aligned on generated Profile.  
   - E2E asserts draft survives evidence round-trip; history never requests rev-2 for this correction.

## Artifacts And Evidence

| Path | Change |
|---|---|
| `frontend/src/pages/SubjectsPage.tsx` | Keep correction mounted on evidence open; pass `evidenceOpen`; close evidence with correction |
| `frontend/src/components/profile/ProfileFactCorrectionDialog.tsx` | `evidenceOpen` parking + Escape guard |
| `frontend/src/components/profile/ProfileCorrectionHistory.tsx` | Semantics comments + generated-revision copy |
| `frontend/src/components/profile/factCorrectionDisplay.tsx` | `受影响历史档案` |
| `frontend/src/components/profile/ProfileCorrectionHistory.test.tsx` | Immutable fixtures/assertions |
| `frontend/src/components/profile/ProfileFactCorrectionDialog.test.tsx` | Copy + `evidenceOpen` draft park test |
| `frontend/src/pages/SubjectsPage.test.tsx` | History binds generated Profile |
| `frontend/e2e/profile-correction.spec.ts` | Draft retention + immutable fixtures |

**Evidence (inference vs observation):**  
- **Observation:** unit + e2e green (below).  
- **Inference:** production will not show “same locator, different page” if backend enforces Phase 4 immutability; fixtures no longer encode that impossible contract.  
- **Out of scope here:** F3 page/artifact consistency guard in evidence panel; regenerating conference screenshots for final visual acceptance.

## Commands And Observations

| Command | Observation |
|---|---|
| `npm test -- src/components/profile/ProfileCorrectionHistory.test.tsx src/components/profile/ProfileFactCorrectionDialog.test.tsx src/pages/SubjectsPage.test.tsx` | 3 files, 20 tests passed |
| `npx playwright test e2e/profile-correction.spec.ts --reporter=line` | 3 viewports (1080p/2K/4K) passed in ~7s |

## Blockers Or Missing Environment

None for the assigned frontend item. Environment (Node/Vitest/Playwright) was sufficient; no installs performed.

## Rerun Requests Or Next Step

1. Codex: review this output against worker_01 (backend revision/snapshot contract) and worker_03 (read-only full-chain check).  
2. After acceptance: regenerate Phase 5.7 correction screenshots and re-run visual conference if needed.  
3. Optional follow-ups outside this worker: ProfileEvidencePanel page/artifact consistency (F3); `OriginalEvidenceViewer` “资料名称暂不可读取” wording (not in write set).
