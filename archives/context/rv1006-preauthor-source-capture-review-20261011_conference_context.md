# Conference Context: rv1006-preauthor-source-capture-review-20261011

Created: 2026-10-11 19:49:52 CST
Objective: 只读核验现有先决来源完整捕获与局部补读在作者前执行：预算、范围、保存消费者与恢复不降级，不读临床或调用产品
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> zcode/zcode/glm-5.3-flash:max -> grok/grok-build/grok-4.7:high -> pi/cursor/grok-4.7-high:high -> pi/openai-codex/gpt-6.1-sol:high`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `rv1006-preauthor-source-capture-review-20261011`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- 基础提交 f25f7eeb667cae0570223b739dc349e278341876；本次仅审阅以下冻结工作补丁及相邻定义，不读取真实临床材料。
- `app/agents/protocol_control_deconstructor.py` SHA256 `5b0c90dd5f2b7163493b00b3bdefd5984dc0088b486f3f35abcfc72f7d7e9529`。
- `app/agents/protocol_control_source_interpretation.py` SHA256 `16f455b455587fc81b32844270bb80acf001215c22914e4f9b28e90cc930f0a2`。
- `app/services/protocol_control_execution.py` SHA256 `e89dcc17c835f1929aab24a57376092d3d4f2e22ce371505c428ab2b885506e1`。
- `tests/v2/protocols/test_slice58c_control_deconstructor.py` SHA256 `dad29247adab1886521fc5c4856e5ab20890ed227607a9fd284b82733e624fc7`。
- 可只读相邻引用合同和 `tests/v2/services/test_protocol_control_execution.py`；不得扫描其他目录。测试合成场景，不含病例。Codex实跑两个模块的连接筛选窗口：140 passed / 1624 deselected / exit 0，非全库或临床验收。

## Scope

- In scope: `missing_sequence_source_units`、既有 `source_unit_quotes_cover_source`、抽取的 `complete_source_units`、作者前调用、保存校验及旧局部恢复入口的一致性。检查预算是否重复、历史完成指令是否绕过、未授权语义是否可变、合法成功源能否复用、局部失败是否准确保留。
- Out of scope: 修改文件、运行测试/模型/数据库、读取 .env、tmp、artifacts/raw、真实方案病例、联网、正式采用、签发或执行新会商。仅输出代码级审阅意见。

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.
- 给出至少一个可操作反例或明确未证边界；区分高后果缺陷与可延后建议。补读必须只改允许摘录字段，成功源/兄弟含义不可重写。不要把材料完整捕获说成医学语义已通过。

## Conference Pass Rule

This packet uses one serial Codex-led conference object. Each declared role receives one complete prompt and may use multiple internal tool turns. Codex decides whether a same-session follow-up is needed after reviewing the result; follow-ups do not create a new conference or change the route identity.

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

- 2026-10-11 19:49:52 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
