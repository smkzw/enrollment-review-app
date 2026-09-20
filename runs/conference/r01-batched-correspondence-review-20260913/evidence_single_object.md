I'll start with the conference context and venue plan, then audit the frozen R01 design, code, and real-run artifacts as a read-only evidence review.Context files are mostly placeholders. Next I’ll pull the frozen design, binding code, tests, and the real R01 probe artifacts.Binding code is in. Next I’ll pull the focused tests, the r4 probe artifacts, and the job v2 vs v3 contract.Inspection starts showing the duration/diagnosis mix-up. I’ll keep sampling candidates, scheduler tests, and agreement logic.Candidate inspection already shows the duration/date_range and age-conflict cases. I’ll now verify those against blobs, frozen predicates, evaluator consumption, and scheduler tests.I’ll query the isolated job payload and a few request/response blobs in read-only mode to check contract version, locators, and receipts.# Conference Output: r01-batched-correspondence-review-20260913 - evidence_single_object

## Output

本角色为只读证据审阅，不是 Codex 终审，也不是临床/监管验收。未改代码、未改病例、未调用模型。会商上下文与主场计划文件当时仍为 TODO 占位；实际审阅以设计 §17.1.1、T1、当前绑定代码/测试，以及隔离实跑 `artifacts/review-20260912/r01-binding-probe-20260913-r4` 为准。

---

### Evidence

**范围与合同**

- 设计 §17.1.1：`supported_requirement_ids`、`FactRuleLink`、`PredicateObservation` 均不是已核实原子语义绑定；候选不得当已验证绑定接入；结构检查不能独自证明语义正确；自动采信仍须隔离评测与用户接入确认。
- T1：绑定链按 §17.1.1 走冻结输入 → 受限候选 → 验证记录 → 统一消费；不得用 `exists` 放行未核实语义；当前 strict xfail 只是缺陷证据。
- 当前代码合同 `predicate-binding-candidate-job/v3`（`app/services/predicate_binding_job.py:28`）。r4 实跑作业 `6d376516cead4ec29dead95ff8906492` 的 payload `contract` 为 **v2**，无 `execution_control`，12 个 `read:*` 步骤彼此无依赖，仅 `summary` 依赖全部读取。
- r4 冻结输入 `075a8198…`：2 组件 / 3 触发谓词 / 0 例外谓词 / 516 事实 / 342 定位。组件为 `IN-01` 年龄 18–75 周岁（`gte 18 周岁`、`lte 75 周岁`，`requires_professional_judgment=false`）与 `IN-02` 既往明确病史时长 `gte 2 年`（`requires_professional_judgment=true`）。6 批覆盖全部 516 事实、342 定位；24 个 locator 跨批重复出现（按事实装包，同源定位可随不同事实进入不同批）。
- 路由：A=`zhipu-coding-plan`/`glm-5.3-flash`/`high`/`65536`；B=`mtplx`/`mtplx-flash-next-optimized-speed`/`xhigh`/`65536`。作业 `completed`，`accepted=false`，全部读取 `status=unverified`。候选作业未注册到正式求值。

**结构校验实际挡住了什么、没挡住什么**

- `validate_predicate_candidates`（`app/llm/predicate_binding_candidates.py:122-153`）只核：条件覆盖、`fact_id`/`locator_id` 在冻结范围且 locator 属于该事实、所选 `fact_attribute` 非空、摘录非空、未核实原文条件不得出候选、分批不得引用本批未给事实。测试明确写 “Reference checks only; these synthetic candidates are not clinical gold.”
- `fact_attribute` 合法值为 `value|date_range|record_time|assertion_basis`（同文件:51）。存在性通过 ≠ 该属性就是谓词要比较的标量。
- r4 全部 55 条候选：locator 均属于对应事实、所选属性非空、`source_excerpts` 与冻结摘录 0 不一致、请求 blob 不含 `api_key`、响应 `finish_reason=stop`。这只证明引用合同成立。

**两模型一致性（精确键 = predicate_identity_sha256 + fact_id + fact_attribute + locator_id）**

