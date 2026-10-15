Fallback declared: I am now `codebuddy-cli/deepseek-v4-flash` continuing worker_03's assignment under the same bounded contract, same read set, same output schema. Both initial-read files are consumed. Proceeding with the assigned work item: deterministic anti-overfit tests + independent review, plus the heterogeneous real-protocol replay gate.

Let me set up tracking and read the source-of-truth files.

`tests/v2/protocols/` lacks the named regression anchors in this worktree. Let me locate them and read the production chain.

The earlier `ls` was truncated. The regression anchors exist. Reading the candidate chain and existing tests now.

Many tests already exist (some predating this dispatch, some from peers). Reading the production chain and the existing anti-overfit/model-identity tests to assess coverage and avoid duplication.

The existing anti-overfit file covers a subset. I need to see the model-identity test, smoke runner, production regressions, and the checkpoint to identify coverage gaps for my supplement.

Existing coverage is substantial. Now checking the smoke-runner tests, the replay harness, and the accepted checkpoint to find the gap my supplement must fill.

Reading the accepted checkpoint and the replay-harness test to understand what "heterogeneous real-protocol replay" preconditions exist today.

Now reading the worker_02 runner script and the discovery transport to understand the replay gate surface and what my supplement must cover.

The runner is fully understood. Now scanning the whole candidate chain for corpus vocabulary to design evidence-driven anti-overfit checks.

Clean so far — only generic terms matched. Running a broader disease/drug/scoring/timepoint scan plus config check.

Scan clean: no corpus vocabulary in the chain. Checking the prompt builders (discovery + deep) and the replay harness module for the spec tests I'll add.

Reading the discovery-input types to construct prompt-level tests correctly.

I have the full API surface. Checking conftest and the deep prompt template default for the marker sweep, then writing the supplement test file.

Verifying the exact final marker set produces zero matches across the chain before I pin it in a test.

One false positive: "IGA" matches inside "obli**ga**tion". Short tokens need word boundaries. Re-verifying.

Zero hits chain-wide. Confirming the discovery-input class name and trial-building a neutral replay fixture to pin source refs before writing the test.

System Python 3.9 can't parse `X | None` unions — the project runs on a newer interpreter via uv. Checking the test invocation convention.

Python 3.12 via `uv run` as expected. Retrying the trial with the project interpreter.

The harness takes a typed config object. Fixing the trial.

Phase detection needs "Ⅱ期" markers in the neutral fixture. Adjusting.

All pieces verified. Writing the supplement test file now.

One fix before running — the deep repair prompt expects a batch, not the agent input.

The pattern scan overreaches — finding where "digit+周" legitimately appears in the prompt contract.

The hit is a generic prompt instruction ("不得凭空补0天边界"), not a project timepoint. Checking all pattern hits across the chain to tune precision.

Single generic hit ("0天" instruction example). Tightening the pattern to non-zero values, which excludes generic instruction forms while catching real timepoints.

Still a hit inside generated prompts. Extracting the exact match.

The remaining hit is a generic schema example ("例如 3 个月或 4 周") in the TimeQuantity domain model — not project hardcoding. Tightening: drop the bare-number pattern, keep numbered/English-week/percent patterns, and add bare endpoint forms as explicit markers.

The replay pack contains the binary source blob. Restricting the artifact sweep to text files.

All 16 pass. Running the coherent focused scope (anti-overfit + regressions + identity + smoke runner) to confirm no interaction issues.

Focused scope green: 62 passed. Verifying my footprint is exactly one new file with clean whitespace.

My footprint is exactly one new untracked test file. Final hygiene check.

All work items complete. Final report follows.

---

# Execution Output: phase5-protocol-control-live-model-smoke-20260831 - worker_03

## Boundary And Context Check

