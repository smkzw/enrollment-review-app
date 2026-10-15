# Conference Context: phase5-slice58j-d001-phase-evidence-design-20260826

Created: 2026-08-26 04:31:07
Objective: 以只读独立顾问身份挑战 D001 II 人工控制矩阵的期别正向依据闭包设计。审阅当前 82 行闭包矩阵、1,840 单元冻结清单、期别 Agent 合同和 5.8d 检查点，回答：如何只针对矩阵实际引用的 152 个单元建立可回源的 selected/opposite/shared/unresolved 依据视图；如何区分共同章节的正向共用依据、仅未限定期别、对侧期引用、II期流程表、表5及结核妊娠等异质结构；哪些结论可确定性派生，哪些必须真实语义 Agent 或 Codex 临床核对；如何用最小代表包而非全跑137包证明闭包；列出会导致治疗后污染、重复计数、错误跨期共享或伪完整声明的反例和验收门槛。不得修改文件，不得宣称最终医学验收。
Task type: `high_risk_contradiction_review`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Visual/design/HTML/PPT tasks use a Codex-led panel with no sub-venue chair. The effective visual participant chain is ``; it is filtered against the actual execution route nodes recorded below before dispatch.
- Chinese labels or Chinese sentence review is handled directly by Codex and does not start a conference.
- Other complex, logic-heavy, evidence-sensitive, artifact-heavy, code-review, and high-risk contradiction work uses a Codex-chaired panel with no sub-venue chair. Participant 1 is night Pi/Alibaba `qwen3.8-max` (xhigh) -> Pi/OpenCode Go `muse-spark-1.2-contributor` (xhigh) -> Kimi Code `k3-256k` (high) -> Codex subAgent `gpt-5.6-luna` (max), and day Pi/OpenCode Go Muse (xhigh) -> Kimi Code K3 (high) -> Codex Luna (max). Participant 2 is Cursor `auto`, with Grok Build `grok-4.6` (medium) and Pi/cms-router `minimax-m3` as fallbacks. Codex remains the final authority.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `phase5-slice58j-d001-phase-evidence-design-20260826`
- Execution evidence status: `no linked execution packet`
- Excluded provider/model nodes: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/coverage_manifest.json`：当前冻结全文清单，1,840 个结构单元；不是完整声明。
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/d001-ii-control-matrix-closed.json`：82 行人工控制矩阵的当前来源闭包副本，`claims_complete=false`。
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/d001-ii-control-matrix-closure-report.json`：来源、关系与期别阻断报告。
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/d001-ii-cross-section-controls-closed.json` 及对应闭包报告：25 行其他章节/流程控制子集。
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260826_PHASE_PACKING_AND_RATIONALE_ACCEPTED.md`、`CHECKPOINT_20260826_D001_MATRIX_SOURCE_CLOSURE_ACCEPTED.md`：当前安全边界与下一动作。
- `app/agents/phase_applicability.py`、`app/protocols/phase_applicability.py`、`app/domain/contracts/phase_applicability.py`：期别语义输入、Agent 输出与确定性门禁合同。
- `research/d001-ii-control-matrix.json` 与 `research/d001-ii-official-flow-controls.json`：人工矩阵的只读来源层。源 DOCX 不在本轮初始阅读范围；如确需核对原文，只读使用冻结清单已保留的逐字摘录和来源位置，并把不足列为后续 Codex 核对，不自行扩展到工作区外原始资料。

## Scope

- In scope：挑战 152 个被矩阵实际引用单元的期别证据分类、确定性/语义责任边界、代表包选择、反例和验收门槛；明确每项建议所依据的文件与字段。
- Out of scope：修改任何文件、运行全部 137 包、解构 MG-K10-SAR、审核受试者、浏览器/视觉试用、建立最终医学结论或把旧人工矩阵视为无条件真值。

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.
- 至少指出一种会把“未限定期别”错误升级为共同适用的路径，以及一种会把治疗后访视内容污染入组前控制的路径，并给出可测试的阻断门槛。
- 给出覆盖共同章节、明确 II 期流程、混合表格、跨期引用、结核/妊娠/结果有效期等异质结构的最小代表包策略，而不是只按数量抽样。

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

- 2026-08-26 04:31:07: Conference initialized by `hermes_workflow_guard.py init-conference`.
