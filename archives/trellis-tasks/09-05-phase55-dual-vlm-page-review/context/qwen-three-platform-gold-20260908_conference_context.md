# Conference Context: qwen-three-platform-gold-20260908

Created: 2026-09-08 22:22:08 CST
Objective: 独立复核真实研究方案与病例横评金标及测试框架，三平台Qwen Flash-Next xhigh，产品独立harness，两维度：方案解构与固定条款病例识别审核；只读临床来源，核对金标完整性、时间节点、书面判断、摘录真实性，禁止修改产品或启动本地模型。
Task type: `C02`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

## Authorized Read-Only Source Packet

Absolute repository root: /Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile . Read-only access to the following root-relative paths is explicitly permitted beyond the runner working directory. No writes, no model/server calls, no credentials, no benchmark candidate outputs. Use image tools to actually inspect original pages; source text alone does not verify visual gold.

- artifacts/phase55-model-comparison/20260907/gold-sar-lab-page9-units-v2.json
- artifacts/phase55-model-comparison/20260907/gold-sar-biochemistry-page17.json
- artifacts/phase55-model-comparison/20260907/product-input-v2/input.json (fixed SAR ClausePack, episode, source identities)
- artifacts/phase55-model-comparison/20260907/product-input-v2/pages/ (original rendered pages; indices 0, 9, 17, 18 in input.json prioritized)
- artifacts/phase55-model-comparison/20260907/product-source-d001-sa07007-v1/input.json and its pages/ (D001 indices 0, 42, 44 prioritized)
- artifacts/phase55-model-comparison/20260907/protocol-native-runs/d001-glm-low-v1/manifest.json; its source.path is the actual DOCX, explicitly allowed read-only.
- app/agents/protocol_deconstructor.py; app/llm/page_review_harness.py; app/domain/contracts/page_review.py; app/domain/contracts/clause_pack.py; docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md

Test design: three exact Qwen platform/weight combinations, each xhigh, input ceiling65536 and output ceiling131072, platform-default other sampling. Reuse actual product prompt/schema; gold never goes to candidates. Independent dimension1 native protocol deconstruction preserves official numbering, branch logic, stage applicability, cross-section restrictions and locators. Dimension2 holds published ClausePack constant across candidates, tests visual observations and evidence links, not fabricated page-level final inclusion decisions. Deterministic assessment remains code-owned. Missing researcher written judgment is an unresolved clinical finding, not automatic fail/pass or mandatory user interruption. Assess metric completeness; do not assert clinical acceptance. Return source-grounded expected facts and any corrections to draft gold, with exact image locator; state inspected vs uninspected scope explicitly. For protocol full-gold do not treat the published product ClausePack as unquestionable: compare source DOCX, identify omissions/overclaims relevant to screening/baseline. No need to enumerate unrelated treatment follow-up.

Codex retains final decisions. No external web research or further delegation. Use fresh review context without prior candidate answers. If source gold cannot be fully validated, identify exact remaining scope; do not claim full completeness from sampled pages.

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`visual_single_object`) with no sub-venue chair. Its effective `CST` route chain is `google-antigravity/gemini-3.7-flash:high -> zcode/glm-5.3-flash:max -> opencode-go/muse-spark-1.3-contributor:high -> cms-router/cms-model:high -> openai-codex/gpt-5.6-luna:max`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `qwen-three-platform-gold-20260908`
- Execution evidence status: `no linked execution packet`
- Excluded provider/model nodes: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- TODO: Add authoritative local files, extracts, datasets, screenshots, URLs, or user-provided materials.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: TODO
- Out of scope: TODO

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.

## Parallel Work Rule

For logic-heavy, rigor-sensitive, or artifact-heavy tasks, each participant independently runs the whole bounded workflow and writes a separate output. Leads compare after all available participant outputs are in or explicitly marked pending.

## Timeout Policy

- Participant soft wait: 60 minutes.
- Large-task participant wait: 120 minutes.
- Chair hard wait: 120 minutes.
- Failure rule: Do not fail a model for slow response alone; fail only on terminal error, provider exhaustion/rate limit after controlled retry, empty/truncated retry output, or no useful progress after the high-budget same-session recovery loop. A catalog/auth/transport health preflight timeout or malformed response is diagnostic and must still allow one live route attempt; explicit user routes also proceed when the catalog is stale or incomplete, while a genuinely missing CLI or native transport boundary may block. If a resumable session exists after a step/size boundary, continue it before fallback; repeated identical output/tool evidence triggers the no-progress breaker.
- Pass/turn boundary: one conference prompt is one conference pass. The
  `--max-turns` value controls internal Agent tool-calling turns and is never
  set to 1 for substantive conference execution; generated participant and
  chair commands use the route budgets recorded by the guard.

## Risk Boundaries

- External Agents are advisory; Codex remains final authority.
- Codex owns visual/browser/PPT/PDF/rendered checks, live authority checks, final clinical/regulatory conclusions, and production writes.
- Do not mark a slow model failed solely due to latency.

## Loop Log

- 2026-09-08 22:22:08 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