| 批 | A | B | 交 | 仅A | 仅B |
|---|---:|---:|---:|---:|---:|
| 0 | 6 | 10 | 5 | 1 | 5 |
| 1 | 4 | 4 | 4 | 0 | 0 |
| 2 | 6 | 2 | 2 | 4 | 0 |
| 3 | 9 | 8 | 7 | 2 | 1 |
| 4 | 3 | 3 | 3 | 0 | 0 |
| 5 | 0 | 0 | 0 | 0 | 0 |
| 合计 | 28 | 27 | 21 | 7 | 6 |

属性分布：`value` 44，`date_range` 10，`assertion_basis` 1。来源强度：`contemporaneous_objective_result` 32，`screening_record_transcription` 18，`unverifiable_source` 5。全部候选 locator `authenticity=degraded`。

**精确一致但语义不能当正确的样本（r4 交集体）**

1. **`date_range` 不是时长标量。** 批 4 两模型 3/3 一致，把 `过敏性鼻炎` 的 `date_range`（年份精度，下界 `2000-01-01`、上界 `2000-12-31`，`source_text` 如 `2000.UK.UK`）绑到 `IN-02-history-duration`。事实 `value` 是诊断名或“开始于2000年，持续”，单位为空。谓词要比较的是 `gte 2 年`。批 3 也对 `季节性过敏性鼻炎` 的 `date_range` 达成一致。模型说明自己把 `date_range` 当“起算点”，但输出合同没有角色字段，求值器若按绑定事实取 `value` 会拿诊断字符串去比 2 年；若把 `date_range` 当观察值则拿日历年区间当时长。
2. **诊断值不是摘录里的时长。** 批 0 交集体里，两模型都选了 `fact:fa9f8244…`（对象“季节性过敏性鼻炎年限”，`value=25`，`unit=年`，**`source_strength=unverifiable_source`**）。仅 A 另用同一 locator 的诊断事实 `assertion_basis`；B 把同一诊断事实的 **`value=季节性过敏性鼻炎`** 当作时长候选。B 独有项还包括 `value="2000年"`、`value="诊断为季节性过敏性鼻炎，年限自2000年起"`，以及摘录“需记录病史X年，请核实”。A 在说明里承认“时长信息仅存在于断言依据中”，这恰好证明 `value` 不是时长。
3. **亚型未定。** 批 4 一致对象是“过敏性鼻炎”，不是方案原文“季节性过敏性鼻炎”。A 自己写了亚型不确定，仍输出 `status=candidates`。
4. **不可用/不可核实来源。** 唯一带时长标量 25 年的一致候选来源为 `unverifiable_source`，摘录是筛选入选标准转录“已核实修正”，不是可核原始病历。locator 降级原因为无页面坐标。
5. **同一来源重复观察。** 同一 `locator-2f81…` 同时支撑年限事实的 `value` 与诊断事实的 `value`/`assertion_basis`。`locator-ca2f…` 支撑两条过敏性鼻炎 `date_range`。提示词写了“同一来源的不同表述不构成独立印证”（`predicate_binding_candidates.py:95`），但输出仍是多条候选，校验器不折叠。
6. **冲突年龄。** 批 1 两模型 4/4 一致，同时绑定 51 岁与 52 岁两个事实到同一年龄谓词。冻结集中年龄类值：51/`岁` 5 条、52/`岁` 2 条、`"51岁"` 无单位 1 条、51/`years` 1 条。现有求值器在多个观察值时返回 `source_conflict`/`UNKNOWN`（`app/domain/expression.py:496-508`），不会“取一条就算过”。
7. **单位与值形态。** 谓词单位是 `周岁`；事实单位是 `岁` 或 `years`，另有 `value="51岁"` 且 `unit=None`。`_canonical_unit` 只做大小写/空白归一（`expression.py:138-141`），`岁` 与 `周岁` 不相等，会走 `unit_mismatch`（测试 `tests/v2/test_contract_logic.py:1804`）。即使绑定对象正确，现求值器也不能拿这些年龄值直接得出 TRUE。

**批内 unresolved 不是全库未见**

- 批 5 两模型对 3 个谓词均为 unresolved；A 明确写“仅表示本批提供的事实尚未对应，不表示年龄核查未做、记录缺失或受试者不符合条件”，并拒绝用诊断存在代替病史时长。这与分批提示（`predicate_binding_candidates.py:109`）一致。
- 若把各批 unresolved 误读成“全部资料未见”，会在已有年龄/病史候选的情况下制造假缺口。

