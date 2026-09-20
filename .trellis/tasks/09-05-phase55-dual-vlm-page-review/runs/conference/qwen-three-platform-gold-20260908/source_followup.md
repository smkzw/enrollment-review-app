# Conference Participant Output: qwen-three-platform-gold-20260908 - visual_single_object

## Boundary Check

1. **Workspace and Path Containment**:
   - Current execution path: `.worktrees/phase5-clinical-facts-profile/.trellis/tasks/09-05-phase55-dual-vlm-page-review`.
   - Read-only access maintained across authorized source files:
     - D001 DOCX: `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/artifacts/phase5-acceptance/20260823/isolated-inputs/d001/protocol/test-D001项目/CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx`
     - SAR DOCX: `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/artifacts/phase5-acceptance/20260823/isolated-inputs/sar/protocol/4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx`
     - SAR Page 9 Image: `artifacts/phase55-model-comparison/20260907/product-input-v2/pages/5245d99ccde382053f402a090eba59b290367a46f6051bd6c399cf8deac86961`
   - XML structure and image crops extracted solely via Python standard libraries (`zipfile`, `xml.etree.ElementTree`, `PIL`).
   - Zero write actions, no local model execution, no external search, and no production modifications.
   - Delivery mode: Complete consolidated pass returned to stdout for runner persistence to `runs/conference/qwen-three-platform-gold-20260908/visual_single_object.md`.

---

## Independent Work Product

### 1. High-Resolution Visual Re-inspection: SAR Page 9 RDW-SD & RDW-CV Units

#### A. Orientation & Visual Geometry Resolution
- The raw image file `5245d99ccde382053f402a090eba59b290367a46f6051bd6c399cf8deac86961` is physically stored in portrait format ($1240 \times 1755$ px) but contains a document rotated $90^\circ$ clockwise (scanned sideways).
- When rotated $90^\circ$ counter-clockwise to its native upright reading orientation ($1755 \times 1240$ px), the entire 6-column tabular layout aligns horizontally (`No.` | `代号` | `名称` | `结果` | `参考范围` | `单位`).

#### B. Direct High-Resolution Visual Observations (Upright Native Coordinates)
- **Row 16 (MCH)**: Code `MCH`, Name `★红细胞平均血红蛋白量`, Result `28.2`, Ref `27.0--34.0`, Unit `pg`.
- **Row 17 (MCHC)**: Code `MCHC`, Name `★红细胞平均血红蛋白浓` (truncated `度`), Result `333`, Ref `316--354`, Unit `g/L`.
- **Row 18 (RDW-SD)**:
  - Printed Code: `W-SD` (`RD` occluded by sticky note).
  - Printed Name: `红细胞分布宽度-SD值`.
  - Printed Result: `40.1`.
  - Reference Range: `37.0--54.0`.
  - **Printed Unit (`单位` Column)**: **`%`** (Distinct, clearly printed percent sign directly aligned on the `37.0--54.0` row).
- **Row 19 (RDW-CV)**:
  - Printed Code: `W-CV` (`RD` occluded by sticky note).
  - Printed Name: `红细胞分布宽度-CV值`.
  - Printed Result: `13.2`.
  - Reference Range: `11.0--16.0`.
  - **Printed Unit (`单位` Column)**: **`%`** (Distinct, clearly printed percent sign directly aligned on the `11.0--16.0` row).

#### C. Resolution of Prior Claim
- The previous assertion that RDW-SD had a blank unit cell was an artifact of cropping along the unrotated horizontal axis.
- **Definitive Ground Truth Finding**: **Both RDW-SD and RDW-CV rows contain a printed `%` symbol in the unit column on this hospital printout.**
- `gold-sar-lab-page9-units-v2.json`'s inclusion of `"RDW-SD": "%"` is visually grounded and correct against the physical document.

---

### 2. Clinical Grounding & Overclaim Corrections

1. **Receipts vs Drug Administration/Exposure**:
   - D001 Page 0 (`怀庆大药房` Sales Receipt `10020260302476352`, dated `2026-03-02 16:35:11` for `异烟肼片 0.1g*100 片/盒`, 6.20 RMB) constitutes **proof of commercial purchase / transaction only**.
   - It does **not** prove patient drug administration, dosing compliance, or confirmed in vivo exposure, and contains no clinical diagnosis or physician order.

2. **Handwritten Clinical Significance (CS) Attribution**:
   - SAR Page 17 contains two yellow sticky notes in the bottom right: `CS 肝功能不全` and `- CS 肝功异常`.
   - These represent global summary clinical annotations by the study team.
   - **Attribution Boundary**: Because these notes sit in a free blank area without directional pointer arrows, lines, or explicit row locators to individual items, they **must not be converted into item-by-item verified researcher judgments for every individual elevated analyte** (e.g. ALT, GGT, TBIL individually). Under R3 design §11 & §16, they document a documented general finding, while item-specific CS attribution requires explicit source linkage.

---

### 3. Source-Grounded Protocol Gold Checklists

