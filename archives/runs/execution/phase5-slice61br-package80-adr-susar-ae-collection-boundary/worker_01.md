I'm the fallback `codebuddy-cli` / `deepseek-v4-flash` worker continuing this bounded read-only verification task. Starting with the initial read set.

Initial read set consumed. Context notes "TODO: Codex must add authoritative source files" — so I must locate the real sources (body document, package plans) inside the workspace myself. Exploring the workspace structure first.

Now I need to locate the real sources: the "body" document with p1015-p1026 page markers, and the 131-package plan (packages 79-99). Prior package-boundary contexts (61bq = package 79) should reveal source locations.

The package-79 context confirms "body.pXXXX" refers to a protocol body document. Let me find it and the 131-package plan.

Package 75-79 boundaries were accepted; their worker reports will point me to the actual sources. Let me read package-79's report and checkpoint.

The package-79 report provides the exact evidence map. Now I must locate the actual files and verify package-80 ownership and p1015–p1026 content myself (not rely on prior report claims).

Found the frozen plan. Now verifying package 80 ownership and its context units from the frozen plan.

Ownership map confirmed from the frozen plan: P80 = p1015–p1026 (12 units), adjacent P79 (p1007–p1014) and P81 (p1027–p1032). Note P82, P89, P91 own no body pages (likely tables/footnotes). Now dumping P80's owned units with excerpts and heading paths.

P80 ownership fully confirmed: ADR definition (p1015–1016), SUSAR (p1017–1019), AE collection window (p1020–1024), AE recording rules (p1025–1026). Now locating the protocol_blocks blob for verbatim text verification.

Verbatim text confirmed for p1013–p1027. Now checking coverage manifest heading paths for p1015–p1167 and the non-page packages (82, 89, 91).

Heading hierarchy is now clear. Checking the table-only packages (82, 89, 91) and extracting verbatim text for P81–P84, P85–86, P90, P92–99 ranges.

P82 owns Table 7 (secondary events AE recording), P89 owns Table 8 (severity grades), P91 owns Table 9 (causality evaluation). Now extracting verbatim text for P81–84, P85–86, P90, P92–99 ranges.

P81–P84 verified. Now P85–86 (liver injury), P90 (causality), P92–99 (reporting flow).

P85–86 verified with Hy's law criteria and 24h-report obligations. Now P90 (causality) and P92–99 (reporting flow).

P90 verified (note p1095 references "表7" while caption at p1097 is "表9" — a source-internal cross-reference discrepancy worth flagging). Now P92–99.

P92–94 verified. Now P95–99 (p1124–1167).

P95–99 verified. P96 owns p1136–1137 which didn't appear in the block dump — checking what those units are.

P96 = last two items of the "一般不作为快速报告内容" list (cross-package list split with P95, mirroring the P78/79 pattern). Now checking TOC numbering for exact section numbers and the flow-directory matrices for ADR/SUSAR/AE hits.

TOC numbering locked: ADR=7.3.2.4, SUSAR=7.3.2.5, 收集=7.3.3.1, 记录=7.3.3.2. Getting the remaining TOC entries (7.3.4/7.3.6/7.3.7) to complete the section map.

Complete TOC map locked. Now checking flow-directory matrices and required procedures for ADR/SUSAR/AE-collection term hits.

Key finding: matrix/cross rows contain "不良事件" and "24小时" hits — potential preemption sites. Examining those rows in full.

The AE/24h hits must be in deeper fields of those rows. Locating exact match positions.

Matrix hits are all pre-dose/eligibility or treatment-boundary context — no ADR/SUSAR/AE-collection preemption. Checking required_procedures and the flow table t5 (AE row + safety follow-up columns).

required_procedures has no AE semantics. Verifying t5.r38's full row (AE across visits) and the safety-follow-up vs last-visit wording in visits chapter.

t5.r38 confirmed: "不良事件^26" X only at c3 (D1). Now verifying against the raw docx: p1015–1026 verbatim text, numId=12 heading numbering, the gridSpan on the AE X cell, and footnote 26.

No footnotes.xml — checking document.xml for p1015–1026 region, numbering, the AE row gridSpan, and whether "^26" is literal text or a footnote reference.

