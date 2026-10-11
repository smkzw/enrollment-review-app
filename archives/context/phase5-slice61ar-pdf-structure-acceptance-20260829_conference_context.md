# Conference Context: phase5-slice61ar-pdf-structure-acceptance-20260829

Created: 2026-08-29 17:01:33 CST
Objective: 只读独立复核 Phase 5.8d 原生文字 PDF 结构质量切片。审查当前工作树中的 app/protocols/pdf_structure.py、app/evidence/pdf_native.py、app/evidence/page_processor.py、app/protocols/source_alignment.py、相关 tests/v2/protocols 与 tests/v2/evidence、scripts/verify_pdf_structure_quality.py，以及 runs/verification/phase5-slice61ar-pdf-layout-structure-quality-20260829 中的固化报告。重点挑战：通用标题识别是否误把数值/时间窗当标题；横线表格及合并单元格是否保持页原生顺序和精确来源范围；页眉页脚是否隔离正文；祖先/后代范围重叠豁免是否会放过无关重复；解码器版本迁移与测试隔离是否正确；真实报告、全量测试和结论是否匹配。不得修改文件，不得读取工作区外原始临床资料，不得自行声称最终接受。输出按严重度列问题、证据、建议和有限结论。
Task type: `complex_delivery_conference`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`general_single_object`) with no sub-venue chair. Its effective `CST` route chain is `google-antigravity/gemini-3.7-flash:high -> opencode-go/muse-spark-1.2-contributor:xhigh -> cms-router/minimax-m3:xhigh`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `phase5-slice61ar-pdf-layout-structure-quality-20260829`
- Execution evidence status: `linked`
- Excluded provider/model nodes: `mtplx/mtplx-qwen38-27b-optimized-quality`, `codebuddy-cli/glm-5.3-flash`, `openai-codex/gpt-5.6-luna`
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

- 2026-08-29 17:01:33 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
