# Conference Context: v3-abc-retro-20260918

Created: 2026-09-18 09:49:52 CST
Objective: 复盘入排审核系统V3分工A/B/C切片：本地MTPLX属主启动与语法约束回退（合同入提示词）修复、IN-02本地修订成功、门禁28→5、剩余5项性质判定（真临床未决vs模型能力）与下一步构建方向（发布路径/B资料链/解释材料通道）
Task type: `complex_delivery_conference`
Risk: `medium`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`general_single_object`) with no sub-venue chair. Its effective `CST` route chain is `zcode/zcode/glm-5.3-flash:max -> codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> codex-subagent/codex/gpt-5.6-sol:medium`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `v3-abc-retro-20260918`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- `.trellis/tasks/09-11-e2e-eligibility-review/RETURN_A.md`（含"最终增量"节：门禁 28→5 过程、模型路由记录、修订剧本）
- `.trellis/tasks/09-11-e2e-eligibility-review/RETURN_B.md`（资料勘查：31001 五份扫描件、OCR 就绪、P1 硬依赖 A 发布）
- `.trellis/tasks/09-11-e2e-eligibility-review/implement.md`（六项状态与交接快照）
- `.trellis/tasks/09-11-e2e-eligibility-review/design.md`（P0 短图：方案/资料两链真实断点）
- 运行证据：`data_v2/blobs/protocol-semantic-{batches,preview,route-audits}/769ae98f…/`；`artifacts/mtplx-owned-runtime-20260918/logs/`（装卸生命周期+kernel 缺陷服务端日志）
- 实时状态：`curl http://127.0.0.1:8902/api/v2/protocol/deconstructions/769ae98f76b4450ca810fbbdd9f518d8/integrity`（当前 blocking=5）

## Scope

- In scope：V3 A/B/C 切片当前状态复盘；本地 MTPLX 接入改造评价（属主启动/语法回退/合同入提示词/瘦后缀绕行 kernel 缺陷）；剩余 5 项门禁问题定性（真临床未决 vs 模型能力）与处置路径；发布策略与 B 链下一步。
- Out of scope：修改源码/数据库/临床原件（本会商为只读咨询）；重新裁决 V3 已确认方向（内置方案 Agent、非全量双读等）；C 包执行细节。

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.

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

- 2026-09-18 09:49:52 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
- 2026-09-18 10:2x CST: Codex filled source-of-truth/scope and main-venue plan; 关键事实补充：IN-02 已由本地 Flash-Next 修订成功（revision 15）；EX-04/IN-06/EX-07 在 Flash-Next（瘦合同后缀绕行 kernel 500 后）与 27B-Quality 下各 ≥2 轮失败，错误形态为普通格式滑误（缺 source_span_ids / 多 component_id / 超时），两轮无进展边界已达成；当前 blocking=5（EX-04×3、EX-07x、IN-06-C2-P1）。

## 待裁决问题（Codex 提请会商）

1. 剩余 5 项定性：EX-07x/EX-04 回溯锚点类（原文未写）是否应定性为"必须走 register_interpretation_sources 等用户澄清"，不再消耗模型迭代？IN-06 来源绑定/EX-04 频次形式是否值得 GLM 恢复后再试一轮？
2. 发布策略：门禁把"按处方保留未决"仍计为阻止发布（TIME_ANCHOR_UNRESOLVED），产品上是否存在不伪造的最小修复（如该类问题在 unresolved_items 显式存在时降级为非阻塞+报告披露）？何时修、谁来修？
3. B 链最短路径确认：发布→建 subject 31001→上传血常规→original-page-images/v1→GLM-OCR-bf16 主读取→事实发布→原件回看。该顺序是否遗漏必要接点？
4. 本地 MTPLX kernel 缺陷（qsa_prefill JIT 500）的处置：瘦合同绕行是否足够稳定？是否需要把"合同入提示词"的mtplx特例与"语法约束"做成可配置而不是硬编码 frozenset？
5. 十五次修订全部通过范围守卫（兄弟零变化）——局部修订证明已达成。C 包开始前还缺哪些 A 侧证据？