Raw docx confirms the structure. Now verifying: the AE-row gridSpan, numbering.xml definitions for numId 12/53/58, footnote-26 text, and p1018–1019 full verbatim.

Raw docx confirms both flow tables: AE row "不良事件^26" X with gridSpan=7 (phase II) / 17 (phase III). Finding the footnote-26 note text after the table.

Notes use numId=29 list. Extracting the 26th note.

Footnote 26 found — "不良事件于D1启动给药后开始记录，直至末次安全性随访或者退出研究为止" — cross-consistent with p1022. Final verification: no duplicate ownership across packages and full page coverage p995–1167.

All checks pass. One final boundary anchor — the AE/TEAE definitions (p986/p994) that P80's collection rules build on.

All evidence gathered. One quick check of phase scopes for P80 units, then compiling the report.

All verification complete. No blockers. Compiling the final report.

---

# Execution Output: phase5-slice61br-package80-adr-susar-ae-collection-boundary - worker_01

## Boundary And Context Check

- **Role/fallback:** This pass executes as the declared same-platform fallback `codebuddy-cli` / `deepseek-v4-flash` (primary `glm-5.3-flash` unavailable before a resumable session existed). No capability limitation affected this read-only work; all verification used local tools inside the worktree.
- **Boundary compliance:** Read-only task. **No file was created or modified.** The runner-managed report is returned inline; no sibling process files. No production paths, no package installs, no model calls, no subject review, no conference, no peer-worker review.
- **Initial read set (both read):** `context/phase5-slice61br-package80-adr-susar-ae-collection-boundary_execution_context.md`, `plans/codex_execution_phase5-slice61br-package80-adr-susar-ae-collection-boundary.md`.
- **Additional reads (all inside workspace, justified by the task — sources were not enumerated in the context "Source Of Truth" TODO, so I located and verified them from the frozen plan):** `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/frozen_phase_plan.json` (131包冻结计划, plan_id `papl-40b1237a22e538a278b4fd5e`), `coverage_manifest.json` (1848 units, claims_full_coverage=false), `structure/blobs/protocol_blocks/3946ea2c….json` (3581 blocks, 逐字文本+numbering), raw docx `source-input/blobs/protocol_sources/362443131f0d….docx` (document.xml+numbering.xml解析; sha256 与 manifest 一致), `.trellis/tasks/08-22-…/research/` 三矩阵 (`d001-ii-official-flow-controls.json` 58行, `d001-ii-control-matrix.json` 82行, `d001-ii-cross-section-controls.json` 25行), `artifacts/phase5-slice61bl-procedure-footnote-scope-20260829/required_procedures.json` (50项), 第79包 worker_01 报告（沿用证据模式，逐项独立复核，未采信其结论本身）.

## Work Performed

### 1. 第80包冻结所有权（131包冻结计划，独立复核）
- **第80包** = `pap-bb9bf95c9cd13f15e3b737f3`，**12 单元 = body.p1015–p1026**（连续、不重复、无重叠）；`selected_phase=phase_ii`、`opposite=phase_iii`；全部单元 `phase_scopes=['unknown']`（安全章节通用文本，Ⅱ/Ⅲ期共用，闭包应视为双期适用）。
- 全 131 包扫描：**无重复拥有**；p985–p1167 页级覆盖**无缺口**（第77–99包共同构成 7.3.2.3 SAE→7.3.7 妊娠 整段安全章节）。
- 邻包所有权：第79包 = p1007–p1014（8单元）；第81包 = p1027–p1032；第82包 = t12（表7，无正文页）；第83包 = p1033–p1042；第84包 = p1043–p1054；第85/86包 = p1055–p1073；第90包 = p1087–p1097（+第91包 t14 表9）；第92–99包 = p1098–p1167（其中第89包 t13 表8、第91包 t14 表9 为纯表包）。

### 2. body.p1015–p1026 逐字文本与 docx 结构核对（protocol_blocks == 原始 docx 双重命中）