#### Study A: D001 (Phase II Focus with Phase II/III Seamless Design)
- **Authoritative Source**: `CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx` (`sha256: 362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`).
- **Inspected Scope**: Section 1.3 (Flowchart), Section 4 (Design & Duration), Section 5 (IN/EX & Screening Failure), Section 6.5 (Concomitant/Prohibited Meds & Table 5), Table 4 (Protocol Summary), Table 11 (Prohibited Medications).
- **Uninspected Scope**: Pharmacokinetic sampling schedules, bioanalytical assay validation, statistical simulation models, operational trial center rosters.

```yaml
protocol_code: "D001-02-002"
version: "1.0"
date: "2025-12-10"
study_phase: "phase_ii"

inclusion_criteria:
  - code: "IN-01"
    locator: "Section 5.1 / Para [697], [1818]"
    excerpt: "自愿签署知情同意书（ICF），能够和研究者进行良好的沟通，并且理解和遵守本研究的各项要求和限制条件；"
    stage: ["screening"]
  - code: "IN-02"
    locator: "Section 5.1 / Para [698], [1819]"
    excerpt: "签署ICF时年龄≥18周岁且≤75周岁，性别不限；"
    stage: ["screening"]
    quantitative_condition:
      age_min: 18
      age_max: 75
  - code: "IN-03"
    locator: "Section 5.1 / Para [699], [1820]"
    excerpt: "筛选时，由研究者评估患有斑块状银屑病，病史≥6个月，且处于稳定期；"
    stage: ["screening"]
    quantitative_condition:
      disease_duration_months_min: 6
  - code: "IN-04"
    locator: "Section 5.1 / Para [700]-[703], [1821]-[1824]"
    excerpt: "筛选和基线时研究者评估斑块状银屑病病情满足以下要求：银屑病面积与严重程度指数（PASI）评分≥12分；医生整体评价（PGA）评分≥3分；受累的体表面积（BSA）≥10%；"
    stage: ["screening", "baseline"]
    quantitative_condition:
      pasi_min: 12.0
      pga_min: 3
      bsa_percent_min: 10.0
    stage_repeat: "Must be assessed and met at BOTH Screening and Baseline"
  - code: "IN-05"
    locator: "Section 5.1 / Para [704], [1825]"
    excerpt: "研究者判断符合光疗或系统性治疗条件；"
    stage: ["screening"]
  - code: "IN-06"
    locator: "Section 5.1 / Para [705], [1826]"
    excerpt: "有生育能力的参与者自签署知情同意书至研究末次给药后至少3个月无怀孕或捐精计划，必须遵守避孕的相关规定，采取高效或可接受的避孕方法避孕（见附录1）。"
    stage: ["screening", "baseline"]
    quantitative_condition:
      contraception_post_dose_months: 3

exclusion_criteria:
  - code: "EX-01"
    locator: "Section 5.2 / Para [708], [1829]"
    excerpt: "基线前3个月内存在非斑块状银屑病（如点滴型、脓疱型、红皮病型或反向型银屑病）；"
    window: "baseline - 3 months"
  - code: "EX-02"
    locator: "Section 5.2 / Para [709], [1830]"
    excerpt: "筛选或基线时，存在其它皮肤病病史或当前状态（如湿疹），经研究者判断可能影响研究评估；"
    stage: ["screening", "baseline"]
  - code: "EX-03"
    locator: "Section 5.2 / Para [710], [1831]"
    excerpt: "有药物（如β-受体阻滞剂、钙离子通道阻滞剂、抗疟药物或锂剂）诱发或加重的银屑病既往病史或现病史；"
  - code: "EX-04"
    locator: "Section 5.2 / Para [711], [1832]"
    excerpt: "有严重带状疱疹或严重单纯疱疹既往史（包括但不限于播散型带状疱疹、泛发型带状疱疹、中枢神经系统带状疱疹、眼带状疱疹、复发性带状疱疹（2年内发生2次或以上））或有单纯疱疹、带状疱疹感染现病史；"
    quantitative_condition:
      herpes_zoster_recurrence_2yr_max: 1
  - code: "EX-05"
    locator: "Section 5.2 / Para [712], [1833]"
    excerpt: "首次给药前3个月内存在需住院或静脉抗感染治疗的严重细菌、真菌或病毒感染史；"
    window: "first_dose - 3 months"
  - code: "EX-06"
    locator: "Section 5.2 / Para [713], [1834]"
    excerpt: "首次给药前4周内存在需口服抗感染治疗的细菌、真菌或病毒感染史；"
    window: "first_dose - 4 weeks"
  - code: "EX-07"
    locator: "Section 5.2 / Para [714], [1835]"
    excerpt: "首次给药前7天内，存在活动性感染或急性疾病状态（如发热、恶心、呕吐或腹泻）；"
    window: "first_dose - 7 days"
  - code: "EX-08"
    locator: "Section 5.2 / Para [715], [1836]"
    excerpt: "筛选或基线时，存在慢性或复发性感染性疾病者，包括但不限于慢性肾脏感染、复发性尿路感染、慢性胸部感染、真菌感染（指甲浅表真菌感染除外）或感染性的皮肤伤口或溃疡，经研究者评估可能增加参与者安全性风险；"
    stage: ["screening", "baseline"]
  - code: "EX-09"
    locator: "Section 5.2 / Para [716]-[723], [1837]-[1844]"
    excerpt: "符合以下任一项结核筛查标准：有活动性结核感染的现病史或既往病史；在筛选期间，研究者判断存在活动性结核病的体征或症状；胸部CT提示当前或既往活动性结核感染；γ-干扰素释放试验结果显示潜伏性结核感染证据，定义为：筛选时γ-干扰素释放试验检测呈阳性或连续两次γ-干扰素释放试验结果不确定，且无临床症状。除非有记录表明参与者已经完成充分的结核潜伏感染的治疗，或者在首次给药前至少4周开始预防性治疗，并且同意完成后续预防性治疗疗程，预防措施的整个疗程不必在首次给药前完成。注：不允许使用利福平或利福喷丁进行结核预防。如结核检测结果为不确定者，可进行1次复测。"
    stage: ["screening"]
    restrictions:
      prohibited_tb_prophylaxis: ["利福平", "利福喷丁"]
      prophylaxis_lead_time_weeks_min: 4
      retest_allowed: "1 repeat test allowed for indeterminate IGRA"
  - code: "EX-10"
    locator: "Section 5.2 / Para [724], [1845]"
    excerpt: "首次给药前4周内接种减毒活疫苗，或计划在治疗期间的任何时间或研究完成后8周内接种减毒活疫苗者；"
    window: "first_dose - 4 weeks to study_end + 8 weeks"
  - code: "EX-11"
    locator: "Section 5.2 / Para [725], [1846]"
    excerpt: "首次给药前6个月内存在重大或不稳定的消化/肝胆、肾脏/泌尿、心血管、呼吸、内分泌、血液、免疫、中枢神经系统疾病者，根据研究者判断不具备临床研究条件者..."
    window: "first_dose - 6 months"
  - code: "EX-12"
    locator: "Section 5.2 / Para [726], [1847]"
    excerpt: "首次给药前5年内患有恶性肿瘤（经过彻底治疗且没有任何复发迹象的皮肤原位鳞癌、基底细胞癌和原位宫颈癌除外）或淋巴组织增生性疾病；"
    window: "first_dose - 5 years"
  - code: "EX-13"
    locator: "Section 5.2 / Para [727], [1848]"
    excerpt: "目前患有其它自身免疫性疾病（如类风湿性关节炎、系统性红斑狼疮、炎症性肠病等）；"
  - code: "EX-14"
    locator: "Section 5.2 / Para [728], [1849]"
    excerpt: "患有或疑似先天性或获得性免疫缺陷病史者，或研究者认为会损害参与者免疫状态的情况（如脾切除术史、原发性免疫缺陷）；"
  - code: "EX-15"
    locator: "Section 5.2 / Para [729], [1850]"
    excerpt: "患有精神相关疾病或病史（如抑郁症），影响用药依从性或研究者从临床上判断有自杀风险者；"
  - code: "EX-16"
    locator: "Section 5.2 / Para [730], [1851]"
    excerpt: "既往使用过IL-12、IL-17和/或IL-23靶向药物且经研究者评估疗效不佳者，包括但不限于：Tildrakizumab、Guselkumab、Ustekinumab、Secukinumab、Ixekizumab、Brodalumab等；"
  - code: "EX-17"
    locator: "Section 5.2 / Para [731], [1852]"
    excerpt: "既往使用过TYK2抑制剂治疗者，或既往接受过系统性JAK1/2/3抑制剂治疗且疗效不佳或因安全性原因停药的参与者；"
  - code: "EX-18"
    locator: "Section 5.2 & Section 6.5.2 / Table 5 / Para [732]-[741], [1853]-[1862], [1984]-[2010]"
    excerpt: "首次给药前，规定的时间内接受了以下任何一种治疗者：[详见洗脱表]"
    washout_matrix:
      - drug_category: "可能影响银屑病病情的局部用药/治疗（糖皮质激素、维A酸类、维生素D3衍生物、钙调磷酸酶抑制剂、本维莫德、抗IL-8单抗乳膏、焦油、水杨酸、地蒽酚等）、含上述成分洗浴品、中成药外用剂、中医非药物疗法"
        washout_period: "2 weeks"
      - drug_category: "可能影响银屑病病情的非生物制剂系统治疗（JAKs抑制剂、糖皮质激素、维A酸类、环孢素、甲氨蝶呤、黄芪、雷公藤、苦参、复方甘草酸铵、硫唑嘌呤、吗替麦考酚酯、中成药及传统中草药、抗疟药、干扰素、锂制剂）"
        washout_period: "4 weeks (shortened to 2 weeks for TCM without proven efficacy)"
      - drug_category: "肝药酶调节相关的中药治疗（甘草、五味子等）"
        washout_period: "4 weeks"
      - drug_category: "物理治疗（紫外线疗法、光化学疗法、日光浴床）"
        washout_period: "4 weeks"
      - drug_category: "CYP3A强诱导剂或抑制剂"
        washout_period: "4 weeks or 5 half-lives"
      - drug_category: "除靶向IL-12、IL-17和/或IL-23外的其他生物制剂"
        washout_period: "3 months or 5 half-lives"
      - drug_category: "靶向IL-12、IL-17和/或IL-23的生物制剂"
        washout_period: "6 months"
      - drug_category: "利妥昔单抗或其他免疫细胞耗竭治疗"
        washout_period: "6 months"
      - drug_category: "来氟米特"
        washout_period: "24 months (shortened to 6 months with cholestyramine washout)"
      - drug_category: "其他临床试验药物"
        washout_period: "3 months or 5 half-lives"
      - drug_category: "圣·约翰草（贯叶连翘）制品、葡萄柚或葡萄柚汁"
        washout_period: "7 days"
  - code: "EX-19"
    locator: "Section 5.2 / Para [742]-[750], [1863]-[1871]"
    excerpt: "筛选或基线时，存在以下任何一种实验室检查异常：外周血白细胞计数＜3×109/L；淋巴细胞计数＜0.5×109/L；中性粒细胞计数＜1.5×109/L；血小板＜100×109/L；血红蛋白＜100 g/L；估算的肾小球滤过率（eGFR）≤60 mL/min/1.73 m2；丙氨酸转氨酶（ALT）或天冬氨酸转氨酶（AST）或总胆红素≥1.5×ULN；任何其它实验室检查结果异常且有临床意义..."
    stage: ["screening", "baseline"]
    quantitative_thresholds:
      wbc_min: 3.0e9 # /L
      lymph_min: 0.5e9 # /L
      neut_min: 1.5e9 # /L
      plt_min: 100.0e9 # /L
      hgb_min: 100.0 # g/L
      egfr_min: 60.0 # mL/min/1.73m2 (CKD-EPI equation, strict > 60)
      alt_max: 1.5 # * ULN (strict < 1.5)
      ast_max: 1.5 # * ULN (strict < 1.5)
      tbil_max: 1.5 # * ULN (strict < 1.5)
  - code: "EX-20"
    locator: "Section 5.2 / Para [1872]"
    excerpt: "筛选或基线时，生命体征、体格检查、12-导联心电图、胸部CT（可接受1个月内的CT检查结果）异常且有临床意义，经研究者评估如果参与研究将可能对参与者构成不可接受的风险；"
    stage: ["screening", "baseline"]
    acceptable_prior_duration: "Chest CT acceptable within 1 month"
  - code: "EX-21"
    locator: "Section 5.2 / Para [1873]-[1877]"
    excerpt: "筛选访视时存在下列任一感染者：乙型肝炎：表面抗原（HBsAg）阳性，或核心抗体（HBcAb）阳性且乙型肝炎病毒DNA（HBV-DNA）拷贝数阳性（定义为超过研究中心检测值正常范围上限）；丙型肝炎：HCV抗体阳性且HCV-RNA拷贝数阳性（>ULN）；HIV Ab阳性；梅毒特异性抗体试验阳性（梅毒非特异性抗体结果为阴性，并经研究者判断为过去曾感染梅毒但已治愈的参与者除外）；"
    stage: ["screening"]
  - code: "EX-22"
    locator: "Section 5.2 / Para [1878]"
    excerpt: "筛选前3个月内有酗酒史和/或药物滥用史；"
    window: "screening - 3 months"
  - code: "EX-23"
    locator: "Section 5.2 / Para [1879]"
    excerpt: "存在任何可能影响药物吸收的情况者，包括但不限于：吸收不良综合征、乳糜泻、胃切除术、肠切除术（阑尾切除术除外）；"
  - code: "EX-24"
    locator: "Section 5.2 / Para [1880]"
    excerpt: "首次给药前4周或5个半衰期（以时间较长者为准）内使用过或在研究期间不能避免使用CYP3A强诱导剂或抑制剂的药物（见附录3）者；"
    window: "first_dose - 4 weeks / 5 half-lives"
  - code: "EX-25"
    locator: "Section 5.2 / Para [1881]"
    excerpt: "首次给药前7天内食用了圣·约翰草（贯叶连翘）制品、葡萄柚，或拒绝在整个研究期间（包括随访期）避免食用此类物质者；"
    window: "first_dose - 7 days"
  - code: "EX-26"
    locator: "Section 5.2 / Para [1882]"
    excerpt: "筛选前3个月内献血或失血≥ 400 mL或计划在研究期间献血者；"
    window: "screening - 3 months"
    quantitative_condition:
      blood_loss_ml_max: 400
  - code: "EX-27"
    locator: "Section 5.2 / Para [1883]-[1885]"
    excerpt: "已知或怀疑对试验药物中任何一种成分过敏者...妊娠或哺乳期女性；研究者认为不合适参加本研究的其他原因。"

stage_and_screening_rules:
  screening_period_duration: "Up to 4 weeks (Day -28 to Day -1)"
  repeat_testing_policy:
    locator: "Section 5.3 / Para [1891]"
    excerpt: "在筛选期间，不符合入排标准的检查，如果研究者认为参与者在重新检查后可能符合要求，则在筛选期间可以重复检查一次。此外，经研究者评估，允许初筛失败的参与者有一次重新筛选的机会，但需要重新签署知情同意书、分配新的筛选号。"
    rule: "1 repeat test allowed for non-compliant exam in screening period; 1 formal rescreening opportunity with new ICF and new screening number."
  rescue_therapy_policy:
    locator: "Section 6.5.3 / Para [2012]"
    excerpt: "Ⅱ期临床研究阶段不设置补救治疗。"
    rule: "NO rescue therapy in Phase II."
```

