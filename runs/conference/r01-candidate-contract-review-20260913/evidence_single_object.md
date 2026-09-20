I'll start with the conference context, the plan, and the frozen candidate-contract files so the review is grounded in the actual v3 code and probe artifacts.Context and plan are mostly placeholders, so I’ll audit the candidate modules, tests, and design T1 next.Next I’ll pull design §17.1.1, T1, and the r1/r2 probe artifacts so the review can cite real failures rather than the code path alone.Probe artifacts are in the workspace; I’ll read r1/r2 receipts and failures first, then check how JobRunner currently consumes this path.r1 overflow and r2 excerpt-mismatch are confirmed. Next I’ll inspect the r2 candidate payload, request sizes, and existing JobRunner consumers.r2 GLM still overclaims and retypes excerpts; I’ll check the frozen-input size mix, ContractModel extras, and the closest JobRunner pattern.I'll run a read-only v3 validation against the stripped r2 GLM payload and confirm the current tests still pass.# Conference Output: r01-candidate-contract-review-20260913 - evidence_single_object

## Output

只读审阅结论：v3 只把「模型重抄摘录」改成「引用 locator 后由代码取回冻结原文」，**不能**阻止错误链接，也**不能**当作 r2 或临床签收。用同一份冻结输入（`075a8198…`）把 r2 GLM 候选去掉 `excerpt` 后送入现行 `validate_predicate_candidates`，**结构校验通过**（3 条谓词、14 条候选，含出生日期当年龄、`fact_type` 对应、阈值/推算/互为印证）。r2 不得记为 v3 接受。下一步只应接隔离 JobRunner 持久化未核实候选；**禁止**写入求值器/FactRuleLink/PredicateObservation。

### Evidence（观察）

**代码与合同**
- `PROMPT_VERSION = predicate-binding-candidates/v3`。`PredicateFactCandidate` 仅有 `fact_id` / `fact_attribute` / `locator_id` / `correspondence_explanation`；`ContractModel.extra="forbid"`，无 `truth`。
- `validate_predicate_candidates` 只做引用闭包：谓词全集覆盖、`source_status==verbatim` 才允许 `candidates`、`locator_id ∈ fact.locator_ids`、属性非空、locator 摘录非空。**不读** `asserted_object`、单位、比较符、阈值，也不核对说明是否超范围。
- `read_predicate_candidates` 在校验通过后按所选 `locator_id` 填 `source_excerpts`（冻结原文）。调用方自管预检/并发/持久化；未接 JobRunner。
- `predicate_binding_prompt_input` 仍把 **516 条事实表 + 342 条来源表（含 excerpt）** 一次送给模型。本工作树对该冻结输入构建的 v3 user 正文约 **294 699** 字符（facts 表 221 781，sources 表 80 041，components 4 397）。
- `build_predicate_binding_frozen_input` 即使传入 `component_ids`，事实仍是当前校正头全集，不按组件裁事实。

**r1 / r2 探针（同一 `frozen_input_sha256=075a8198debacde546e1ade580f722e1c3ce2cbf8ff1d553e9958ee3b0c2b45c`）**
- 冻结范围：2 个组件（IN-01 年龄 18–75 的 2 个触发谓词；IN-02 既往明确病史≥2 年 1 个触发谓词）、516 事实、342 定位、5 份源文档。不是全规则集 7 组件。
- r1/v1：GLM `prompt_tokens=274871`，`stop`，失败 `候选摘录不是该事实来源的逐字内容`（至少 2 处摘录≠冻结原文，其一把截断主诉补成「于2000年确诊为…」）。MTPLX 400 `BadRequestError`（上下文溢出，无正文）。
- r2/v2：表格压缩后 GLM `137964` / MTPLX `161890` tokens。GLM 14 条候选与冻结摘录 **0 处不等**；信封 `accepted: false`。MTPLX `stop` 后仍失败同一摘录逐字错误（3/6 处截断或改写，例如 `'性别：男 年龄：51岁'` vs 冻结 `'姓名： 性别：男 年龄：51岁 登记号：'`）。
- r2 GLM 说明中的超范围内容（原文摘录）：`fact_type为年龄证明，与证据要求…直接对应`；`51不低于18周岁阈值`；出生日期事实 `56560a06`（`asserted_object=出生日期`，`value=1973-8-11`）`结合…访视日期2025-08-08推算年龄约51周岁`；`可与年龄证明事实互为印证`。病史侧把 `date_range`/`assertion_basis` 推算「约25年，不低于2年」。
- 产品路由与回执一致：main-A `zhipu-coding-plan` / `glm-5.3-flash` / high；main-B `mtplx` / `mtplx-flash-next-optimized-speed` / xhigh。无个人 harness。