| 页 | 逐字文本（节选，双源一致） | 结构证据（numId） | 语义职责 |
|---|---|---|---|
| p1015 | 药物不良反应（ADR） | numId=12 lvl3 标题（7.3.2.4，TOC p221） | 7.3.2.4 节标题 |
| p1016 | 药物不良反应（Adverse Drug Reaction，ADR）：指临床试验中发生的任何与研究药物可能有关的对人体有害或者非期望的反应。研究药物与AE之间的因果关系**至少有一个合理的可能性，即不能排除相关性**。 | 无编号正文 | **ADR 定义**：可能相关阈值 = “不能排除相关性” |
| p1017 | 可疑且非预期严重不良反应（SUSAR） | numId=12 lvl3 标题（7.3.2.5，TOC p222） | 7.3.2.5 节标题 |
| p1018 | 可疑且非预期严重不良反应（Suspected Unexpected Serious Adverse Reaction，SUSAR）指临床表现的性质和严重程度**超出了**试验药物《研究者手册》、已上市药品的说明书或者产品特性摘要等已有资料信息的**可疑并且非预期的严重不良反应**。 | 无编号正文 | **SUSAR 定义**：严重+可疑+非预期 **三维 AND**；参照物=IB/说明书/产品特性摘要 |
| p1019 | 非预期不良反应指不良反应的性质、严重程度、后果或频率，**不同于**试验药物当前相关资料（如《研究者手册》等文件）所描述的预期风险。**《研究者手册》作为主要文件**提供用以判断某不良反应是否预期或非预期的安全性参考信息。 | 无编号正文 | **非预期性定义 + IB 权威参照**（主要文件） |
| p1020 | 不良事件的收集和记录 | numId=12 lvl2 标题（7.3.3，TOC p223） | 7.3.3 节标题 |
| p1021 | 不良事件的收集 | numId=12 lvl3 标题（7.3.3.1，TOC p224） | 7.3.3.1 节标题 |
| p1022 | 本试验中，不良事件收集期应从参与者**首次服用试验用药品后至最后一次安全性随访或者退出研究为止（以先发生时间为准）**。 | 无编号正文（自控正文） | **AE 收集期**：锚点=首次服药后 → 末次安全随访/退出 |
| p1023 | 在签署知情同意书后到首次服用试验用药品之前，发生的临床不良医学事件作为**病史/伴随疾病**记录在原始病历中，**不作为AE记录**。 | 无编号正文 | **ICF 后首次服药前 = 病史，非 AE**（与 p1050 既存疾病、统计分析章节“治疗前清单”呼应） |
| p1024 | 从首次服用试验用药品至**末次访视**期间发生的所有AE均需记录在eCRF中。 | 无编号正文 | **eCRF 记录范围**（“末次访视”措辞 ≠ p1022“末次安全性随访”，**不得合并**） |
| p1025 | 不良事件的记录与规定 | numId=12 lvl3 标题（7.3.3.2，TOC p225） | 7.3.3.2 节标题（仅标题属第80包） |
| p1026 | 研究者在记录不良事件时应使用正确的医学术语/概念，避免使用口语和缩略语，在eCRF不良事件页的**单一事件项中应只记录一个不良事件术语**。 | 无编号正文 | **单一事件术语规则**（与 p1028–29、表7、p1035–36 构成“单一事件”语义族，分属 P80/81/82/83） |

**列表层级结论（docx numbering.xml 交叉验证）：** 第80包自身**不含任何 bullet/编号子列表**——6 个标题用 numId=12 多级十进制标题列表（lvl2–4，`%1.%2.%3.%4.`），6 个正文段无编号。紧邻的 p1013/p1014 为 numId=53 十进制列表第 5、6 项（SAE 严重性标准⑤⑥，属第79包）。第80包前后均为**干净切分**（P79 末条 p1014 标准⑥ → P80 首条 p1015 新标题；P80 末条 p1026 无编号正文 → P81 首条 p1027 新标题 numId=12 lvl4）。

### 3. 第79包 SAE 尾段（边界参照）
- p1013“先天性异常或者出生缺陷：指参与者的**后代**出现畸形…”= 标准⑤（对象=后代，非受试者本人）；p1014“其他有重要意义的医学事件：必须运用**医学和科学的判断**…预防如上情形之一的发生”= 标准⑥。两者为 SAE 严重性标准列表（numId=53，①–⑥跨第78/79包）的**同级项**，语义上不是 SUSAR 的定义组件——第80包 SUSAR 定义引用“严重”时不得改写或吸收标准①–⑥的具体内容。