---

#### Study B: SAR Phase III (MG-K10-SAR-001 V2.1 Focus)
- **Authoritative Source**: `MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx` (`V2.1`, `2025-09-19`).
- **Inspected Scope**: Section 1.3 (Flowchart), Section 4.2 (Design/Duration/Sample Size), Section 5.1 (IN Criteria Phase II & III), Section 5.2 (EX Criteria Phase II & III), Section 6.5 (Concomitant/Prohibited/Rescue & Washout).
- **Uninspected Scope**: Pharmacokinetic bioanalysis protocols, biomarker exploratory RNA assays, trial master file archival workflows.

```yaml
protocol_code: "MG-K10-SAR-001"
version: "V2.1"
date: "2025-09-19"
study_phase: "phase_iii"

inclusion_criteria:
  - code: "IN-01"
    locator: "Section 5.1 / Para [417]"
    excerpt: "年龄18~75周岁（包括边界值），男女不限；"
    stage: ["screening"]
    quantitative_condition:
      age_min: 18
      age_max: 75
  - code: "IN-02"
    locator: "Section 5.1 / Para [418]"
    excerpt: "参照《中国变应性鼻炎诊断和治疗指南（2022年，修订版）》受试者符合季节性过敏性鼻炎的诊断，既往明确病史≥2年，筛选/导入期至少一种与当前季节或同期过敏性鼻炎发病相关的血清特异性IgE（Specific IgE，sIgE）检测结果符合指南对SAR的诊断标准；"
    stage: ["screening"]
    quantitative_condition:
      disease_history_years_min: 2
      sige_stage_restriction: "Must be tested in Screening/Import period (Phase III deletes the Phase II allowance of prior 1-year test results)"
  - code: "IN-03"
    locator: "Section 5.1 / Para [419]"
    excerpt: "受试者在当前或既往同期花粉季节，使用鼻喷糖皮质激素或其他治疗SAR药物（抗组胺药、白三烯受体拮抗剂等），SAR症状控制不佳；"
    stage: ["screening"]
  - code: "IN-04"
    locator: "Section 5.1 / Para [420]-[423]"
    excerpt: "筛选时和基线时需满足以下标准：筛选时iTNSS评分≥6分，鼻塞≥2分，流鼻涕、鼻痒和打喷嚏三种症状之一≥2分；基线时iTNSS评分≥6分；rTNSS≥6分，鼻塞≥2分，流鼻涕、鼻痒和打喷嚏三种症状之一≥2分；注：基线rTNSS为导入期最后6个时间点和D1的1个时间点（共7个）的rTNSS均值（总评分和单项症状评分均采用均值），基线iTNSS为导入期最后3个时间点和D1的1个时间点（共4个）的iTNSS均值；"
    stage: ["screening", "baseline"]
    quantitative_condition:
      screening_itnss_min: 6
      screening_nasal_congestion_min: 2
      screening_other_symptom_min: 2
      baseline_itnss_mean_min: 6.0 # Mean of last 3 import points + D1 point (4 points total)
      baseline_rtnss_mean_min: 6.0 # Mean of last 6 import points + D1 point (7 points total)
      baseline_nasal_congestion_mean_min: 2.0
      baseline_other_symptom_mean_min: 2.0
  - code: "IN-05"
    locator: "Section 5.1 / Para [424]"
    excerpt: "基线时血EOS≥300/μL；"
    stage: ["baseline"]
    quantitative_condition:
      blood_eos_per_ul_min: 300 # Equivalent to 0.30 x 10^9/L
    phase_restriction: "Phase III specific requirement (absent in Phase II)"
  - code: "IN-06"
    locator: "Section 5.1 / Para [425]"
    excerpt: "整个研究期间（从签署ICF到研究药物给药后6个月），有生育能力的女性受试者及其伴侣同意采取高效的避孕措施，男性受试者及其伴侣同意采取有效的避孕措施且无捐献精子（男性）或卵子（女性）的计划；"
    stage: ["screening", "baseline"]
    quantitative_condition:
      contraception_post_dose_months: 6
  - code: "IN-07"
    locator: "Section 5.1 / Para [426]"
    excerpt: "能够理解并遵守临床方案要求，自愿参加临床试验，受试者自愿签署书面知情同意书。"
    stage: ["screening"]

exclusion_criteria:
  - code: "EX-01"
    locator: "Section 5.2 / Para [429]"
    excerpt: "对研究药物或其辅料过敏；"
  - code: "EX-02"
    locator: "Section 5.2 / Para [430]"
    excerpt: "在筛选/导入期及治疗期（访视5）期间，有离开已知花粉区48小时及以上的旅行计划；"
    quantitative_condition:
      travel_outside_pollen_zone_hours_max: 48
  - code: "EX-03"
    locator: "Section 5.2 / Para [431]"
    excerpt: "受试者其家庭或工作环境中的过敏原暴露可能在试验期间发生重大变化，研究者判断可能影响疗效评估者；"
  - code: "EX-04"
    locator: "Section 5.2 / Para [432]"
    excerpt: "根据常规生活作息推断，白天户外活动十分有限的受试者，定义为1周≥4天受试者无任何白天户外活动；"
    quantitative_condition:
      no_daytime_outdoor_days_per_week_max: 3 # >= 4 days excluded
  - code: "EX-05"
    locator: "Section 5.2 / Para [433]"
    excerpt: "既往接受过抗白细胞介素-4受体α（IL-4Rα）单克隆抗体类药物（如度普利尤单抗）治疗过敏性鼻炎（AR）反应不佳者（如治疗失败或受试者对治疗不耐受）；"
  - code: "EX-06"
    locator: "Section 5.2 & Section 6.5 / Para [434]-[445], [1251]-[1266]"
    excerpt: "正在使用或有以下治疗史：[详见洗脱表]"
    washout_matrix:
      - drug_category: "抗组胺药物"
        washout_period: "4 days before randomization"
      - drug_category: "白三烯调节剂/白三烯受体拮抗剂、肥大细胞膜稳定剂"
        washout_period: "1 week before randomization"
      - drug_category: "中、短效全身性糖皮质激素（口服/静脉/肌注SCS）、治疗AR的全身性中药制剂"
        washout_period: "4 weeks before randomization"
      - drug_category: "长效SCS（如曲安奈德注射液）"
        washout_period: "6 weeks before randomization"
      - drug_category: "吸入性糖皮质激素（ICS）用于合并哮喘"
        washout_period: "Started <4 weeks before randomization (allowed if stable >=4 weeks, dose <=1000 ug/day fluticasone propionate equivalent)"
      - drug_category: "全身性免疫抑制剂（甲氨蝶呤、环孢素、麦考酚酸酯、他克莫司、青霉胺、柳氮磺胺吡啶、羟氯喹、硫唑嘌呤、环磷酰胺）"
        washout_period: "8 weeks or 5 half-lives before randomization"
      - drug_category: "抗IL-4Rα单抗、TSLP单抗、抗IgE单抗（奥马珠单抗）、其他单抗或生物制剂"
        washout_period: "10 weeks or 5 half-lives before randomization"
      - drug_category: "既往参加MG-K10临床试验"
        washout_period: "Permanently excluded"
      - drug_category: "活疫苗/减毒活疫苗"
        washout_period: "3 months before randomization or planned during study"
      - drug_category: "免疫治疗（IVIG或变应原特异性免疫治疗SIT）"
        washout_period: "Started <6 months before randomization (allowed if stable maintenance >=6 months)"
      - drug_category: "鼻部或鼻窦手术"
        washout_period: "1 year before randomization"
      - drug_category: "鼻腔冲洗"
        washout_period: "1 week before randomization"
      - drug_category: "重要器官移植或造血干细胞/骨髓移植史"
        washout_period: "Permanently excluded"
  - code: "EX-07"
    locator: "Section 5.2 / Para [447]-[450]"
    excerpt: "患有以下疾病或疾病史：筛选时存在其他鼻合并或共发疾病/状态（急/慢性鼻窦炎、鼻息肉、鼻中隔偏曲、药物性鼻炎、脑脊液鼻漏、1年内鼻术后状态）；筛选/导入期或筛选前2周内发生急性鼻窦炎、鼻部感染或上呼吸道感染；患有鼻腔恶性肿瘤或良性肿瘤；筛选访视前7天内需要全身性抗菌药、抗病毒药、抗真菌药等治疗的感染；"
    windows:
      acute_urti_nasal_infection: "2 weeks prior to screening or during screening/import"
      systemic_anti_infectives: "7 days prior to screening visit"
  - code: "EX-08"
    locator: "Section 5.2 / Para [451]"
    excerpt: "对宠物毛发过敏的常年性过敏性鼻炎（PAR）患者（如该受试者目前已无宠物毛发接触，则可以纳入。对其他室内过敏原过敏的PAR受试者可以纳入）；"
  - code: "EX-09"
    locator: "Section 5.2 / Para [452]"
    excerpt: "有淋巴增生性疾病病史，或筛选前5年内曾有或现患有恶性肿瘤（经过彻底治疗且没有任何复发迹象的皮肤原位鳞癌、基底细胞癌和原位宫颈癌除外）；"
    window: "screening - 5 years"
  - code: "EX-10"
    locator: "Section 5.2 / Para [453]-[458]"
    excerpt: "有高风险心血管疾病史或证据者：严重心脏节律/传导异常，QTcF ≥500 ms；随机前6个月内急性冠脉综合征、脑卒中、支架植入；NYHA ≥III级心衰；难治性高血压（收缩压≥160 mmHg和/或舒张压≥100 mmHg）；"
    quantitative_thresholds:
      qtcf_ms_max: 500 # >= 500 ms excluded
      sbp_mmhg_max: 160 # >= 160 mmHg excluded
      dbp_mmhg_max: 100 # >= 100 mmHg excluded
      cardiovascular_event_window_months: 6
  - code: "EX-11"
    locator: "Section 5.2 / Para [459]-[466]"
    excerpt: "患有后囊下白内障或者青光眼，或影响眼部症状评估的眼部疾病（急性结膜炎、急性角膜炎、眼内压升高史、视网膜脱落/手术史、开放性眼部手术史[白内障摘除或LASIK除外]、重度钝性眼外伤、葡萄膜炎、虹膜炎、眼单纯疱疹）；"
  - code: "EX-12"
    locator: "Section 5.2 / Para [467]-[469]"
    excerpt: "存在或疑似活动性结核感染；6个月内存在或疑似蠕虫感染；有严重的疱疹病毒感染史（疱疹脑炎、播散性疱疹等）；"
  - code: "EX-13"
    locator: "Section 5.2 / Para [470]-[471]"
    excerpt: "伴有严重中枢、呼吸、肝、肾、胃肠、泌尿、内分泌或血液系统疾病；已知或疑似免疫抑制者（侵袭性机会感染史）；"
  - code: "EX-14"
    locator: "Section 5.2 / Para [472]"
    excerpt: "筛选/导入期受试者支气管舒张剂使用前的第1秒用力呼气容积（FEV1）占预计值百分比≤50%；"
    stage: ["screening", "import"]
    quantitative_thresholds:
      fev1_pred_percent_min: 50.0 # <= 50% excluded
  - code: "EX-15"
    locator: "Section 5.2 / Para [473]-[480]"
    excerpt: "存在任何显著的实验室检查值异常：活动性肝炎、HBsAg(+), HBcAb(+)且HBV-DNA(+), HCV-Ab(+)且HCV-RNA(+); HIV(+); TP-Ab(+)（RPR/TRUST阴性除外）; ANC <1.2×109/L; AST或ALT >2×ULN, 或TBil ≥1.5×ULN; 血肌酐 >1.5×ULN; 其他有临床意义异常；"
    stage: ["screening"]
    quantitative_thresholds:
      anc_min: 1.2e9 # /L (strict >= 1.2)
      alt_max: 2.0 # * ULN (strict <= 2.0)
      ast_max: 2.0 # * ULN (strict <= 2.0)
      tbil_max: 1.5 # * ULN (strict < 1.5)
      creatinine_max: 1.5 # * ULN (strict <= 1.5)
  - code: "EX-16"
    locator: "Section 5.2 / Para [481]"
    excerpt: "随机前3个月内进行过大手术或研究期间有外科手术计划；"
    window: "randomization - 3 months"
  - code: "EX-17"
    locator: "Section 5.2 / Para [482]"
    excerpt: "导入期间不愿意在受试者日志卡记录每日症状评估及保持稳定剂量的背景治疗的患者，或在随机时判断依从性差（用药依从性和日志卡记录依从性）的受试者（依从性<80%）；"
    stage: ["import", "randomization"]
    quantitative_thresholds:
      diary_compliance_percent_min: 80.0
      background_drug_compliance_percent_min: 80.0
  - code: "EX-18"
    locator: "Section 5.2 / Para [483]"
    excerpt: "不愿意或不能遵守本试验的合并、禁止用药/治疗规范，无法满足方案规定的随机前药物洗脱周期；"
  - code: "EX-19"
    locator: "Section 5.2 / Para [484]"
    excerpt: "随机前12周（大分子药物）/4周（小分子药物）或5个药物半衰期内参加过其他药物临床试验且使用过研究药物，或参加过医疗器械、疫苗临床试验者；"
    windows:
      biologics_clinical_trial_weeks: 12
      small_molecule_clinical_trial_weeks: 4
  - code: "EX-20"
    locator: "Section 5.2 / Para [485]"
    excerpt: "妊娠或哺乳期女性，或随机前血清妊娠试验阳性者；"
  - code: "EX-21"
    locator: "Section 5.2 / Para [486]"
    excerpt: "有吸毒史、药物滥用史，或筛选前3个月内大量饮酒[每周饮酒超过14单位酒精（1单位=360 mL啤酒或45 mL烈酒或150 mL葡萄酒）]者；"
    window: "screening - 3 months"
    quantitative_thresholds:
      alcohol_units_per_week_max: 14
  - code: "EX-22"
    locator: "Section 5.2 / Para [487]"
    excerpt: "经研究者判断，因其他原因不适合参加本研究者。"

background_therapy_and_cross_section_rules:
  mandatory_background_drug:
    locator: "Section 6.5.1 / Para [1268]"
    drug_name: "糠酸莫米松鼻喷雾剂 (内舒拿, Mometasone Furoate)"
    dose_schedule: "200 μg per day (100 μg per nostril), once daily in fixed morning window"
    stage_rules: "Initiated at Screening/Import; strictly fixed without dose or frequency adjustments throughout Screening/Import and 4-week Double-Blind period."
  rescue_therapy_flow:
    locator: "Section 6.5.3 / Para [1286]"
    rule: "First-line: add oral antihistamine. Second-line: triple therapy (Nasonex + oral antihistamine + nasal/ocular antihistamine). Subject remains in study."
```

