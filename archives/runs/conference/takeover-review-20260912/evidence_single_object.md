# Conference Output: takeover-review-20260912 - evidence_single_object

## Output

### 0. 审查方法与证据等级

- 基线：worktree `phase5-clinical-facts-profile`，HEAD=4caf392（与任务指定一致）。只读审查：完整阅读指派的 9 个源文件及相关模块（`clause_pack.py`、`judgment_search_job_service.py`、`fact_repositories.py`、`eligibility_review.py`、`fact_correction_service.py` 相关段），并用 `sqlite3 mode=ro + PRAGMA query_only` 在 06c 真实库（`artifacts/phase55-takeover/20260911/glm-gemini-runtime-06c-page19-retry/enrollment-review-v2.sqlite3`）上**以真实 `EligibilityReviewProjectionService.project()` 全链复现**了筛选期 81 条条款的判定分布。未改任何产品/源/测试文件，未调用模型，未重跑旧作业。
- 证据分级：【复现】= 本会话在真实库/真实代码上直接运行得到；【引述】= 交接文档/agent:// 报告的结论，本运行时无法访问原始 transcript，未独立复核；【推断】= 基于代码与数据的推理。

### 1. 核心结论（TL;DR）

1. 交接文档的两个 G2 判定语义缺陷**全部本地复现属实**，且我定位到比交接描述更上游的共同根因：**34d4f43 的词汇表桥接把“条款级全部资料要求的 fact_type 并集”无差别映射到该条款的每一个谓词（含专业判断谓词和例外分支谓词）**（`app/services/eligibility_review_projection.py:689-714`）。交接提议的两处下游修补方向正确但各有一处语义偏差（见 §4）。
2. **新发现一个 P0 级界面功能缺陷（交接未记录）**：投影 wire 的 `rule_code` 用官方父编号（`official_code`），81 条条款只余 23 个不同编码（EX-07×29、EX-06×14、EX-09×8…），API DTO 的正则 `^(IN|EX|REQ)-\d{2}$`（`app/api/v2/eligibility_review.py:33`）从结构上禁止子条款身份上线。前端按 `ruleCode` 建 Map、做选择和 React key（`EligibilityWorkbenchPage.tsx:244/290/619`、`ReportsPage.tsx:192`），**点击 29 条 EX-07 子条款中的 28 条会打开第一条的详情**，报告表出现重复 key。这直接削弱“界面验收 ✅”与第三方测试对子条款导航的覆盖可信度。
3. 交接声称“决策-文案矛盾 0”**被复现反驳**：EX-07e 判“未触发排除标准”，理由却是“**未见**满足该排除条款的记录（另有待核对事项：病历记录不完整）”，而该条款 `fact_refs` 里明明挂着一条 affirmed 过敏事实——判定与理由在医生眼前自相矛盾。
4. G1（Profile run 级坍缩）在 06c 库**精确量化复现**：筛选期档案 medication 泳道 33→2（rev1→rev4），rev4 权威=当前活动指针故**不标 stale**。同时澄清一个交接未言明的边界：**入排判定投影不受 G1 影响**（不按 run_id 过滤，601 条事实跨 4 个 partial run 折叠后全部可见）——G1 是档案/展示层缺陷，不是判定层缺陷。
5. 新发现一个 P1 级**口径分裂**：判断检索需求选择（`judgment_search_job_service.py:100`）与期望兜底（`fact_expectation_gaps.py:245-247`）只认 `required_source_types` 含 `investigator_assessment`；投影 `_requires_investigator_judgment`（`eligibility_review_projection.py:427-435`）还认条款 `determination_mode`。IN-03 的资料要求 source_types 为空 → **永远不会被判断检索覆盖**，G2-1 修复后将永久卡在“尚无完整的判断检索摘要”的死胡同。

### 2. 缺陷清单（按优先级；除注明外均为【复现】）

#### D1（P0）investigator_judgment 条款产出终局判定（=交接 G2-1，根因定位到桥接层）