### 4. 第81–84包 AE 记录规则（不得提前吞并）
- **P81** p1027–1032：诊断与症状、体征和检查值（诊断术语优先、无法诊断用症状/体征/实验室值、后期诊断明确后替换并**以首次症状出现日期为起始日**）；继发于其它事件的不良事件事件（引语 + 表7标题 p1032）。
- **P82** t12 表7（4行）：继发事件记录规则——轻度/中度/非严重/无需干预 → 仅记事件A；重度或严重继发 → A、B 分别单独报告；时间分离的重要医学意义次级事件 → 全部单独报告；无法确定 → 全部单独记录。p1033 注（事件A/事件B 记法）。
- **P83** p1034–1042：持续性（仅记一次）/复发性（每次复发单独记录）不良事件；实验室检查值异常（研究者医学和科学判断 + **任一标准** numId=58 三选一：伴临床症状/体征；导致研究治疗变化；导致医学干预或合并用药改变）。
- **P84** p1043–1054：生命体征异常（同模式，numId=58 三条）；既存（合并）疾病（p1050 筛选访视时或首次给药前已存在 → 记 eCRF 病史和基线状况；p1051–1053 只有恶化或改变且非预期进展才记为 AE，numId=58 两条；p1054 用“偏头痛频次增加”式描述语）。
- **边界**：p1023（病史/伴随疾病，第80包）与 p1050（既存疾病定义，第84包）互为依据但**职责不同**——P80 管收集期与“不作为AE”，P84 管恶化后如何记录为 AE，不得互相改写。

### 5. 第85–86包 肝损伤（不得提前吞并）
- **P85** p1055–1066：Hy's law 指征（numId=58：ALT/AST>3×ULN+TBIL>2×ULN 或+黄疸；比值≥5）；**p1059 必须按 SAE 记录并 24h 内报告**；基线正常（p1061–62）与基线异常（p1064–66，以较小者为准）两组标准。
- **P86** p1067–1073：DILI 简介（p1068 潜在 DILI 始终视为重要医学事件）；疑似 Hy's 48h 返回评估（p1070）、扩展实验室（p1071）、**重复检查证实后报告为 SAE + 24h 报告**（p1072）、排除其他病因后确诊（p1073）。
- **边界**：肝损伤特有的“按SAE记录+24h报告”义务**属于第85/86包**；第92–99包通用报告流程（SAE报告表、时限、随访）不得提前并入第85/86包，反之亦然。

### 6. 第90包 因果关系（不得提前吞并）
- p1087–1097：五分法（肯定有关/很可能有关/可能有关/可能无关/无关，p1088）；五个评价要点（numId=59：时间相关性、是否已知、去激发、再激发、其他合理解释，p1090–94）；p1095 统计分析时“肯定/很可能/可能有关”视为相关；**p1096 SAE 因果关系由研究者和申办者双方共同判断，意见不一致时任一方判相关即属报告范围**；p1097 表9标题（表体 t14 属第91包）。
- **发现的源内不一致（证据，非错误）**：p1095 正文写“可参照**表7**进行”，而该表标题为“表 9”（p1097）。疑似原文笔误，闭包须**保留逐字**，不得静默“修正”。
- **边界**：P80 的 ADR 阈值（不能排除相关性）与 P90 五要点/共同判断是**上下游引用**关系，共同判断义务不得提前并入 P80。

