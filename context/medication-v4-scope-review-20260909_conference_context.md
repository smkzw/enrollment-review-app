# Conference Context: medication-v4-scope-review-20260909

Created: 2026-09-09 23:40:10 CST
Objective: 只读审阅用药分项v4跨受试者失败与通用用途边界：明确未药物干预却提取疾病日期为use_start；挑战最小修订方案，防止为无药名但明确使用的记录误删事实，不作临床或产品接入验收。
Task type: `C03`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `zcode/glm-5.3:max -> xai/grok-4.6:high -> xai/grok-4.6:high -> openai-codex/gpt-6-astra:low`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `medication-v4-scope-review-20260909`
- Execution evidence status: `no linked execution packet`
- Excluded provider/model nodes: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- scripts/medication_component_experiment.py、scripts/run_medication_component_experiment.py、tests/v2/scripts/test_medication_component_experiment.py。
- 原始模型输入/响应优先：artifacts/phase55-takeover/20260909/medication-components-v4-holdout-page3 和 medication-components-v4-holdout-page4；source.json、pair-*-request.json、response.json、bound.json、comparisons.json。
- 页级来源：同根medication-holdout-31006-targeted-page3/result.json与page4/result.json；真正原件在medication-holdout-31006/originals及pages，provenance.json/manifest.json提供绑定。工具不能看图时如实说明，不将读JSON称目视。
- 校准对照：同根medication-components-v4-prescription、medication-components-v4-page0/page3/page4。预先规则见medication-component-expanded-plan.md。主线程意见见MEDICATION_COMPONENT_ASSESSMENT.md，放在独立检查原始响应之后阅读，不视为权威答案。
- 用户授权只设计/扩测，正式接入需另批；产品模型GLM/Gemini直连，实验全程product_acceptance=false，未修改临床库。
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: 只读检查当前分项提示/合同是否先验把病史当用药、日期/剂量角色丢失及假冲突，提出一个最小通用修订及必须通过的反例。不需要完整仓库审计，不需重复32K以上工件逐文件扫读。可运行聚焦测试且不写缓存（-p no:cacheprovider）。
- Out of scope: 不改文件、不调用产品模型、不写数据库、不读取工作区之外的原临床路径/个人配置、不联网、不递归派发、不作自动接入批准。
- 待挑战方案：先输出有自身原文依据的观察用途（使用/处方/购买/明确未用药/非用药/不明等仅为待评选项），随后限制用药分项。不要只按drug_name=null抹掉日期，因为药名不详的真实使用也可能有时间。不要靠药物名单、疾病名或项目特例修补。区分原文没写剂型与跨页药名残缺；剂量分母不得一律删除。请评估能否保持一轮短提示、不引入平行harness，指出遗漏与可执行最小合同。

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

- 2026-09-09 23:40:10 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