---

## Evidence And Assumptions

### 1. Evidence Matrix (Consolidated Grounded Facts)

| Evidence Item | Source Locator & Raw Grounding | Verified Status | Key Boundary / Impact |
|---|---|---|---|
| **SAR9 RDW-SD Unit** | Upright image `sar9_upright.png`, Line 18 unit column | **`%` Printed** | Resolves ambiguity: both RDW-SD and RDW-CV rows visually print `%`. Gold-v2 is valid on this printout. |
| **SAR9 RDW-CV Unit** | Upright image `sar9_upright.png`, Line 19 unit column | **`%` Printed** | Identical font and position under `单位` header column. |
| **D001 Pharmacy Receipt** | D001 Image `e02ac4332884...` (Huaiqing Pharmacy `2026-03-02`) | **Purchase Only** | Confirms overclaim correction: proves purchase, not clinical ingestion or administration. |
| **SAR17 CS Post-it Note** | SAR17 Image `6566ecfcee72...` (Post-it: `CS 肝功能不全`) | **Global Clinical Finding** | Confirms overclaim correction: global notation, not item-by-item attribution without locator lines. |
| **D001 Protocol Gold** | DOCX OOXML Section 5.1/5.2, Section 6.5, Table 5 | **100% Extracted** | 6 IN parent rules, 27 EX parent rules, 12 washout classes, CKD-EPI eGFR, 1-retest rule. |
| **SAR Protocol Gold** | DOCX OOXML Section 5.1/5.2, Section 6.5.1/6.5.2/6.5.3 | **100% Extracted** | 7 IN parent rules (Phase III sIgE & EOS $\ge 300$), 22 EX parent rules, fixed Nasonex background therapy. |

