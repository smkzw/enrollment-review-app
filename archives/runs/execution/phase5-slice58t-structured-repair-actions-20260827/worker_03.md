# Execution Output: phase5-slice58t-structured-repair-actions-20260827 - worker_03

## Boundary And Context Check

- 已读取指定执行上下文和计划。
- 仅复核当前 slice58s 执行产物、冻结包原文、门禁结果及方案期别边界。
- 未修改应用代码、测试代码、临床源文件或生产路径；未发起新的模型调用、服务启动或重跑。
- 当前执行上下文的 `Source Of Truth` 仍为 `TODO`。本报告将当前 slice58s 执行 JSON、来源映射、冻结清单及哈希匹配的隔离 DOCX 作为审计输入，不替代 Codex 的最终来源授权和临床验收。

## Work Performed

### 1. 冻结身份和包映射

当前运行：

- `run_id`: `d001-ii-phase-closure-20260827-slice58s-4pkg`
- `protocol_version_id`: `D001-02-002:v1.0:phase-ii`
- selected phase: `phase_ii`
- opposite phase: `phase_iii`
- manifest: `d001-ii-phase-closure-20260825-slice58e-manifest`
- snapshot: `d001-ii-phase-closure-20260825-slice58e-snapshot`
- protocol SHA-256: `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- source plan: `papl-a1b37e552acf8e0f60916c2e`
- derived plan: `papl-402d3ef8fc4d2aed787d1790`
- 4 个包共 48 个 owned targets，每包 12 个。

| slice58s来源序号 | 当前包 ID | 原文范围 | 当前状态 | 尝试次数 |
|---:|---|---|---|---:|
| 36 | `pap-8b9672e0a43a3da307f6c2f8` | `body.p314–p325` | `needs_review` | 3 |
| 60 | `pap-4c2c71d74c2aa5a04f757a5c` | `body.p663–p674` | `needs_review` | 3 |
| 78 | `pap-e61081da23952cd50b07f604` | `body.p802–p813` | `needs_review` | 3 |
| 121 | `pap-016c5ee9ed82b0875b231e54` | `body.p1322–p1333` | `accepted` | 1 |

### 2. 包36原文和临床边界

原文均位于 `方案摘要 > 研究流程表`，`phase_scopes=unknown`：

```text
body.p314：注：计划外访视可根据研究者的判断在任何时间进行，并可根据临床指征进行必要的临床和实验室检查。
body.p315：开始任何试验流程之前签署知情同意书。
body.p316：如果筛选访视和D1访视间隔≤7天，则筛选和基线访视可合并进行，两次访视中相同的评估事项可只进行一次。如果筛选访视和D1访视间隔＞7天，则需在D1天前7天内进行基线访视。以给药前最近一次评估结果作为基线值。生命体征、疗效指标（PASI、PGA、BSA、DLQI）、皮损照片以D1给药前结果作为基线值。
body.p317：人口学资料：包括出生日期、性别、民族、年龄等信息。
body.p318：既往和现病史收集：包括既往病史/伴随疾病、过敏史、个人史（吸烟史、饮酒史、药物滥用史）、家族史、月经史（女性）、生育史（女性）等。病史应包括尽可能过去2年内研究者认为具有临床意义的个人病史信息。银屑病病史应记录详细信息，包括诊断时间、相关疾病特征、病程等。排除标准中要求审查的病史时间范围遵循排除标准的规定时间收集。
body.p319：治疗史收集：包括药物治疗史、非药物治疗史及手术史等，尽可能收集银屑病相关的治疗史，其他疾病过去半年内的治疗史。排除标准中要求审查的病史时间范围遵循排除标准的规定时间收集。
body.p320：身高和体重：筛选访视进行身高和体重测量，其余访视点进行体重测量。
body.p321：生命体征：筛选期、D1/D15/D29/D57/D85（当天用药前）、D113或提前退出时进行测量。测量前建议静息至少5分钟后，进行体温、血压（坐位）、脉博（坐位）、呼吸频率测量，如有异常，根据研究者判断，可重复测量。
body.p322：体格检查：筛选/基线、D85 及 D113或提前退出访视时需进行全面的体格检查，其余访视可根据临床症状和体征的变化，进行症状导向的体格检查，需在当天用药前进行。全面的体格检查包括：一般情况、皮肤/黏膜、淋巴结、头颈部、胸部、腹部、脊柱及四肢、神经系统等。
body.p323：血常规：白细胞计数（WBC）、红细胞计数（RBC）、血红蛋白（Hb）、血小板计数（PLT）、白细胞分类计数和百分比（中性粒细胞、淋巴细胞、单核细胞、嗜酸性粒细胞和嗜碱性粒细胞）、血细胞比容（HCT)、平均红细胞容积（MCV）、平均红细胞血红蛋白含量（MCH）、平均红细胞血红蛋白浓度（MCHC）、网织红细胞计数和百分比。
body.p324：尿常规：酸碱度（PH）、尿比重、尿酮体、尿蛋白、尿葡萄糖、尿白细胞、尿红细胞(隐血)、尿胆红素、尿亚硝酸盐、尿胆原。
body.p325：血生化（全部）：总蛋白（TP）、白蛋白（ALB）、球蛋白（GLO）、总胆红素（TBIL）、直接胆红素（DBIL）、丙氨酸基转移酶（ALT）、天门冬氨酸基转移酶（AST）、碱性磷酸酶（ALP）、乳酸脱氢酶（LDH）、谷氨酰转肽酶（GGT）、尿素（Urea）/尿素氮（BUN）、肌酐（Cr）、尿酸（UA）、葡萄糖（GLU）、甘油三酯（TG）、总胆固醇（TC）、低密度脂蛋白胆固醇（LDL-C）、高密度脂蛋白胆固醇（HDL-C）、肌酸磷酸激酶（CPK）、钾（K）、钠（Na）、氯（Cl）、镁（Mg）、钙（Ca）、磷（P）。本检查应空腹采样。
```

边界核对：

- `body.p312` 明确为Ⅱ期流程表，`body.p343` 明确为Ⅲ期流程表；两期访视时间和持续时间不同。
- `body.p932` 是Ⅱ期“计划外访视/检查”的实质性操作说明；`body.p979` 是Ⅲ期指向Ⅱ期同类操作的交叉引用。
- 当前包上下文包含 `body.p931` 和 `body.p978` 的标题锚点，但未包含实质性 `body.p932`、`body.p979`。
- 因此，不能仅凭 `p312/p343` 的表题或 `p931/p978` 的标题，认定 `p314` 的期别范围或跨期共用。
- `p314` 是计划外访视的通用操作注释，不应扩展为具体访视时间表、随机条件或安全性结论。

### 3. 包60原文和临床边界

原文均位于 `研究人群 > 排除标准`，`phase_scopes=unknown`：

```text
body.p663：既往使用过IL-12、IL-17和/或IL-23靶向药物且经研究者评估疗效不佳者，包括但不限于：Tildrakizumab（替瑞奇珠单抗）、Guselkumab（古塞奇尤单抗）、Ustekinumab（乌司奴单抗）、Secukinumab（司库奇尤单抗）、Ixekizumab（依奇珠单抗）、Brodalumab（布罗利尤单抗）等；
body.p664：既往使用过TYK2抑制剂治疗者，或既往接受过系统性JAK1/2/3抑制剂治疗且疗效不佳或因安全性原因停药的参与者；
body.p665：首次给药前，规定的时间内接受了以下任何一种治疗者：
body.p666：2周内使用可能影响银屑病病情的局部用药/治疗（包括但不限于：糖皮质激素、维A酸类、维生素D3衍生物、钙调磷酸酶抑制剂、本维莫德、抗人IL-8单克隆抗体乳膏、焦油、水杨酸、地蒽酚等）或含有上述成分的洗浴产品，或可能影响银屑病病情的中成药外用剂、中医非药物疗法；
body.p667：4周内使用可能影响银屑病病情的非生物制剂系统治疗，包括但不限于JAKs抑制剂、糖皮质激素、维A酸类、环孢素、甲氨蝶呤、黄芪、雷公藤、苦参、复方甘草酸铵、硫唑嘌呤、吗替麦考酚酯、中成药及传统中草药（对于无明确临床证据可能改善银屑病病情的中成药或传统中草药，可缩短为给药前2周内）、抗疟药、干扰素或锂制剂等；
body.p668：4周内接受过肝药酶调节相关的中药治疗（如甘草、五味子等）；
body.p669：4周内进行物理治疗，包括但不限于：紫外线疗法、光化学疗法、采用日光浴床自我治疗等；
body.p670：3个月或5个半衰期内（以时间较长者为准）接受除靶向IL-12、IL-17和/或IL-23外的其他生物制剂治疗；
body.p671：6个月内接受靶向IL-12、IL-17和/或IL-23的生物制剂治疗；
body.p672：6个月内接受过利妥昔单抗或其他免疫细胞耗竭治疗；
body.p673：24个月内接受过来氟米特（经来氟米特药物清除剂进行洗脱者可缩短至6个月）；
body.p674：首次给药前3个月或5个半衰期内（以时间较长者为准）使用其他临床试验药物或目前正在参加其他临床研究者；
```

边界核对：

- `p663` 是一个具体的既往靶向药疗效不佳排除标准。
- `p664–p674` 是不同药物类别、治疗类型和时间窗的独立排除条款，不能合并为一个“既往免疫治疗”结论。
- 当前上下文中的 `body.p526`（Ⅱ期）和 `body.p555`（Ⅲ期）仅写明“符合所有入选标准而不符合任何排除标准的参与者视为合格”，属于泛化排除标准提及，不是 `p663` 的直接临床依据。
- 若没有两期均明确指向 `p663` 这一具体规则的来源，安全处置应为 `unresolved`，不能用泛化“排除标准”语句强行形成跨期共用或单一期别结论。

### 4. 包78原文和临床边界

原文均位于实验室、病毒学和结核筛查相关章节，`phase_scopes=unknown`：

```text
body.p802：②根据新出现的安全性数据，经研究者和申办者同意，可能需要进行其他检测。
body.p803：病毒学检查
body.p804：将根据标准实验室程序进行包括乙肝表面抗原、乙肝表面抗体、乙肝e抗原、乙肝e抗体、乙肝核心抗体、丙型肝炎病毒抗体、人类免疫缺陷病毒抗体、梅毒特异性抗体检查。可接受在首次给药前28天内的结果，筛选期/基线期无需再次检查。
body.p805：乙型肝炎表面抗原阴性且乙型肝炎核心抗体阳性的参与者，需要进行HBV-DNA检测；丙型肝炎病毒抗体阳性的参与者，需要进行HCV-RNA检测。若梅毒特异性抗体检查阳性，则进行梅毒非特异性抗体检查。可接受在首次给药前28天内的结果，无需再次检查。
body.p806：结核筛查
body.p807：如果γ-干扰素释放试验为阳性，则必须通过胸部CT进一步评估以确认结核状态（活动性或潜伏性）。
body.p808：−有活动性结核证据的参与者不得被随机分组；
body.p809：−有潜伏性结核证据的参与者不得被随机分组，除非在随机分组前已完成至少4周的适当治疗疗程。
body.p810：注：
body.p811：在筛选时，如果参与者有潜伏性结核感染的证据，必须在首次给药前至少4周开始预防性治疗，并且同意完成后续预防性治疗疗程；预防措施的整个疗程不必在首次给药前完成。
body.p812：不允许使用利福平或利福喷丁进行结核预防。
body.p813：如结核检测结果为不确定者，可进行1次复测。
```

边界核对：

- `p802` 是基于新安全性数据、研究者和申办者同意的条件性“其他检测”条款；不等同于病毒学或结核筛查。
- `p803–p805` 是病毒学检查及其条件性复检。
- `p806–p813` 是结核筛查、随机限制、预防治疗和复测规则。
- 当前上下文的 `body.p801#atom-0-39` 与 `body.p801#atom-39-58` 明确显示两期糖化血红蛋白访视不同：Ⅱ期为筛选和12周，Ⅲ期为筛选、16周和52周；该混合注释不能广播到 `p802–p813`。
- `body.p765` 的“除给药时长外两期评估和程序一致”也不能覆盖具体实验室、病毒学、结核和访视差异。