- **复现**：真实投影输出 `IN-03 [investigator_judgment] -> inclusion_met gap=professional_judgment`，理由“本次提交的资料支持满足该入选条款。（另有待核对事项：研究者专业判断缺失）”。驱动事实是全库唯一一条 `fact_type=用药史和症状记录` 的 affirmed 事实：“注射用奥马珠单抗300mg，皮下注射治疗，治疗效果不佳”。
- **链路**：谓词 `IN-03-poor-control`（`requires_professional_judgment=true`，comparator=exists）被别名映射到要求 fact_type 集合 {用药史和症状记录} → `_evaluate_atomic`（`app/domain/expression.py:493-559`）对 affirmed 事实 EXISTS→TRUE → `derive_component_decision`（`app/domain/gates/assessment.py:295-328`）**没有 determination_mode 输入** → INCLUSION_MET。
- **违反的设计红线**：FINAL_DESIGN §7.3“`investigator_judgment` 条款的‘判断记录存在性→状态/缺口’映射”、§5.4、R3 §11（无判断≠阴性；专业判断条款不猜）。注意后果不只是“给了终局”：wire 呈现是**绿色“符合入选标准”徽章 + 底部小字“需要研究者结合资料确认”**（`EligibilityWorkbenchPage.tsx:86-111,393`），对医生是最强信号压过最弱信号。
- **附带**：`_evaluate_atomic:503-509` 只在“无匹配事实”时才因 `requires_professional_judgment` 给 `professional_judgment_missing`；一旦桥接让事实命中，PJ 语义即被绕过——这是 G2-1 的求值层根源。

#### D2（P0）例外接管 + 理由文案失实（=交接 G2-2，根因定位到别名构造）

- **复现**：`对宠物毛发过敏的PAR患者 [semantic] -> exclusion_not_triggered`，理由“本次提交的资料中**未见**满足该排除条款的记录。（另有待核对事项：病历记录不完整）”，`fact_refs=[fact:136614e9…]`。
- **链路**：EX-07e 只有一条资料要求（`fact_type=allergy_history`）；别名构造（`eligibility_review_projection.py:707-714`）把**例外谓词** `该受试者.目前已无宠物毛发接触` 也映射到 `allergy_history`。库中唯一该类型事实“患有对宠物毛发过敏的常年性过敏性鼻炎**但目前不接触宠物毛发**”affirmed → trigger EXISTS→TRUE **且** exception EXISTS→TRUE（同一事实）→ `assessment.py:326-327` → EXCLUSION_NOT_TRIGGERED。
- **两处独立缺陷**：(a) 例外由触发事实本身“证明”——类型级匹配无法区分断言文本的哪一部分支持哪个谓词。**反例证明危险性**：若事实为“对宠物毛发过敏，且家中养猫”，今天同样判“未触发”——临床上错误。(b) `_reason`（`eligibility_review_projection.py:543-560`）对一切 NOT_TRIGGERED 输出“未见满足该排除条款的记录”——例外路径下该句为假。本例源文本确实同时支持两命题（结论碰巧正确），但推导不成立，且理由句失实。
- **对交接“EX-07e 是唯一走例外接管路径的条款”的更正**：81 个组件中 **8 个携带真实例外表达式**（EX-06f、EX-06l、EX-07e、EX-07g、EX-07h、EX-07r、EX-07u、EX-09d；其余 73 个 exception JSON 为 null）。EX-07g/EX-07h 的例外谓词还带 `requires_professional_judgment=true`（“经过彻底治疗且无复发的皮肤原位癌…”），同样暴露于本缺陷。

#### D3（P0，新）rule_code 碰撞：子条款在工作台不可寻址

- **复现**：投影 81 条 → 23 个不同 `rule_code`（EX-07×29、EX-06×14、EX-09×8、EX-10×3、IN-02×3、EX-11/12/14/15/IN-04/IN-06 各×2）。`rule_code=clause.official_code`（`eligibility_review_projection.py:769-771`），`display_code`（EX-07e 等）不出网（DTO 正则禁止）。
- **后果**：前端 `byCode` Map 塌缩、`onSelect(ruleCode)→find(ruleCode===param)`（`EligibilityWorkbenchPage.tsx:616-619`）恒返回第一条同码条款 → **28/29 条 EX-07 子条款的详情/原件面板不可达**；React 重复 key（`:290`；`ReportsPage.tsx:192`）在打印报告的逐条判定表中同样存在。
- **波及**：PRD Slice 6 验收项“每条官方 IN/EX 一行——判定+原因+原件定位链接”对子条款实际未达成；三档截图与第三方测试若未逐条点开 EX-07 子项则测不到。

#### D4（P1）类型桶冲突无对象判别（=交接 G3，机制修正）