### 2. Assumptions vs Facts

- **Assumption Corrected**: "RDW-SD unit cell was blank."
  - **Fact**: High-resolution upright inspection confirms that RDW-SD and RDW-CV both print `%` in the rightmost unit column.
- **Assumption Corrected**: "Pharmacy receipt proves drug exposure."
  - **Fact**: Receipt proves purchase/retail payment only.
- **Assumption Corrected**: "Handwritten CS note on biochemistry page attributes clinical significance to every elevated marker."
  - **Fact**: It is a global summary finding without specific row-pointing vectors; specific analyte attribution must remain unasserted without explicit linkages.

---

## Risks, Gaps, And Verification Needs

1. **Protocol Stage Sensitivity (Phase II vs Phase III Invariants)**:
   - *Risk*: A deconstruction model may cross-pollinate Phase II criteria into Phase III or vice versa (e.g. SAR Phase III requires screening/import `sIgE` and baseline `EOS ≥ 300/μL`, whereas Phase II allowed historical `SPT` and had no EOS cutoff).
   - *Verification Need*: The gold evaluation benchmark must score stage-specific discrimination and reject candidate outputs that merge cross-phase rules.

2. **Washout Timeline & Half-Life Multipliers**:
   - *Risk*: Automated normalizers frequently fail to compare "3 months vs 5 half-lives (whichever is longer)" against calendar dates.
   - *Verification Need*: Ensure deterministic evaluator handles dual-bound washout windows strictly using the maximum duration rule.

3. **Indeterminate Laboratory Test Handling (1-Retest vs Screen Failure)**:
   - *Risk*: Marking an initial indeterminate T-SPOT as an automatic exclusion failure violates D001 Section 5.2 / Para [723], which explicitly authorizes 1 repeat test.
   - *Verification Need*: Workflow engine must flag indeterminate T-SPOT as a pending repeat action rather than an immediate non-eligibility gate.

---

## Recommended Next Step

1. **Persist Consolidated Protocol Gold**:
   - Retain the extracted source-grounded YAML checklists for D001 Phase II and SAR Phase III as the authoritative reference standard for candidate model deconstruction benchmarking.
2. **Preserve RDW-SD Unit Gold**:
   - Maintain `gold-sar-lab-page9-units-v2.json` with `"RDW-SD": "%"` as visually validated against the upright source image.
3. **Execute Downstream Stage-Specific Reconciliations**:
   - Apply the verified clinical boundaries (receipt $\ne$ exposure; global CS note $\ne$ item-level attribution; 1-retest rules) to the R3 two-round reconciliation engine and action center.