**现求值器消费面**

- `_evaluate_atomic` 仍按 `fact_type` 别名匹配全部事实，再比较 **`fact.value`**（`expression.py:446-520`）。注释写明 “Legacy matching remains until the source-verified binding path is integrated.”
- `PredicateObservation` 带 `truth`/`observed_value`（`app/domain/contracts/review.py:160-167`）。§17.1.1 禁止把候选改名为已验证绑定后让观察去镜像求值结果。
- 因此：交集体不能直接喂给现求值器；即便只喂 `value` 属性，时长/亚型/来源/单位问题仍在。

**调度、失败、取消、回执**

- r4（v2）步骤事件：12 个读取完全串行，重叠对数 0，最大并发 1。墙钟 2026-09-13 05:17:21 → 06:01:33，约 **2652s**。`summary` 约 29s（含 `_verify_current` 重建冻结输入）。
- 当前 v3（`predicate_binding_job.py:64-74`）：每 lane 串行依赖前一批；`execution_control.max_parallel_steps = 1 if local_count==2 else 2`。`LOCAL_PAGE_PROVIDERS = {omlx, mlx-serve, mtplx}`（`page_reader_capabilities.py:12`）。r4 这种 1 本地 + 1 远端组合在 v3 下允许跨 lane 并行 2；双本地仍强制 1。
- 测试 `tests/v2/services/test_predicate_binding_job.py:105-154` 用 Barrier 证明：非双本地最大并发 2，双本地为 1；失败 lane 时作业 `failed_final`、无 summary、两路回执仍可按 SHA 读回（同文件:19-59）。`accepted` 永不 true。
- 并行波次通用测试 `tests/v2/workflow/test_parallel_wave.py:16-63`：一侧已提交检查点在另一侧仍运行时，成功/崩溃/取消均保留已提交回执。
- 绑定作业调用 `run_cancellable`（`predicate_binding_job.py:174-177`；`page_review_cancellation.py:10-34`）。取消抛 `PAGE_REVIEW_CANCEL_REQUESTED`，执行器只 `except PredicateCandidateReadError`。因此：**取消路径可能把已 `_put` 的请求/响应 blob 留在 ArtifactStore，但不写入带 `receipt_sha256s` 的步骤检查点。** 绑定作业本身没有取消专项测试。
- 来源核验：冻结构建走 `EvidenceLocatorRepository.get_many` + `validate_locators`（`predicate_binding_input.py:18-21`）。缺失 locator 拒绝（`test_predicate_binding_input.py:592-602`）。r4 是对已冻结输入的引用复核，不是对原件 PDF 的临床 QC。

**时延（只用实测，不估费）**

| 项 | A (GLM high) | B (MTPLX xhigh) |
|---|---:|---:|
| 6 次调用墙钟合计 | 1202.7s | 1025.7s |
| prompt_tokens 合计 | 175322 | 206976 |
| completion_tokens 合计 | 70735 | 14929 |
| reasoning_tokens 合计 | 62729 | 8320 |
| 候选条数 | 28 | 27 |

- 单次输入约 19k–38k prompt tokens，用户正文约 41k–67k 字符；相对 r2 全量（GLM 137964 / MTPLX 161890 tokens，422.5s / 775.3s）单次输入下降，但 A 总调用时间约 1203s vs r2 423s，B 约 1026s vs 775s。分批降低单次输入 **没有** 降低总时延。
- `runtime-contract.json`：MTPLX 2.11.2 严格 JSON 思考前导默认 **4000 字符**，请求仍为 xhigh、输出 65536。B 的 reasoning_tokens 每批 891–2191，与此前导上限相容，**不能当作无限制 xhigh**。不得把“减输入”说成总时延改善。
- 两路调用时间之和 2228s，墙钟 2652s；差额主要是 v2 串行空隙 + summary 重核，不是模型计费的第二份证据。

---

### Inference

最高影响缺陷：若把“两模型在 `fact_id+attribute+locator` 上一致”当作语义正确或可自动采用的验证绑定，批 4 的 3 条 `date_range` 一致项会把诊断起病年区间当成病史时长证据；批 1 会同时采用 51 与 52。精确一致是引用键重合，不是对象/属性/时间角色/来源强度正确。