- **复现（EX-01）**：桶 `过敏史记录` 内两条事实——“否认对本研究药物成分及辅料过敏…”（negated，对象=药物过敏）与“承认对大豆、螃蟹…食物过敏史”（affirmed，对象=食物过敏）。`(value,unit,polarity)` 去重后 ≥2 → `source_conflict`（`expression.py:519-531`）→ 无法判定。临床上这是**两个不同问题的答案，不是矛盾**；仅凭药物过敏否认，EX-01 本应“未触发”。
- **复现（感染桶）**：`infection_history` 5 条否认（结核/疱疹/蠕虫/鼻窦炎/抗感染药，value_json true/false 混杂）→ 5 条 EX-07 子条款全部 conflict。
- **对交接的修正**：根因不是“同页多事实”而是**同 fact_type 多 assertion_object**，与页无关；`clinical_facts_v2.assertion_object` 字段已存在且填充（评估器未使用）。“18 条全是误触发”过强——同一 assertion_object 的真实分歧也会走同一呈现（如 ANC 桶 11 条事实中可能含真实检验冲突），当前机制**无法区分真假冲突**，这才是缺陷本体；设计 §8/R3 §8“不同展示字段名不自动构成临床冲突”明确禁止此行为。
- **镜像问题**：单一值元组的多事实桶取 `matching[0]`（`expression.py:532`）任意一条做终局判定的 fact_ref——14 条“未触发”中每条引用的事实可能属于**另一个临床对象**（如疱疹条款引用“否认结核”行），医生下钻看到的是错误证据。

#### D5（P1，新）“需要研究者判断”三处口径不一 → IN-03 永久死锁

- 【复现】三个判定口径：
  1. 判断检索需求选择：`judgment_search_job_service.py:100` 只认模板 `required_source_types ⊇ investigator_assessment`（库中 8 个模板，7 个 screening 已检索——与 summaries 表 7 要求一致）；
  2. 期望兜底：`fact_expectation_gaps.py:245-247` 同上；
  3. 投影缺口：`eligibility_review_projection.py:427-435` 另认 `determination_mode=investigator_judgment`。
- IN-03 模板存在（`required_source_types=[]`）→ 口径 1/2 均不选中 → 检索摘要永缺 → 口径 3 永远补 `professional_judgment` 缺口。G2-1 修复后 IN-03 将**永久**“无法判定：尚无完整的判断检索摘要”，无任何系统路径可解除。交接“7 要求 ↔ PJ 期望 7:1 闭环”只在口径 1 下为真，掩盖了此分裂。

#### D6（P1）Profile run 级坍缩（=交接 G1，确认+量化+边界澄清）

- 【复现】代码：`fact_normalization_executor.py:1299-1305` 传 `run_id=publication.run_id`；`patient_profile_service.py:342/356/370/390` 四处 run 过滤；修正路径 `fact_correction_service`（≈:1163）不传 run_id——同服务双口径确认。
- 【复现】06c 数据：筛选期 4 个 partial run（223+190+151+37=601 事实）共享同一权威元组；档案 rev1 medication=33/总 387 → rev4（37 事实 run 收尾后）medication=**2**/总 173；rev4 权威=当前活动指针 → `_derive_stale` 不标 stale → 塌缩档案以“当前有效”身份呈现。QC_31001 的 33→2 数字即来自本库。
- **边界澄清（交接未言明）**：入排判定投影读 `list_for_authority`（全权威、无 run 过滤），601 条全部参与求值——**G1 不污染判定，只污染档案/档案派生视图**。修复风险低：链头折叠+引用闭包在全量集合下只会更宽松（各 run 候选自包含，4 个 rev 均通过闭包校验可证）。

#### D7（P2）面向用户呈现违反产品边界

- 【复现】裸 `fact.factId`（形如 `fact:53f78709…`）直接渲染给医生（`EligibilityWorkbenchPage.tsx:368、457、468`），违反 goal“不得出现内部 ID/英文枚举”。
- 【复现】页脚“档案版本”实为 `ruleSetRevision`（workbench `:716`、ReportsPage `:249`）——规则修订被误标为档案版本；证据快照/处理修订身份完全缺席，与设计 §8.8 报告身份要求不符。
- 【复现】报告页标题“入排审核结果/完整的入排审核结果”，而数据源是**实时只读投影**（API 自述“不启动正式 ReviewRun”，`eligibility_review.py:92`）；“生成时间”= 浏览器渲染时刻（`ReportsPage.tsx:229`）。医生今天打印、明天新 run 发布事实后重开页面结论可变，打印件无身份可对账——“readonly 预览 vs 正式报告”的措辞与身份问题。
- 【复现】冲突卡只说“存在相互冲突的事实”（`_reason:538`），不给冲突内容原文/页码并排（G3 UI 面已知的部分）。

#### D8（P3）零散