### 7. 第92–99包 报告流程（不得提前吞并）
- **P92** p1098–1101：预期性评估——“评估CMS-D001片不良事件预期性**见CMS-D001片的《研究者手册》**”（p1099，与 p1019 IB 权威参照闭合）；7.3.5/7.3.5.1 标题。
- **P93** p1102–1112：24h 内应报告事件类型（死亡/SAE/妊娠，numId=58）+ 新重要信息 5 类（numId=58：新体征症状或诊断改变、新诊断检查结果、因果关系变化、事件结果变化、临床过程其他描述）。
- **P94** p1113–1123：安全信息资料（原则、**《SAE报告表》24h 书面报告** p1117、随访报告、死亡报告处理、报告途径=附录7）。
- **P95** p1124–1135 + **P96** p1136–1137：申办者报告要求——**SUSAR 快速报告给所有研究者/机构/伦理，并向药监和卫健部门报告**（p1126）；三维 AND 复核点：p1127“肯定相关或**可疑的非预期且严重**的不良反应”快速报告；7天/15天时限（p1128–29）；报告起止窗口（p1130）；结束后获知 SAE 仍须报告（p1131）；**双方分歧时任一方不能排除相关即快速报告**（p1132）；**一般不作为快速报告内容**（numId=58 四选一列表，P95 持前2条 p1134–35、**P96 持后2条 p1136–37 = 同一列表跨包切分**，与 P78/79 模式相同）：非严重AE、SAE 与药物无关、**严重但属预期的不良反应**、SAE 为主要疗效终点。
- **P97** p1138–1149：不良事件的随访（处理；随访直至消退/返回基线或更好/稳定/失访或撤回同意 4 种情况；结果类型 E2B(R3) 6 态）。
- **P98** p1150–1157：结果定义（numId=61：痊愈/好转/未好转/伴后遗症/致死/未知）+ 结束时间规则。
- **P99** p1158–1167：妊娠——24h《妊娠事件报告表》（p1160）；**单纯的妊娠事件本身不属于不良事件，不记录在 eCRF 不良事件页**（p1162，与 p1023 病史逻辑同族）；妊娠期 SAE 以《SAE报告表》24h 报告（p1163）；随访至妊娠结局、新生儿 SAE 24h（p1166）。

### 8. SUSAR 三维 AND 的跨包印证（闭包关键证据链）
- 定义（P80 p1018）：严重 AND 可疑 AND 非预期。
- 报告范围（P95 p1127）：与试验用药品肯定相关**或可疑**的**非预期且严重**不良反应 = 同一 AND 语义。
- 反证（P95/P96 p1134–37）：缺任一维度即不快速报告（非严重 / 无关 / 严重但预期 / SAE 为主疗效终点）——与“三维缺一不可”互为补集。
- 非预期参照（P80 p1019 + P92 p1099）：IB 为权威参照（“主要文件”/“见《研究者手册》”）。
- 因果阈值（P80 p1016 “至少合理可能性/不能排除相关性” ↔ P90 p1095 “可能有关”及以上视为相关）。

### 9. 收集期锚点：流程表 footnotes 与 D1 起算
- t5（Ⅱ期）r38“不良事件^26”：仅 D1 列 X，gridSpan=7（D1→提前退出）；t6（Ⅲ期）同模式 gridSpan=17。
- **脚注26 原文（raw docx，numId=29 列表第26条，双流程表共用）**：“不良事件于D1启动给药后开始记录，直至末次安全性随访或者退出研究为止（以先发生时间为准）。” —— 与 p1022 措辞一致，与 p1024“末次访视”措辞不同，**两种表述须分别保留**。
- 安全随访访视锚点：Ⅱ期 W16（p903 随访期）、Ⅲ期 W56（p972 安全性随访）——即“末次安全性随访”；“末次访视”为该阶段最后一个计划访视。两者差异不得合并为一个概念。
- AE 定义锚点（第77包，边界参照）：p986“接受试验用药品**之后**出现的所有不良医学事件…不一定与试验用药品有因果关系”；TEAE p993–94“给药后出现…治疗前并未出现或相对于治疗前发生恶化”。

### 10. 现有流程目录与正式矩阵（均无 ADR/SUSAR/AE 收集语义）
| 工件 | 规模 | ADR/SUSAR/非预期/因果/肝损伤 | 命中明细 |
|---|---|---|---|
| official-flow-controls | 58行 | **0** | “不良事件”仅 row56 源引用“D1…同时需要记录合并用药及不良事件”（D1 给药前基线复核注记，非 AE 收集语义）；row34/47 妊娠=入排资格事实 |
| control-matrix | 82行 | **0** | 同上 row56/80/81（D1 基线复核源引用）；row59“用于治疗不良事件的药物/治疗”=允许合并用药边界；row59“24小时”=**润肤剂访视前 24h 停用**（与安全报告无关） |
| cross-section-controls | 25行 | **0** | 同 matrix 对应行 |
| required_procedures | 50项 | **0** | 仅“妊娠试验/FSH”“病毒学检查”等程序项，无 AE 项 |

