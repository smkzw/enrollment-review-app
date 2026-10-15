# Conference Context: phase5-slice61aq-native-pdf-structure-entry-audit-20260829

Created: 2026-08-29 07:24:17 CST
Objective: 只读独立审查 Phase 5.8d 原生文本 PDF 方案结构入口。核查：一、原始 PDF 字节与来源哈希身份是否保持；二、页码、文本区间与坐标框定位是否可验证且不制造伪精确；三、扫描件、加密、损坏及文本不足 PDF 是否失效关闭；四、DOCX 冻结序列化和 D001 指纹是否保持兼容；五、真实 120 页 MG-K10-SAR PDF 的重复确定性验证能否支持“原生文本 PDF 入口已工程接受”的有限结论。必须明确区分入口能力与标题/表格语义恢复质量；后者尚未达到 DOCX 等价。仅审阅，不修改文件，不运行临床模型，不发布控制点。输出具体文件/测试证据、阻断问题、非阻断后续项和接受/拒绝结论。
Task type: `code_open_audit`
Risk: `medium`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
- This packet uses one Codex-led conference object (`general_single_object`) with no sub-venue chair. Its effective `CST` route chain is `codebuddy-cli/deepseek-v4-flash:max -> grok-build/grok-4.6:medium -> cursor/cursor-grok-4.6:medium`; it is resolved once at packet creation and filtered against the actual execution route nodes recorded below before dispatch.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `phase5-slice61aq-native-pdf-structure-entry-20260829`
- Execution evidence status: `linked`
- Excluded provider/model nodes: `codebuddy-cli/glm-5.3-flash`, `mtplx/mtplx-qwen38-27b-optimized-quality`, `openai-codex/gpt-5.6-luna`
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

- 2026-08-29 07:24:17 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