- EX-06 子条款 determination_mode 不一致（交接 G6）：【引述，未复核】。
- run.sh 启动 legacy v1（交接 G6）：【引述，未复核】。
- `not_due` 条款带 fact_refs 的口径（交接 G6）：未在本轮展开。

### 3. 交接文档（HANDOFF_20260912_SUCCESSOR）不准确处汇总

| # | 交接原文 | 复核结果 |
|---|---|---|
| 1 | “决策-文案矛盾 0”（34d4f43 验证口径） | 被反驳：EX-07e“未触发+未见记录+fact_refs 非空”是活的决策-文案矛盾；34d4f43 只消除了“终局判定配无法判定理由”一类 |
| 2 | “EX-07e 唯一走例外接管路径” | 8 个组件带真实例外表达式；EX-07e 是本数据上已证实走通该路径的一条，非结构上唯一 |
| 3 | “18 条 conflict 是同页多事实误触发” | 机制为同 fact_type 多 assertion_object（与页无关）；“全是误触发”过强，机制不能区分真假冲突 |
| 4 | G2-2 修法定位“`_evaluate_logical` 例外接管” | 例外决策实在 `derive_component_decision:324-327`；`_evaluate_logical` 只做逻辑运算；根因在投影别名构造 `:707-714` |
| 5 | G2-1 修法备注“clause.determination_mode 已在投影层” | mode 在 `ClausePackClause` 上，`RuleComponent`/`derive_component_decision` 均无此参；修复需改签名并保留 CONFLICT 透传（EX-01 现为 conflict，若“永远 PJ”会退化冲突可见性） |
| 6 | “判断检索 7 要求 ↔ PJ 期望 7:1 闭环” | 仅在 source_types 口径下为真；漏掉 mode 口径的 PJ 条款（IN-03），闭环陈述掩盖 D5 |
| 7 | 筛选分布“21PJ+14 未触发+2 满足+26 未到期+18 冲突” | 【复现】逐项一致，可信 |
| 8 | “601 事实/46 事件/22 暴露” | 601 事实【复现】（4 run 共享权威）；事件/暴露数未重数【引述】 |
| 9 | 基线“81 全 PJ→54PJ+18+9” | 【引述】未重跑基线 episode |

### 4. 对交接建议修法的反例与替代方案（Codex 决策点）

1. **G2-2“trigger 与 exception 命中同一事实（fact_id 交集非空）→ 降级 conflict”**：反对以 conflict 为降级目标。EX-07e 源文本同时支持两命题（“过敏但目前不接触宠物毛发”），**不存在来源分歧**，标“资料有矛盾”会让医生去核对根本不存在的矛盾（且本任务提示自身警告：不得把同事实被相容谓词复用自动当冲突）。替代：判例外证据**独立性**——`exception.used_fact_ids ⊆ trigger.used_fact_ids` 时例外视为 UNKNOWN（非独立证据，理由如“无独立证据支持该例外情形”），走 `_decision_for_unknown` → 无法判定 + 明确缺口（description_insufficient/record_incomplete），交集判定用子集而非非空（例外合法引用判断记录事实时可能共享页/源但不共享事实）。同时 `_reason` 增加例外路径文案：“资料显示存在该排除情形，但例外条件尚无独立证据确认”。
2. **G2-2 根治选项（更上游）**：别名构造对**例外分支谓词默认不做 fact_type 桥接**（回到严格匹配），直至资料要求能显式绑定例外分支。后果：EX-07e 变“无法判定”——诚实但改变用户可见结论（现状碰巧结论正确）。建议与选项 1 叠加实施（桥接收口为根，独立性检查为防御）。
3. **G2-1“investigator_judgment 组件永远返回 PJ”**：应表述为“永不产出**终局**判定”。CONFLICT/NOT_DUE/NOT_APPLICABLE 必须透传（EX-01/IN-02 现为 conflict，是更具体的状态；一律 PJ 会丢失冲突可见性）。实施点：`derive_component_decision` 增加可选 `determination_mode` 参数（缺省 None 保持现行为，Phase-3 gate 路径不破坏），投影传入 `clause.determination_mode`。
4. **G1 修法（去 run_id）**：认可为最小正确修法；补充验收断言应含“partial run 收尾后档案 medication 泳道保持 33”（现有 33→2 即现成反例测试数据）。

### 5. 最小修订顺序与验收测试（建议）

