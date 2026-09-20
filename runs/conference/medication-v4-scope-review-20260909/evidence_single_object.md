All evidence gathered and verified. The provenance chain holds (page_review_ids match the targeted reads; manifest binds the original PDF sha `376da20a…`; I did not view page images — the owner's visual check is recorded in the plan). I'm ready to deliver my advisory report.

---

# Conference Output: medication-v4-scope-review-20260909 - evidence_single_object

## Output

### 1. 总体判断（结论先行）

主线程的最小修订方向（先判观察用途、再限制用药分项、禁止按 `drug_name=null` 抹掉日期）**方向正确且必要**，但按当前表述直接实现会**复现同一缺陷或误删真实使用事实**，因为它没有明确"限制"到底落在哪些分项上。实测失败恰恰不在药名，而在 `times` 和 `ongoing`。修订必须同时改三处才闭合：提示（用途门 + 分项条件化）、确定性校验器（用途一致性硬门 + QC 旗标条件化）、比较器（用途行 + 旗标语义）。一轮短提示可行，不需要平行 harness。

### 2. 证据（独立检查原始工件所得，非转述）

**证据 A — 核心失败（原文级，已核实）：**
- `medication-components-v4-holdout-page4/source.json`：lane A `fact-03` 原文"2. 血压升高，开始时间2025.08.27，持续中，未药物干预。"、`fact-04`"3. 鼻息肉，开始时间：2025.08.27，持续，未药物干预。"——均为明确否定用药的病史记录（`context.target_text` 分别为"血压升高"/"鼻息肉"）。
- `pair-1-lane-0-response.json`（GLM-5.3-flash）：对 fact-03 输出 `times:[{value:"2025.08.27", source_quote:"血压升高，开始时间2025.08.27", role:"use_start", precision:"day"}]`、`ongoing:{value:"持续中", source_quote:"持续中，未药物干预"}`。**source_quote 本身就证明日期属于疾病而非用药**——引用文本里的"血压升高"与"未药物干预"与 role=use_start 直接自相矛盾。Gemini（lane-1）同记录全 null、`times:[]`。fact-04 同型。
- `medication-component-expanded-plan.md` 第39行（调用前冻结的预期）："血压升高、鼻息肉均写明未药物干预；不得当作正在使用降压药或其他药物。它们是带否定范围的病史，不是遗漏药名待填。"→ GLM 输出构成**已度量的语义失败**，非判断口径问题。

**证据 B — 机制定位（代码级）：**
- `scripts/medication_component_experiment.py:188` 系统提示第一句"只处理这一条**用药观察**"——先验把任何送入记录框定为用药记录，无"非用药"输出状态。
- `:200-205` "times 是列表：原文有几条明确时间就输出几条"——**无条件**要求输出原文日期，而 role 词表（prescription_date|use_start|use_end|administration_date|unclear）全是用药语义；"不把就诊或采样日期当作用药时间"只排除了就诊/采样日，**未排除疾病开始时间**。疾病记录的"开始时间"在用药框架下最优解就是 use_start，模型行为在其框架内是"合规"的。
- `:257-259` QC 旗标逻辑：`times` 为空且摘录含日期样式 → `possible_unextracted_time`。结果在 comparisons.json pair-1/2 出现**QC 反转**：填错的一侧（GLM）`qc_flags.a=[]`，判对的一侧（Gemini）反而被标 `possible_unextracted_time`——自动 QC 会把人工复核引向错误一侧。
- `scripts/run_medication_component_experiment.py:57` 配对完全由 `--pair` 人工给定，harness 无任何用药适格性门——这不是 bug（page-review 侧 field_name 也不可靠：page3 中 Gemini 把真实用药行标为 `既往/伴随病史` 字段），说明**门必须放在提示/合同内、按观察自身文本判，不能放 harness 侧按字段名筛**。

**证据 C — 次级失败（原文级，已核实）：**
- 剂型缺失 vs 跨页残缺两类 completeness 混淆：holdout page3 氯雷他定/孟鲁司特钠**原文未写剂型**，GLM 标 `fragment`、Gemini 标 `complete` → unresolved。对照开发集 `medication-components-v4-page3` f24 摘录"2025.4.5-2025.4.12口服孟"与 `v4-page4` f03"鲁司特钠片，10mg…"——**同一药名真实跨页断裂**，双道一致 `fragment`（这才是 fragment 的正确用法）。GLM 误标的驱动源是提示句"药名必须逐字照抄**含剂型**的名称"。
- 剂量假冲突：`5mg/次` vs `5mg`、`每次两喷` vs `两喷`——双方都是原文精确子串，分歧只在抄写范围（分母"/次"、"每次"是否入值），非语义冲突。
- UK 端区间不拆分：page4 pair-0 原文"UK-2025. 6. UK鼻喷苯环喹溴铵鼻喷雾剂…"，Gemini 整段"UK-2025. 6. UK"作**单条** `role=unclear` 输出（验证器 `_DATE_RANGE` 只认数字引导端点，故放行，`medication_component_experiment.py:47-48`）；GLM 整段漏提（此例 QC 旗标为真阳性）。
- 真实用药也存在角色分歧：开发集 v4-page4 f09（"2025.04.uk使用清肝降压胶囊…"）一(use_start)道标 use_start 一道标 unclear——"不得因提到日期就推断 use_start"过度保守时产生跨道分歧。

**证据 D — 反删除反例（真实存在于语料）：**
- `medication-components-v4-prescription/source.json` fact-2"银屑病**应用HR治疗中**"——明确正在用药但无规范药名（方案缩写）。任何"药名 null → 抹时间/状态"的规则会摧毁这条真实使用事实。
- holdout page4 pair-0 鼻喷剂区间开始端在上页、单页仅剩 UK 残段——真实用药、时间残缺，需要保留而非删除。

**证据 E — 测试与溯源：**
- `tests/v2/scripts/test_medication_component_experiment.py` 44/44 通过（`-p no:cacheprovider` 实跑）。失败是**合同设计缺口，不是实现 bug**。测试无任何非用药记录用例；`test_hyphen_ranges_cannot_be_single_start_dates` 参数全部数字引导，无 UK 端点区间用例。
- 溯源链核实：v4 source.json 的 4 个 `page_review_id` 与 `medication-holdout-31006-targeted-page3/page4/result.json` 完全一致，`manifest.json` 绑定原件 PDF（`376da20a…`）。**说明：我未目视原件图像**（所有者已目视核对，见 plan 记录）；本审阅是工件/文本级，不称目视核对。

### 3. 对最小修订方案的挑战（按影响排序）

**挑战 1（最高影响）："随后限制用药分项"未指明限制对象——按字面实现会复现缺陷。** 实测错误输出在 `times`+`ongoing`，而 `drug_name` 本来就正确为 null。若"限制分项"被实现为只约束药名/剂量等用药分项、times 规则保持"原文有几条时间就输出几条"，疾病日期会再次进入 use_start。必须写成：**用途 ∈ {明确未用药, 非用药} ⇒ 六个分项全 null 且 `times=[]` 且 `ongoing=null`**（疾病的开始时间/持续语义留在上游 page-review 事实里，分项层不得复制为用药语义）。

**挑战 2：QC 旗标不改，正确输出会被持续惩罚。** 即使加了用途门，`:257-259` 的日期提示仍会对"否定用药 + 摘录含日期 + times 空"的正确输出打 `possible_unextracted_time`（本_run已发生）。旗标必须以用途为条件：仅当用途属于 {use, prescription, purchase, unclear} 且 times 空且含日期提示才触发。这是 harness 代码改动，提示侧改不掉。

**挑战 3：用途单字段 vs 语义二维。** "血压升高，未药物干预"同时是(a)病史记录、(b)对用药的明确否定——单字段 `observation_use` 会把两维压成一维。"使用/处方/购买/明确未用药/非用药/不明"六个选项里，**"明确未用药"与"非用药"必须保留为两个值**（否定本身是入排相关的用药事实，有自己的 source_quote："未药物干预"）。混合记录（一条记录既有病史+否定又提另一种药）暂路由到 unclear，作为反例集成员而非立即扩 schema。

**挑战 4："不明"不得被迫二值化。** 用途判不清时（如仅写"治疗"无主语），分项应照常按原文提取、比较保持 unresolved，而不是强制猜 use/非use。否则会在门上制造新的错误趋同风险。

**挑战 5：剂量分母的正确修法在抄写规则，不在归一化。** 若在比较器里删"/次""每次"来消冲突，即违反"剂量分母不得一律删除"。正确做法：提示定义 **dose 值 = 原文每次用量的完整写法（含连写的"/次""每次"等分母）**，双道抄写范围一致 → agree，分母保留。

**挑战 6：completeness 定义必须文本化。** 补一句："completeness 只描述本观察原文药名**文本**是否连续完整：原文本身没写剂型不算缺失、不得取 fragment；只有摘录边界截断、跨页残字（如'口服孟'/'鲁司特钠片'）才是 fragment。"并把"必须逐字照抄含剂型的名称"改为"照抄原文写出的完整药名（含原文写有的剂型）"，消除 GLM 误标的驱动源。

**挑战 7：UK 端区间需要可执行拆分规则。** "UK-2025. 6. UK"应拆为 use_start(value="UK" 照抄、precision=unclear)+use_end("2025.6.UK"、partial)；同时 `_DATE_RANGE` 端点应接受 UK 段，使 Gemini 式整段单条输出被确定性拒绝。注意 GLM 对该区间的漏提被现有旗标正确捕获——改用途条件后，此真阳性必须保留。

**挑战 8：一轮短提示的可行性成立，但要守边界。** 以上全部改动 = 1 个 schema 字段（`observation_use{value, source_quote}`，枚举六个值）+ 约 5 句规则 + 实例形状一行。提示增量约百余字，仍是一轮、单实例、无解释输出；无需平行 harness、无需药物名单/疾病名单/项目特例（门只看观察自身原文措辞，通用）。

**挑战 9（方案未提的遗漏）：比较器需要用途行与分诊顺序。** 用途应作为比较行（按标准化文本 agree/conflict/missing）；当用途行 conflict（如一道 use、一道 non_medication）时，分项层的 missing/conflict 全是下游噪音——输出保留但复核分诊以用途行优先。另建议：新版本号必须是 **v5**（按 plan 自己的规则"任何修改另建版本并使当前资料转为校准集"），不得原地改 v4 冻结成绩。

### 4. 可执行最小合同（v5 建议稿，供 Codex 裁剪）

1. **schema**：新增 `observation_use: {value: use|prescription|purchase|explicitly_no_medication|non_medication|unclear, source_quote}`；其余分项结构不变。
2. **提示新增规则**（中文表述，接在现有防补值规则后）：先判用途再取分项；用途判据须为该观察原文自身措辞；判为明确未用药/非用药 ⇒ 其余分项全 null、times 空；禁止因药名缺失判非用药（药名不详但明确使用 ⇒ use，时间照常提取）；疾病开始时间/持续不属于用药分项；completeness/剂量分母/UK 端拆分三句按挑战 6/5/7。
3. **确定性校验器**（`medication_component_experiment.py`）：用途∈否定集 ⇒ 强制全 null+空 times（不符即拒绝，与提示镜像）；QC 日期旗标加用途条件；`_DATE_RANGE` 端点接受 UK；比较器加用途行。
4. **必须通过的反例集**（任一失败即不通过）：血压升高/鼻息肉两例（双道 use=explicitly_no_medication、全 null、无旗标）；"银屑病应用HR治疗中"（use=use、ongoing=治疗中、不得凭医学常识补药名剂量）；氯雷他定/孟鲁司特钠（双道 complete）；口服孟/鲁司特钠片跨页对（双道 fragment）；UK-2025.6.UK 鼻喷区间（拆分为 UK 起点+2025.6.UK 止点）；5mg/次与每次两喷（双道同抄含分母 → agree）；构造反例"2025.3起口服降压药（药名不详）至今"（use=use、drug_name absent、use_start=2025.3、ongoing=至今）——反误删的守门用例。

### 5. 给 Codex 的决策点与有界问题

- **Q1（影响 schema）**："HR"这类方案缩写应作为 `drug_name.value="HR"`（completeness=uncertain）照抄保留，还是 drug_name 保持 absent？我建议前者（原文药名位文本照抄、quote 绑定、uncertain 待核）；安全暂行路径 = 后者，但会丢失可绑定的药名位证据。
- **Q2（影响合同形状）**：`observation_use` 单字段（我建议，最小）还是拆"记录关于什么 + 对用药断言什么"两字段？混合记录反例是否必须进本轮反例集？我建议单字段+混合记录列入反例集观察，暂不扩 schema。
- **Q3（影响比较语义）**：双道"明确未用药"一致时是否要在比较中呈现为正向 agree 行（我建议是——它是这些记录里唯一可跨道一致的用药相关语义）？
- **假定不再确认即按此执行**：v5 新建版本号与代码哈希，v4/holdout 结果转为校准集；本轮一切输出 product_acceptance=false。

### 6. 未验证与限制

- 未目视原件图像（工具与边界所限；所有者目视核对已由 plan 记录）；页级 JSON 溯源链已完整核实。
- 未调用任何模型（越界）；第 4 节反例集的"必须通过"是提示文本分析推得的验收预测，需实现后在 v5 扩测中实测确认。
- 现有 44 测试全通过；新用途门/旗标条件/UK 端拆分的测试属实现任务，不在本只读审阅范围。测试补齐建议随 v5 实现一并加入（至少：非用药记录不触发日期旗标、UK 端区间拒绝单条整段、用途否定集强制全 null）。
