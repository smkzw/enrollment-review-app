Trellis SessionStart ✓ — 按 delegated worker 边界执行 Phase 5.8 浏览器验收编排骨架。先读初始上下文与现有 e2e 模式。继续对照现有 live e2e、playwright 配置与设计书中 5.8 验收边界。对齐 worker_01 清单契约与项目创建 UI，确保环境变量与观察 schema 一致。已对齐 ledger 的 `browser_tester` 证据形状。开始实现编排骨架：环境门控、禁止 fixture、新鲜身份断言，以及可机读观察输出。修复 `beforeAll`：在 disabled 时不得抛错；并去掉无效的 `fabricated` 断言。端口冲突干扰了半开配置验证；改为直接用 Node 探测配置解析。修复项目目录响应解析：API 返回 `{ projects: [...] }`，不是裸数组。# Execution Output: phase5-slice58-acceptance-harness-latest - worker_03

## Boundary And Context Check

- Role: `worker_03` finite code executor; no manager; no conference; no final acceptance claim.
- Read: execution context/plan, task `prd.md`/`design.md`/`implement.md` §5.8, existing live e2e patterns, `playwright.config.ts`, catalog `/api/v2/protocol/projects` shape, and (for observation alignment only) `tools/phase5_acceptance/ledger.schema.json`.
- Writes limited to authorized paths: `frontend/e2e/phase5-real-acceptance.spec.ts`, `frontend/e2e/phase5-real-acceptance-support.ts`, `frontend/playwright.config.ts` (comment-only gate docs).
- Did **not** read external clinical paths, did **not** set `PHASE5_REAL_ACCEPTANCE_ALLOW_LIVE_MODEL`, did **not** run OCR/model, did **not** write the runner report file.

## Work Performed

- Implemented Phase 5.8 browser acceptance **orchestration skeleton** for **D001-II** and **MG-K10-SAR-III** covering: project create → study-phase select → subject upload → real Normalizer → Patient Profile → source locator → history replay.
- Gate: suite **skips** unless `PHASE5_ISOLATED_DATASET_ROOT` is set; half-open config **fails loudly** (no fixture fallback).
- Role separation: `PHASE5_REAL_ACCEPTANCE_ROLE` must be `independent_tester`; `executor` is rejected as misconfigured.
- Anti-fixture: rejects `registerProfileRoutes` / `registerEvidenceRoutes`; forbids known trial/synthetic UI/project markers; refuses default `data_v2`.
- Fresh identity: requires isolation `DATA_DIR` + `.phase5_fresh_acceptance` marker; fingerprints data dir; reads real `GET /api/v2/protocol/projects` as `{ projects: [...] }`.
- Live model/OCR steps require explicit `PHASE5_REAL_ACCEPTANCE_ALLOW_LIVE_MODEL=1`; otherwise steps emit `not_run` observations only.
- Machine-readable `browser_tester` JSONL observations + run summary aligned to ledger EvidenceItem fields (`observed_only` / `not_run` / structural `pass` for fixture gate only).

## Artifacts And Evidence

| Path | Change |
|---|---|
| `frontend/e2e/phase5-real-acceptance-support.ts` | **new** — config resolver, fixture traps, identity checks, step skeleton, observation sink |
| `frontend/e2e/phase5-real-acceptance.spec.ts` | **new** — gated dual-case orchestration suite |
| `frontend/playwright.config.ts` | comment documenting `PHASE5_ISOLATED_DATASET_ROOT` / independent-tester gate |

Required env for a future independent-tester run (not exercised with live model here):

- `PHASE5_ISOLATED_DATASET_ROOT` → isolation root containing `browser-cases.json` (both labels) + protocol/subject files under that root only
- `PHASE5_REAL_ACCEPTANCE_BASE_URL` → production frontend + real API (not `build:e2e` trial stub)
- `PHASE5_REAL_ACCEPTANCE_DATA_DIR` → fresh isolated DB dir (not repo `data_v2`)
- `PHASE5_REAL_ACCEPTANCE_ROLE=independent_tester`
- fresh marker file at `$DATA_DIR/.phase5_fresh_acceptance` (or `PHASE5_REAL_ACCEPTANCE_FRESH_MARKER`)
- optional: `PHASE5_REAL_ACCEPTANCE_ALLOW_LIVE_MODEL=1` to execute model-touching steps

## Commands And Observations

1. `npx tsc -p tsconfig.json --noEmit` — clean (no diagnostics).
2. `npx playwright test e2e/phase5-real-acceptance.spec.ts --project=desktop-1080p` with env unset → **2 skipped**.
3. Same suite with `PHASE5_ISOLATED_DATASET_ROOT` pointing at missing dir → **fails** in `beforeAll` with `不是可用目录` (no fixture downgrade).
4. Fixed after catalog evidence: projects API unwraps `{ projects: [...] }` (not bare array).

## Blockers Or Missing Environment

- Isolation dataset root, `browser-cases.json`, fresh DB marker, and real BASE_URL are **not** provisioned in this pass (by design; Codex/executor prep + independent tester).
- Default `playwright.config.ts` `webServer` still uses `build:e2e` trial build; real runs must target `PHASE5_REAL_ACCEPTANCE_BASE_URL` against a non-stub frontend/API. Structural UI markers should catch accidental trial use.
- Full live Normalizer/Profile/locator/history paths remain `not_run` until `ALLOW_LIVE_MODEL=1` and isolated inputs exist.

## Rerun Requests Or Next Step

1. **Executor (not this suite):** prepare workspace isolation copy + `browser-cases.json` for D001-II / MG-K10-SAR-III; create empty `DATA_DIR` and write fresh marker; start real API + production frontend.
2. **Independent tester:** set the env vars above (including `ROLE=independent_tester`), then run:
   `cd frontend && npx playwright test e2e/phase5-real-acceptance.spec.ts --project=desktop-1080p`
   Add `PHASE5_REAL_ACCEPTANCE_ALLOW_LIVE_MODEL=1` only when intentionally invoking real OCR/Normalizer.
3. **Codex question:** Should live acceptance use a dedicated `playwright.phase5-real.config.ts` (no `build:e2e` webServer), or is BASE_URL-only against an externally started production stack the frozen contract? (Authorized writes did not include a new config file.)