- **Fallback declared:** This session continued as the declared same-platform fallback `codebuddy-cli/deepseek-v4-flash` (route switched from `glm-5.3-flash` after the worker-03 role resumed). Same bounded contract, same read set, same output path (`runs/execution/phase5-protocol-control-live-model-smoke-20260831/worker_03.md`, runner-managed, not written by me), same quality gates.
- **Initial read set consumed:** `context/phase5-protocol-control-live-model-smoke-20260831_execution_context.md`, `plans/codex_execution_phase5-protocol-control-live-model-smoke-20260831.md`.
- **Assigned work item (worker_03):** 补充确定性测试与独立反过拟合审查，验证无D001/SAR/药物/疾病/评分/时间点硬编码，并明确异构真实协议回放前置门禁。
- **Hard boundaries respected:** work confined to the runner CWD; read-only access to all production candidate-chain modules, runner scripts, tests, and the accepted checkpoint; **no production file, prompt, clinical artifact, or peer worker file was modified**; no D001/SAR/raw-clinical content opened; no live model called; no formal `ProtocolReviewControl` catalog created; only focused tests run (full suite not run — Codex owns broad verification); no conference, no peer review, no internet.
- **Authorized write scope used:** exactly one new test file under `tests/v2/protocols/` (verified via `git status`). No other file created or changed by me.

## Work Performed

**1. Independent anti-overfit review (read-only assessment) of the full shared candidate chain.**

Static evidence (grep scans, `-i` + word-boundary regex) across: `app/agents/protocol_control_{agent,discovery}_transport.py`, `app/agents/protocol_control_deconstructor.py`, `app/services/protocol_control_{execution,executor,job_service}.py`, `app/protocols/protocol_replay_harness.py`, `scripts/run_protocol_control_smoke.py`, `scripts/run_protocol_replay_harness.py`, `app/config.py`, `.env.example`:

- **Zero hits** for: project identifiers (`D001`, `MG-K10-SAR`, `CMS-D001`, `SAR-001`); disease words (`银屑病`, `特应性皮炎`, `斑块`, `皮炎`); drug/mechanism words (`度普利尤`, `达必妥`, `司库奇尤`, `乌司奴`, `IL-4/13/17/23`, `JAK`); instruments (`PASI`, `EASI`, `IGA`, `SCORAD`, `DLQI`, `PGA`, `BSA`, `HADS`, `NRS`); explicit timepoints (`第12/24/52周`, `12/24/52/8/16周`, `W12`, `Week 12`); thresholds (`75%`, `50%`); and patterns `第N周/天`, `W N`, `week N`, `N%`.
- Only generic matches found and judged non-project-specific: `"4 周"` schema example in `TimeQuantity` documentation (generic unit example), `"0天"` generic repair instruction ("不得凭空补0天边界"), `访视` as a generic visit-assignment concept in the gate contract, model-name constants in `app/config.py`/`.env.example` (runtime identity, not clinical vocabulary).
- Cross-checked against pre-existing coverage: `test_protocol_control_anti_overfit.py` scans 4 modules with 9 tokens; `test_protocol_control_production_regressions.py` scans `app/**` globs (note: `app/protocols/protocol_replay_harness.py` does NOT match its `protocol_control*` glob, and neither scans `scripts/`, `app/config.py`, or `.env.example`). My supplement closes exactly that gap (chain-wide, scripts + harness + config included, behavioral prompt/fixture/pack sweeps added).

**2. Deterministic supplement tests written** — new file `tests/v2/protocols/test_protocol_control_anti_overfit_chain_wide.py` (16 tests, all deterministic, no model, no real protocol):

- Static scans: whole-chain corpus-vocabulary sweep + per-file timepoint/threshold pattern sweep (11 chain files, parametrized).
- Behavioral: generated discovery/deep/repair prompts neutral (built via real `plan_protocol_control_*` + real prompt builders); bundled smoke synthetic DOCX neutral; model-free replay-pack text artifacts neutral and byte-for-byte reproducible (`replay_pack_fingerprint` equal across out dirs, `verify_replay_pack == []`).
- Executable replay-gate spec: `test_heterogeneous_real_protocol_replay_precondition_gate` maps each gate precondition G1–G5 to an enforced behavior (below).

**3. Focused test runs (no full suite).**

## Artifacts And Evidence