**只读复现（本会话，无模型调用）**
- 去掉 r2 GLM 的 `excerpt` 后，现行 v3 校验 **接受** 全部 14 条。
- 去掉 r2 MTPLX 的 `excerpt` 后，现行 v3 校验 **同样接受**（覆盖 3 个谓词）。
- 若候选仍带 `excerpt` 字段：`extra_forbidden` 拒绝。

**现网消费（仍是类型别名，不是本候选链）**
- `eligibility_review_projection._component_candidate_types` 把组件内 **全部** `evidence_requirements.fact_type` 复制给每个谓词；`expression._evaluate_atomic` 注释写明 legacy matching。IN-01 要求 `fact_type=年龄证明`（描述却允许出生日期或年龄）；IN-02 要求 `病史记录`。
- `tests/v2/test_predicate_semantic_binding_boundary.py` 仍有 **strict xfail**：类别别名不能证明触发/例外。T1 已声明此项不是完成证据。
- `app/workflow/**` 与 `JobService` **没有** `predicate_binding` job_type。

**测试边界**
- 配套测试是引用/哈希/截断重试/429，合成夹具，明确「不是临床金标」。`excerpt`/`truth` 被拒是因为多余字段，不是语义核对。
- 未在本会话重跑「45 passed」；不把它当作本角色的临床或接线接受。

### Inference（推论）

1. **最高影响缺陷**：v3 的「来源指针取回原文」提高的是 *选了哪条 locator 的可审计性*，不是 *该对应是否成立*。r1 模型补全截断摘录、r2 MTPLX 改写摘录——这些失败会被 v3 消掉，同一 `fact_id+locator_id` 会带着**完整冻结原文**成为 `PredicateCandidateRead`。若下游只检查「有 `source_excerpts` / 校验通过」，错误链接会被包装成已锚定证据。
2. 反例（r2 GLM，结构已能过 v3）：`fact:56560a064a836ccc40b3cd12e2df6b02` 的 `value=1973-8-11` 绑到 `IN-01-age-gte-18` 的 `fact_attribute=value`。取回原文只会是 `'出生日期: 1973-8-11'`，**不会**变成 51 岁，但说明文本已完成非法推算。确定性求值若拿 `fact.value` 去比 18，日期字符串不是年龄。
3. 当前别名路径只吃 `年龄证明`（该冻结集里主要是 `fact:1a3419a0…` 值 51）。若用 v3 候选替换别名，进入求值的事实会**变多**（出生日期、年龄记录 51/52、页眉年龄），类型证据范围扩大，不是收紧。
4. `correspondence_explanation` 可写满阈值方向、互为印证、`fact_type` 对齐；schema 无 `truth` 挡不住自然语言超结论。`assertion_basis` 被用来承载「25年」散文，后续代码没有对 basis 文本做数值比较的合同。
5. 输入体积主因是 **516 事实 + 342 摘录**，不是 2 个组件（组件仅 ~4.4K）。v3 不再让模型回写摘录，**几乎不减** 138K/162K 输入。按源文档切分：5 档，最大一份约 209 locator / 254 事实 / ~364K 原 JSON 字符，粗估仍可能到满包的一半以上；不配「本步 locator 白名单 + 跨步合并」会漏冲突（51 vs 52）或让模型引用未进入本步 prompt 的 `locator_id`（事实行仍列出全部 `locator_ids`，现行校验仍会放行）。
6. 按 `evidence_requirements.fact_type` 裁事实会丢掉描述允许的出生日期，属于临床损失，且是项目字段偶合，**不应**作为本步裁剪。
7. 首次真实 v3 调用若模型仍输出 `excerpt`（输入表里还有摘录，r2 两个模型都输出了），会在 `extra_forbidden` 失败——这是失败关闭，不要改成静默丢掉字段。