| 步 | 内容 | 验收测试（全部可在合成 fixture 上确定性构造） |
|---|---|---|
| 1 | D1：`derive_component_decision` 加 mode 参数，仅抑制终局判定；投影传 `clause.determination_mode` | IN-03 型 fixture（PJ 谓词+命中事实）→ professional_judgment；EX-01 型（PJ+桶冲突）→ 仍 conflict；既有 gate 测试不回归 |
| 2 | D3：wire 增发 `clause_code`（=display_code），前端 key/选择/深链/报告行键全部改用 clause_code | 两条同 official_code 子条款各自可选中、详情与 fact_refs 各自正确；报告表无重复 key；API 快照测试更新 |
| 3 | D2：例外谓词别名收口 + 例外独立性（子集）检查 + `_reason` 例外文案 | EX-07e fixture → 无法判定（非 conflict），理由含“例外条件尚无独立证据”；独立例外事实存在时 → NOT_TRIGGERED 且理由为例外文案；反例（养猫变体）→ 不再错误 NOT_TRIGGERED |
| 4 | D5：`select_judgment_search_requirements` 与 `fact_expectation_gaps` 兜底统一加入 mode 口径（从组件谓词 `requires_professional_judgment` 派生） | IN-03 型 fixture 的 requirement 出现在检索计划列表；期望兜底给 PJ 类缺口而非 record_incomplete |
| 5 | D4：`_evaluate_atomic` 对象感知——同 assertion_object 多值元组→conflict；多对象桶→UNKNOWN+非冲突缺口（列举对象，供“待核对关联”）；`matching[0]` 选择按对象稳定化 | EX-01 fixture（药物否认+食物承认）→ 不再 conflict；感染桶 5 否认 → 不再 conflict；同对象真分歧 → 仍 conflict |
| 6 | D6/G1：`fact_normalization_executor.py:1299` 去 run_id | partial run 收尾后档案 medication 保持 33；与修正路径口径一致的单测 |
| 7 | D7：fact_refs 增加中文摘要（assertion_object/断言摘录）；页脚改“规则版本”并补证据快照/处理修订中文标识；报告页措辞改“实时审核工作底稿（非正式审核记录）”、生成时间改用权威数据时间 | 前端 vitest：无内部 ID 断言、标签正确、报告含身份行 |

顺序理由：1-3 是“判定不能给医生看”的阻断项；2 独立且纯 wire/前端，可并行；4 是 1 的必要配套（否则 1 完成后出现死锁）；5-6 中优；7 收尾。每步后重跑 06c 只读分布对比（本报告 §2 分布数字为现成基线：26 not_due / 21 PJ / 18 conflict / 14 not_triggered / 2 met）。

### 6. 给 Codex 的决策点与问题

1. **D2 降级语义**：采纳“非独立例外→UNKNOWN（非 conflict）”还是交接原案“交集→conflict”？我推荐前者（§4.1 理由）；若 Codex 坚持 conflict，需接受 EX-07e 出现一条医学上不存在的“矛盾”待办。
2. **例外谓词别名是否整体收口**（§4.2）：影响用户可见结论（EX-07e 从“未触发”变“无法判定”），属产品行为变化，建议 Codex 向用户说明后定案。
3. **D3 字段形状**：新增 `clause_code` 字段（推荐，向后兼容）还是放开 `rule_code` 正则改发 display_code（破坏父/子编码语义）？
4. **报告措辞**：在正式 ReviewRun 落地前，ReportsPage 是否改为“工作底稿”措辞并补身份行（我建议是；涉及用户可见文案，Codex/用户裁决）。
5. 提醒：用户已切换产品双模型（GLM-5.3-Flash high + MTPLX Qwen3.8…）。本报告全部缺陷在**确定性层**（求值/投影/档案/前端），不受换模影响；但修复后的真实库重验分布中，判断检索候选层（模型依赖）的数字会随新模型漂移，对比基线时需分开归因。

### 7. 未验证项与限制

- `agent://ClinicalReview`、`agent://JourneyAudit`、`history://CodeReview`、`agent://ThirdPartyTest` 在本运行时不可访问：其结论仅作【引述】；G2 两缺陷已由本地证据独立成立，不依赖这些报告。
- 未重跑后端/前端测试套（4352/564 为【引述】）；未重跑基线 episode 投影；EX-06 mode 不一致与 run.sh legacy 未复核；46 事件/22 暴露未重数；第二条 inclusion_met 条款未识别（次要）。
- 本会话对 06c 的全部数据库访问均为 `mode=ro + PRAGMA query_only`；投影服务 `project()` 无写路径，未触碰 06b/06c 原库。
- 所有修复建议均为方案与验收测试设计，未实施任何代码变更（遵守只读边界）；不声明最终临床/产品验收——Codex 保留最终裁决权。