**结论：现有正式矩阵/流程目录未提前吞并第80包任何语义；唯一同词风险点是 row56/80/81 的“记录合并用药及不良事件”（D1 给药前基线复核）与 p1022–1024 的给药后 AE 收集——时间相邻但语义独立，门禁须防止互相改写。**

### 11. 最小闭包与不得提前吞并边界（供 worker_02 装配）
- **最小闭包主体**：body.p1015–p1026 共 12 单元（unit_kind=paragraph，blob 与冻结计划一致；无列表项）。
- **闭包必配交叉引用锚点（context 而非 owned）**：p986（AE 定义）、p997–p1014（SAE 定义与标准①–⑥，第78/79包）、流程表 t5/t6 不良事件行 + 脚注26、p903/p972（末次安全随访）、p1050（既存疾病）、p1099（IB 预期性参照）、p1100–1137（报告章节，第92–96包）、p1055–1073（肝损伤，第85–86包）。**注意：冻结计划 P80 context_units 未含 p1013–1014（SAE 标准⑤⑥），worker_02 应评估是否补充，因为 p1018“严重”引用该列表。**
- **不得提前吞并**：① 24h/7天/15天报告义务与《SAE报告表》流程 → 第92–99包；② 研究者+申办者共同判断 → 第90包；③ 肝损伤特有按SAE记录+24h报告 → 第85–86包；④ AE 记录细则（诊断/继发/持续复发/实验室/生命体征/既存疾病）→ 第81–84包；⑤ 严重程度分级 → 第88–89包；⑥ 统计分析章节“治疗前不良医学事件以清单列出” → 统计章节（p2588 区域），不得并入 P80 病史语义。
- **门禁要点（不得改写的语义）**：ADR 至少合理可能性阈值；SUSAR 三维 AND（不弱化为任一维度）；非预期必须锚定 IB/说明书/产品特性摘要（IB 为主要文件）；ICF 后首次服药前 = 病史/伴随疾病 ≠ AE；收集期=首次服药后→末次安全随访/退出（先发生）与 eCRF 记录范围=首次服药→末次访视两种表述并存；末次安全随访 ≠ 末次访视；单一事件项只记一个术语（不拆不并）；P80 文本不得改写为筛选/基线入排门槛。
- **已知源内待保留差异（非缺陷）**：p1095“参照表7” vs p1097“表 9”标题——保留逐字，不静默修正。

## Artifacts And Evidence

未创建任何工件（只读任务）。关键证据定位：
- `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/frozen_phase_plan.json`：P80=`pap-bb9bf95c9cd13f15e3b737f3`（p1015–p1026，12单元）；P79/81/82/83/84/85/86/90/92–99 邻包所有权；全131包无重复拥有、p985–1167 无缺口。
- `…/coverage_manifest.json`（sha256=362443131f…=docx 文件名）：7.3.2.4/7.3.2.5/7.3.3/7.3.3.1/7.3.3.2/7.3.3.2.7/7.3.4/7.3.4.1/7.3.4.2/7.3.4.3/7.3.5/7.3.6/7.3.7 全部标题路径；P80 12 单元 phase_scopes=['unknown']。
- `…/structure/blobs/protocol_blocks/3946ea2c….json`：p1013–1167 逐字文本 + numId（12/53/58/59/60/61）。
- `…/source-input/blobs/protocol_sources/362443131f0d….docx`：document.xml 逐字复核（p1015–26 与 blob 完全一致；footnoteReference 计数=0；numId=12 标题 6 处、正文无编号）；流程表 t5/t6 不良事件行 X+gridSpan(7/17)；**脚注26 原文**（numId=29 第26条）；TOC 条目 p221–248（7.3.2.4 页87、7.3.2.5 页87、7.3.3 页87、7.3.3.2.7 页90、7.3.5 页94…）。
- `.trellis/tasks/08-22-…/research/` 三矩阵 + `artifacts/phase5-slice61bl-…/required_procedures.json`：ADR/SUSAR/非预期/因果 0 命中；唯一“不良事件”源引用为 D1 基线复核注记与允许合并用药边界；唯一“24小时”为润肤剂洗脱。
- 第79包 worker_01 报告仅作证据模式参照，本报告所有结论均独立复核。