这是通用关系问题，不是应按“季节性过敏性鼻炎”或 GLM/MTPLX 名称写死的病例补丁。失败模式是：谓词要的是可比较标量（年龄、时长），候选给的是相邻字段（`date_range`、诊断名、摘录里的数字、同页另一事实）。

现求值器只比较 `fact.value` 且单位需规范化相等。因此：

- 直接值：`value` 的类型/单位族与谓词属性一致（年龄数值+岁/周岁族；时长数值+年族）。
- 派生值：需代码由 `date_range` + 节点锚点计算时长，**不能**把 `date_range` 标成谓词属性本身。
- 仅语境：诊断名、症状、`assertion_basis` 文本、筛选表“请核实”字样，不得进入比较器。

没有这三档区分，任何“一致即采用”或“把候选 fact_id 塞进现求值器”都会在时长条款上出错，并在年龄条款上撞上单位/`source_conflict`。

v3 调度解决的是墙钟，不是正确性。r4 语义证据应冻结为 v2 产物；v3 的并行行为已有隔离测试，不必为证明调度再跑昂贵模型。

---

### Recommendation

**不要做：** 新队列、第二套 harness、按病名/模型硬编码、把 21 条交集体标成已验证绑定、改投影/正式审核去读未核实候选、为提速再跑无限制 xhigh。

**最小可实现下一步（仍不自动采信）：** 在现有候选记录之后、现求值器之前，加一层确定性的对应角色与拒绝器，产出 `unverified | contextual_only | derived_pending | structurally_eligible`，**默认不进入求值器**。

1. **角色由代码判定，不信任模型自报。** 输入已有：谓词 `attribute/comparator/value/unit`、事实 `value/unit/date_range/record_time/assertion_basis/source_strength`、候选 `fact_attribute`。规则示例（通用，不写病名）：
   - 比较型数值谓词且 `fact_attribute=value` 且 `value` 为数且单位族可对齐 → `structurally_eligible`（仍未核实语义/来源）。
   - `fact_attribute=date_range` 且谓词属性是时长/间隔 → `derived_pending`，禁止把区间当标量。
   - `fact_attribute=assertion_basis` 或 `value` 为疾病/症状字符串而谓词要时长/年龄 → `contextual_only`。
   - `source_strength=unverifiable_source` 或 locator 无可用摘录 → 不得升为可消费。
   - 同一 `source_text_sha256` / 同一 locator 的多条候选折叠为一条来源，不计独立印证。
   - 同一谓词出现多个不相等的合格标量 → 保持冲突/UNKNOWN，禁止选第一条。
2. **双源一致只作审计度量，不作采用门。** 先做角色过滤，再报告交/差。批 4 交集体必须作为“一致但角色错误”的反例留下。
3. **求值器消费适配器（隔离、默认关闭）：** 仅当显式打开实验开关时，用 `structurally_eligible` 的 `fact_id` **替换** `_evaluate_atomic` 的 fact_type 别名集合，比较逻辑不变。专业判断谓词即使有标量仍不得自动 TRUE。`PredicateObservation.truth` 仍只能来自求值器，不能来自模型。
4. **确定性检查必须先于用户批准边界**（夹具用 r4 采样，去标识、不写产品提示）：
   - `date_range` ≠ 时长标量（批 4 三条一致项）。
   - 诊断 `value` ≠ 摘录中的“25年”（批 0 A `assertion_basis` / B `value`）。
   - 亚型/对象字符串不等同于谓词对象（过敏性鼻炎 vs 季节性条款对象）→ 不得因 fact_type 病史而合格。
   - `unverifiable_source` 不得变为可消费。
   - 同源重复不增加证据条数。
   - 51 与 52 冲突 → UNKNOWN，不得任选。
   - `岁`/`years`/`"51岁"` vs 谓词 `周岁`：要么确定性单位族对齐，要么诚实 `unit_mismatch`；禁止静默通过。
   - 批内 unresolved ≠ 全局未见。
   - 合法正例：同一年龄 `value` 同时支持上下界两个谓词；同一合格时长标量在来源核实后可支持时长谓词，但仍受专业判断合同约束。
   - 伪造 locator、属性为空、跨批引用：保持现有拒绝。