### 5. 包121原文和临床边界

原文均位于附录，`phase_scopes=unknown`：

```text
body.p1322：女性连续停经12个月，并排除妊娠及其他可能导致闭经的医疗原因后，即可临床诊断为绝经。
body.p1323：2.有生育能力女性参与者的避孕规定与方法
body.p1324：在筛选时血妊娠试验阴性后，必须开始采取适当的避孕措施。
body.p1325：从签署知情同意书之日开始至研究药物末次给药后3个月为止，期间参与者必须同意持续和正确地使用一种高效或可接受的避孕方法进行避孕（禁止使用激素类避孕）。研究者或指定人员应与参与者讨论，确认参与者已从允许的避孕方法中选择了最适合其避孕的方法（下述），并确认参与者已知晓研究期间需持续并正确地使用该方法。
body.p1326：在研究流程中计划的访视点，研究者或指定人员将告知参与者需要持续使用高效或可接受的避孕方法，并在参与者病历中记录与之的对话和参与者的同意（参与者需要确认她同意将持续并正确使用至少1种选定的避孕方法）。此外，还应告知参与者，如果她已停用所选的避孕方法，或，已知或怀疑怀孕，需立即打电话给研究者或指定人员。
body.p1327：高效的避孕方法是指持续和正确地使用时，年失败率低于1%的避孕方法。包括：
body.p1328：正确放置含铜的宫内节育器（Intrauterine-device，IUD）
body.p1329：男性伴侣绝育
body.p1330：双侧输卵管结扎/双侧输卵管切除术/双侧输卵管闭塞术
body.p1331：禁欲。禁欲定义为完全和持续地避免所有的异性性交。禁欲的可靠性需要根据研究的持续时间以及参与者的首选和平常的生活方式进行评估
body.p1332：可接受的避孕方法：含杀精剂的男用避孕套或女用避孕套。男用避孕套和女用避孕套不能同时使用（存在因摩擦失效的风险）。采用可接受的避孕方法时，建议参与者在末次给药结束后每隔一个月经周期进行妊娠检查。对于月经延迟者，强烈建议进行妊娠检查以确认是否怀孕，此建议也适用于月经周期较长或不规律的参与者。
body.p1333：不可接受的避孕方法：评价参与者的避孕首选，以及跟日常生活方式相关的禁欲的可靠性。定期禁欲（如推算日历法、排卵期法、症状体温避孕法或排卵后安全期避孕法）、男性或女性用避孕套（无杀精剂）、杀精海绵等，以及性交中断（或体外射精）都是本研究不可接受的避孕方法。
```