## Commands And Observations

| 工具/命令 | 目标 | 观察 |
|---|---|---|
| Bash ls / Glob | 工作区结构 | body.pXXXX 为协议正文页引用；证据位于 slice59i 工件 + .trellis/research + slice61bl |
| python3 json | frozen_phase_plan.json | P77–99 所有权/页范围/无重复/无缺口；P80 context 与 owned 明细 |
| python3 json | coverage_manifest.json | 标题层级、unit_kind、phase_scopes、manifest sha |
| python3 json | protocol_blocks | p1013–1167 逐字文本 + numbering（numId 12/53/58/59/60/61）|
| python3 zipfile+re | 原始 docx document.xml | p1015–26 逐字一致；TOC 7.3.2.4/2.5/3.3/3.3.2.7/3.5/3.6/3.7；flow 表 AE 行 gridSpan；**脚注26 原文**；footnoteReference=0 |
| python3 json | 三矩阵 + required_procedures | ADR/SUSAR 0 命中；“24小时”仅润肤剂；“不良事件”仅 D1 复核/允许治疗引用 |

未运行测试、未启动服务、未写任何文件。

## Blockers Or Missing Environment

无阻塞。四点供 Codex/worker_02 留意（非错误）：
1. **p1095 “参照表7” vs p1097 “表 9”**：源内交叉引用疑似笔误（表9=因果关系评价表）。逐字保留，不得静默修正；如需澄清属源方案问题，应由 Codex 依“方案为权威”原则裁量。
2. **P80 context_units 未含 p1013–p1014（SAE 标准⑤⑥）**：SUSAR 定义（p1018）引用“严重不良反应”概念，闭包配置建议把 SAE 定义/标准①–⑥（p997–p1014）加入 context 锚点集（owned 仍仅 p1015–26）。
3. **末次安全随访 vs 末次访视**：p1022+脚注26（末次安全性随访/退出）与 p1024（末次访视）措辞不同，闭包须保留两条独立表述与两个独立锚点（Ⅱ期 W16 / Ⅲ期 W56）。
4. **blob unit_kind 为 paragraph、无列表项**：第80包内无 numId=58 类列表；但跨包引用中 numId=58 列表在第83/84/93/95/96包出现（含 P95/P96 跨包切分），闭包配置勿按 blob 类型误判其他包列表归属。

## Rerun Requests Or Next Step

- 本项（只读核对）已完成，可交 worker_02（闭包配置/父级临床核对清单/确定性测试）与 worker_03（反例审查）。给 worker_02 的关键锚点：
  - **owned**：body.p1015–p1026（12 单元，双期通用）；**context 建议**：p986、p997–p1014、t5/t6 AE行+脚注26、p903/p972、p1050、p1099、p1055–1073、p1096、p1100–1137。
  - **语义锁**：ADR 至少合理可能性；SUSAR=严重∧可疑∧非预期（AND，p1018↔p1127↔p1134–37）；非预期权威参照=IB（p1019+p1099）；ICF后首次服药前=病史/伴随疾病≠AE（p1023+p1050）；收集期=首次服药后→末次安全随访/退出（p1022+脚注26）≠记录范围=首次服药→末次访视（p1024）；单一事件项只记一个术语（p1026↔p1028–29↔表7↔p1035–36）；P80 文本不得改写为筛选/基线入排门槛。
  - **防吞并**：报告义务=第92–99包；因果共同判断=第90包；肝损伤SAE+24h=第85–86包；AE记录细则=第81–84包；严重程度分级=第88–89包；统计分析“治疗前清单”=统计章节。
- 本 worker 无后续动作；最终临床/来源权威结论由 Codex 裁量。