- **New artifact:** `tests/v2/protocols/test_protocol_control_anti_overfit_chain_wide.py` (16 tests; `py_compile` clean; no trailing whitespace; single new untracked file, confirmed by `git status --short -- tests/`).
- **Test evidence:** new file alone: **16 passed** in 0.45s. Focused scope (new file + `test_protocol_control_anti_overfit.py` + `test_protocol_control_production_regressions.py` + `test_protocol_control_model_identity.py` + `tests/v2/services/test_protocol_control_smoke_runner.py`): **62 passed** in 4.81s.
- **Replay gate pinned (heterogeneous real-protocol replay preconditions, G1–G5):**
  - **G1 模型身份正向核验**: configured model must positively match `/v1/models` served ids; missing/ambiguous/mismatch fails closed (Chinese diagnostic, exit 2) before any semantic request or job creation (no `data_v2` dir created). Re-asserted in gate test; already enforced by transport `verify_model_identity` + runner ordering.
  - **G2 输入边界**: default input is the bundled vocabulary-neutral synthetic protocol only; `projects/` and real-data-dir files rejected by `_assert_fixture_allowed` (exit 4).
  - **G3 词汇中立**: bundled synthetic fixture and all replay-pack text artifacts pass the full marker sweep.
  - **G4 同合同可复现**: replay packs from identical frozen input are fingerprint-identical and verifiable (`replay_pack_fingerprint` equal; `verify_replay_pack == []`), i.e., same prompts/contracts/gates as the neutral smoke — no project-specific branch can enter via replay.
  - **G5 不物化**: every run record carries `formal_catalog_materialized=false`, `real_clinical_content_used=false`, `claims_complete=false`; no formal `ProtocolReviewControl` catalog path exists in the chain.
  - **Operational ordering** (documented, not machine-enforceable across separate CLI runs): neutral smoke exit 0 with verified Quality identity first, then read-only D001 and MG-K10-SAR replay on frozen snapshots with pinned expected SHA-256, identical harness/config; any deviation fails closed. Matches checkpoint "下一安全动作" items 1–2 and "不因任一真实项目添加共享项目特异规则".

## Commands And Observations

| Tool / target | Observation |
|---|---|
| `ls` tests/v2/protocols, app/agents, app/services | Candidate chain and many prior-phase tests present; `tests/v2/protocols/` contains the named regression anchors |
| `git status` / `git log` (worktree) | Phase-5 worktree mid-development; many pre-existing modified/untracked files; my footprint = 1 new untracked test file |
| Read: transports, deconstructor, execution/executor/job_service, replay harness, smoke runner, checkpoint, 4 existing test files | Full API surface and existing coverage mapped; runner implements identity-first fail-closed, fixture guard, frozen-source stop, durable run record |
| `grep` chain-wide marker sweeps (2 rounds) | Zero corpus-vocabulary hits after word-boundary refinement ("IGA" false-positive on `obli**ga**tion`; "4 周"/"0天" generic examples excluded by design) |
| `uv run python` trial builds (replay pack) | Neutral phase-marked fixture resolves `body.p2/p4` owned refs; pack builds; system Python 3.9 cannot import project (3.12 unions) — project interpreter is `uv run` |
| `uv run pytest <new file>` (3 iterations) | 16 passed after two precision fixes (pattern false positives on generic schema example; binary source blob excluded from text sweep) |
| `uv run pytest <5 focused files>` | **62 passed** |
| `git diff --check -- tests/`, `py_compile` | No whitespace errors; compiles clean |

## Blockers Or Missing Environment

- **None blocking.** Note: the worktree's local model service, if running, is not consumed by any of my tests (no live call). The observed Speed-vs-Quality mismatch fixture from the execution context was reused only as vocabulary-neutral two-distinct-names evidence inside the pre-existing identity tests.
- Remaining verification (Codex-owned, per context): broad suite run after integration; real live-model smoke execution; read-only D001/SAR heterogeneous replay under the gate; final rendered/clinical acceptance.

## Rerun Requests Or Next Step

- **Resume point:** none required — worker_03 deliverables complete within budget. Codex may continue this same session to review the new test file and the gate spec.
- **Suggested next step for Codex:** (1) integrate and run the full suite (pre-existing checkpoint reported 3295 passed / 3 skipped / 18 subtests — needs re-confirmation after this addition); (2) run `scripts/run_protocol_control_smoke.py` against the live service once identity is positively matched to the configured Quality model; (3) after smoke passes, run the D001 and MG-K10-SAR read-only heterogeneous replays under the G1–G5 gate with pinned SHA-256, then compare coverage closures and error patterns without adding any project-specific shared rule.