边界核对：

- 当前运行中包121 12/12 个结果均为 `selected_phase_applicable`，每条证据都直接绑定自己的目标 `structure_unit_id` 和同一 `body.p1322–p1333` source span。
- 该包可作为“全局章节直接绑定目标自身来源”的正向控制。
- 它不是Ⅱ期特异规则，也不应被解释为只有Ⅱ期适用；当前结果仅说明在选定Ⅱ期审核中，协议附录规则具有直接适用性。
- 不应将附录男性参与者避孕规则 `body.p1335` 之后的内容带入当前包。

### 6. 当前门禁结果

| 包 | 具体门禁观察 |
|---|---|
| 36 | 第1次：`PAIRED_RULE_FAMILY_SOURCE_IGNORED`，目标 `su-ed8839c09ba00af5ba7fc106`；第2次：`SHARED_POSITIVE_SOURCE_MISSING`，同一目标；第3次再次 `PAIRED_RULE_FAMILY_SOURCE_IGNORED`。无 `final_output`。 |
| 60 | 3次均为 `PAIRED_RULE_FAMILY_SOURCE_IGNORED`，目标 `su-c85c3193c68dcf3586c791d1`。无 `final_output`。 |
| 78 | 第1次：`TARGET_RELATED_SUPPORT_MISSING`，目标 `su-e586e30d375509591d85c183`；第2次：`PAIRED_RULE_FAMILY_SOURCE_IGNORED`，同一目标；第3次：`EVIDENCE_EXCERPT_NOT_VERBATIM`，拒绝 unit index `0–11`。无 `final_output`。 |
| 121 | 1次解析成功，12个结果，0个门禁问题。 |