5. **调度：** v3 代码与测试可保留；新语义探针不是正确性前置。若以后要测墙钟，用现 v3 在隔离副本跑，预期混合本地/远端同批 A/B 重叠，双本地仍串行；不得为对比而放开 4000 字思考前导。

**可在隔离内自主推进：** 角色/折叠/冲突/单位族的纯函数与夹具测试；把 r4 候选投影成夹具（只读复制，不改原工件）；求值器适配器的默认关闭实验与 xfail 对照；v3 调度回归（已有）。

**仍须验收批准才可：** 打开适配器接到实时投影/正式审核；任何“一致即绑定”阈值；把 `unverifiable_source` 或筛选转录当作明确病史；单位族映射是否把 `岁=周岁` 视为可比较（这是临床口径，不是传输细节）；扩大到 81 组件或例外谓词；宣称 R01/T1 完成。

---

### Uncertainty

- 未打开原件图像/PDF，未做临床 QC；摘录相等只证明冻结文本一致。
- 本探针只有 IN-01/IN-02，无例外谓词，不能外推触发/例外分绑。
- r4 为 job v2 串行；v3 并行未在此次真实双模型墙上验证。
- 绑定作业取消时检查点是否挂上 `receipt_sha256s` 未经专项测试；通用 runner 证明的是已提交步骤保留。
- `summary` 29s 未逐项剖析，推断含 locator 重核，不是模型时间。
- 81 组件冻结能力（输入构建测试）≠ 本 2 组件候选质量。
- 批 5 对“诊断名无时长则 unresolved”较稳；批 4 对同类诊断却输出 `date_range` 候选——模型不稳定，不能用提示词微调代替角色校验。

---

### 最重要异议、替代方案、决策点、给 Codex 的有界问题

**异议 1（最高）：** 用双源精确一致当验证。批 4 已提供反例。替代：角色过滤优先，一致率只报告。

**异议 2：** 把“接上现求值器”理解成把候选 `fact_id` 丢进 `_evaluate_atomic`。现比较器读 `value`+单位，会把诊断字符串、`51岁` 文本、`岁` vs `周岁` 变成错误 TRUE/FALSE/单位失败。替代：只消费 `structurally_eligible` 的数值 `value`，派生/语境保持未核实。

**异议 3：** 把 v3 并行或再减输入当作质量或时延胜利。实测分批已增加总调用时间；B 仍受 4000 字思考前导限制。替代：正确性夹具先行；时延只引用回执。

**异议 4：** 提示词已禁止算时长/同源互证，但输出合同允许 `date_range` 绑定到时长谓词，校验器只查字段存在。这是合同缺口，不是模型偶然。

**安全暂定路径：** 保持 r4 `accepted=false`、不接投影；在隔离测试中实现角色拒绝器与上述反例；求值器实验开关默认关。不阻塞该实现去等另一次模型实跑。

**请 Codex 裁定的有界问题**

1. 对应角色是做成代码对现有字段的判定（推荐），还是给模型加必须由代码复核的枚举？后者若不强制复核，批 4 仍会自报“起算点对应时长”。
2. `岁`/`周岁`/`years` 的单位族对齐，是否纳入本步确定性绑定消费，还是单独 T1 单位票？未裁定前，隔离适配器应对年龄保持 `unit_mismatch`，避免假通过。
3. IN-02 在来源未核、且 `requires_professional_judgment=true` 时，即使出现数值 25 年，是否规定为永不可在本步给出 TRUE（推荐），只允许“有时长候选、仍未核实”？
4. 是否授权把 r4 采样事实/候选做成去标识夹具纳入仓库测试？这不改病例库，但会固化真实文本片段。
5. 取消路径是否要求本步补“`run_cancellable` 取消后仍把已 `put` 的 receipt SHA 写入 incomplete 检查点”的测试，还是记为已知限制、不挡角色校验？

以上任一未答都不阻止隔离角色拒绝器；它们只决定求值器实验开关能否打开，以及年龄单位能否在隔离中视为可比较。R01 绑定链在本审阅下仍开放，不得标完成。