### Recommendation（建议）

**可以不经新算法批准就做的工程（仍须用户确认后再自动采信）**
1. **最小接线**：新增隔离 job（仿 `judgment_search` / `fact_normalization`：JobService 建步、JobRunner 执行、checkpoint 存原文）。载荷：`review_episode_id`、`component_ids`、`frozen_input_sha256`、`prompt_version=v3`、双 `PageReaderRoute`。步骤：`read:main-A`、`read:main-B`；失败保留 `PredicateCandidateReadError.completions`。汇总只记录未核实候选与双源分歧，**单车道成功也不得升格**。
2. **共享消费者**：工作台只读展示「未核实对应 + `source_excerpts`」。`evaluate_component` / `FactRuleLink` / `PredicateObservation` / `supported_requirement_ids` **一律不读**该结果。
3. **补隔离反例测试**（无模型）：(a) 去掉 excerpt 的 r2 GLM 载荷现行会通过——锁定这个洞，避免有人把「校验通过」写成验收；(b) 多余 `excerpt` 拒绝；(c) `source_excerpts[locator_id] === 冻结 excerpt`；(d) 出生日期事实绑到年龄谓词在引用层通过 ≠ 语义通过。
4. **先做一次同冻结输入的 v3 双源探针**（仍隔离 artifacts），量 GLM/MTPLX 的 `prompt_tokens`。只有再次触顶再按源文档分步；合并规则须先写：候选并集、仅当全部批次 `unresolved` 才整谓词未对应、每步校验的 locator 必须出现在**该步** sources 表。

**自动采信 / 替换别名 / 改 ComponentDecision：不得在本步做。** 仍受 §17.1.1 第 3–5 步、T1「隔离评测 + 接入确认」、strict xfail、留出验证约束。

**不要做**
- 新框架、第二套调度、按病种/药名裁剪、把 r2 当 v3 金标、用说明文本关键词做「语义门」冒充第 3 步。
- 年龄 gte/lte 的确定性计算可另开小步（对象=年龄且值为数字才比较；出生日期只进日期→年龄代码路径），**不要**塞进本次 JobRunner 最小接线。

### Uncertainty / 限制
- 无 v3 真实模型调用；294 699 字符到 MTPLX token 的换算未测（r2 约 395KB→GLM 138K / MTPLX 162K）。
- 探针只有 IN-01/IN-02；7 组件全量会加大输出覆盖压力，事实侧体积几乎不变。
- 未打开临床库/凭证；未做浏览器/求值器接入。
- 未重跑父任务 45 项测试。

### 对 Codex 的异议、决策点和有界问题

**异议**
1. 「取回原文 = 可追溯」被当成「不会伪装错误链接」——对人工读摘录成立，对自动消费不成立；v3 会让 r2 超范围候选看起来更正式。
2. 「接到 JobRunner 和共享消费者」若理解成替换 `_evaluate_atomic` 别名，会把出生日期/页眉年龄送进正式结论，比现状更差。
3. 源文档分批不是零损失，除非先规定合并与 locator 白名单；不要在无 v3 token 实测时上页面级大批次。

**决策点（建议默认）**
- D1：Job 在任一车道失败时仍持久化回执，状态保持失败/未核实，不产出消费对象。**建议采用**（对齐 r2：GLM 有候选、B 失败、整体不接受）。
- D2：求值器继续走 legacy 别名，直到独立语义核对存在。**建议采用**。
- D3：模型多写 `excerpt`：保持 `extra=forbid`。**建议采用**。

**有界问题**
1. 下一实现回合是否授权「同冻结输入的 v3 双源探针」作为 JobRunner 之前的必做门，还是探针必须已经跑在正式 job 里？影响顺序，不改变「不得进求值器」。
2. 只读工作台展示未核实候选是否算本次「共享消费者」，还是消费者严格定义为 projection/evaluator？我按后者 fail-closed：展示可以，求值不行。
3. IN-01 是否允许「出生日期事实」作为候选（属性仍是日期，计算留给代码），还是候选层就必须拒绝对象≠年龄？这改变隔离测试的期望，而不是本角色可签收的临床规则。

**本角色未主张最终接受。** Codex 保留临床/求值器/生产写入权威。