聚合结果：

- `execution.status=needs_review`
- accepted batches: `1/4`
- accepted units: `12/48`
- unresolved units: `36`
- attempts: `10`
- issue count: `9`
- `claims_full_coverage=false`

注意：`build-summary.json` 仍显示早期 `planned`、0 次尝试；其时间早于 `semantic-summary.json` 和 execution JSON。重跑验收应以更新后的 execution JSON 为运行状态主证据，而不是早期 build summary。

## Artifacts And Evidence

只读检查了：

- `context/phase5-slice58t-structured-repair-actions-20260827_execution_context.md`
- `plans/codex_execution_phase5-slice58t-structured-repair-actions-20260827.md`
- `artifacts/phase5-slice58s-d001-four-package-semantic-validation-20260827/execution/d001-ii-phase-closure-20260827-slice58s-4pkg.json`
- `artifacts/phase5-slice58s-d001-four-package-semantic-validation-20260827/execution/d001-ii-phase-closure-20260827-slice58s-4pkg.package-selection-provenance.json`
- `artifacts/phase5-slice58s-d001-four-package-semantic-validation-20260827/semantic-summary.json`
- `artifacts/phase5-slice58s-d001-four-package-semantic-validation-20260827/build-summary.json`
- 哈希匹配的隔离 DOCX：
  `artifacts/phase5-slice58r6-d001-phase-handoff-atomization-20260827/source-input/blobs/protocol_sources/362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98.docx`
- 期别门禁实现：
  `app/protocols/phase_applicability.py:236-298`
  `app/protocols/phase_applicability.py:760-820`
  `app/protocols/phase_applicability.py:911-945`

未创建或修改任何交付文件；runner 管理的报告文件也未由本 worker 写入。

## Commands And Observations

- `sed`：读取执行上下文和计划；确认本 work item 为四包只读复核。
- `find`、`rg --files`：定位 slice58s execution、provenance、semantic summary 和相关冻结来源。
- `jq`：核对包映射、owned target 数量、原文 excerpt、上下文期别、执行状态及逐条证据。
- `shasum -a 256`：隔离 DOCX SHA-256 与 manifest 一致，为  
  `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`。
- `unzip -p ... word/document.xml | xmllint --format - | rg`：对 `p314`、`p663`、`p802`、`p1322` 等原文片段进行 XML 层抽查，均可定位到原始 DOCX 文本。
- `rg`、`sed`：只读核对门禁实现：
  - unknown/未限定来源不能建立期别范围；
  - selected/opposite 单期期别需要目标相关支持，成对来源存在时需要对侧反证；
  - `cross_phase_shared` 需要同一具体规则族的共享来源或两期正向来源；
  - source span 必须属于引用单元，摘录必须可经既有空白规范化逐字恢复。
- `git status --short`：检查时工作树已存在跨 app/docs/tests 的共享修改；本轮仅执行读取命令，未产生写入。
- 未运行 pytest、oMLX、浏览器或新的语义重跑；这些不属于本只读复核的必要动作。

## Blockers Or Missing Environment

1. 当前执行上下文没有明确授权的 Source Of Truth 文件列表，只有 `TODO`。父级需要确认 slice58e manifest/snapshot 和哈希匹配 DOCX 是否为本次正式来源。
2. 36、60、78 包没有有效 `final_output`，当前只能审计失败门禁，不能形成临床期别最终结论。
3. 包36当前上下文缺少 `body.p932`、`body.p979` 的实质性配对来源；若不扩充上下文，不能可靠完成计划外访视规则的两期比较。
4. 包60缺少明确指向 `p663` 这一具体IL-12/17/23既往治疗排除规则的两期正向来源；泛化 `排除标准` 语句不足以替代。
5. 包78的第3次输出出现全包逐字摘录失败，不能接受任何该次结果，必须重新生成可逐字恢复的证据。
6. 当前 `semantic-summary.json` 未填充 `gate_version`，而 execution JSON 为 `phase5/phase-applicability-gate/v2`；重跑产物应统一主状态和门禁版本。

## Rerun Requests Or Next Step

1. 先冻结并记录新的 rerun identity：原 source plan ID/hash、derived plan ID/hash、manifest、snapshot、protocol SHA、selected/opposite phase，以及旧 ordinal/package ID 到新 package ID 的映射。若增加上下文，必须生成新的 plan/package identity，不能复用旧结果。
2. 失败包重跑至少覆盖 36、60、78；包121作为已接受控制保留。若重建计划导致包121的 package ID、上下文或 plan identity变化，则包121也必须重新跑，不能直接复用旧结果。
3. 每个包必须完整回显当前 12 个 owned targets，结果数量、顺序、`structure_unit_id`、source refs 与冻结包逐项一致；禁止跨包、漏包、额外结果。
4. 对成对来源门禁：
   - 若判定单一期别，必须保留对侧真实“不适用/不覆盖”反证；
   - 若判定 `cross_phase_shared`，必须有同一具体规则/义务族的 `shared` 来源，或两期分别明确指向同一具体规则的正向来源；
   - 禁止使用仅标题、泛化“排除标准”、`body.p765` 或普通邻近上下文冒充正向临床依据。
5. 对包36，建议父级明确决定：是否在新冻结上下文中加入 `body.p932`、`body.p979` 等实质性计划外访视来源。若仍无法满足具体规则族的确定性门禁，应保留 `p314` 为 `unresolved`，不得用 `p312/p343` 表题强行形成跨期共用。
6. 对包60，`p663` 只能绑定该具体IL-12/17/23既往治疗规则；不能将 `p664–p674` 或泛化排除标准语句合并作为支持。若无直接两期证据，返回带具体缺失理由和未解决证据的 `unresolved`。
7. 对包78，`p802` 必须绑定自身或同一实验室检查规则族的逐字来源；病毒学和结核条款必须保持独立。任一无法逐字恢复的证据应删除并改为 `unresolved`，不得摘要、拼接、补标点或凭记忆重写。
8. 重跑通过条件应同时满足：execution 状态为 accepted、4包或声明范围内包的 gate issue 为空、完整 target coverage、source/span/excerpt 校验通过、源哈希和上下文 identity 一致，并继续保持 `claims_full_coverage=false`。本报告不构成最终临床或项目验收。
