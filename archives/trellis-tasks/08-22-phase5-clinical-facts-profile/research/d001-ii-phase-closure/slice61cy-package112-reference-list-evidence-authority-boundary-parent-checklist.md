# Slice61cy Package 112 参考文献与方案正文权威边界 Parent Checklist

## 1. 执行身份与冻结边界

- Task: `phase5-slice61cy-20260830`
- Group: `d001-ii-package112-reference-list-evidence-authority-boundary`
- Frozen plan: `papl-e17d498106b6f71f440ff2be`
- Package 112: `pap-fa6b2b871b90b62bbfe81775`
- Selected phase: `phase_ii`
- Protocol SHA-256: `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- Frozen plan SHA-256: `92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4`
- Structure blob SHA-256: `3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`

本执行只做模型外来源闭包、源文驱动的参考文献题录/方案正文权威分层处置、Package 111/113
边界隔离、确定性 batch/prompt 干跑和专项测试。不得调用临床语义模型，不得发布 control point，
不得进入受试者、OCR、Patient Profile、浏览器或视觉流程。所有产物必须保持
`claims_complete=false`；`parent clinical acceptance` 仍由 Codex 决定。

## 2. Package 112 的唯一 owned 闭包与只读边界

冻结计划中 Package 112 严格且仅拥有以下十二个来源单元，按原始文档顺序恢复：

1. `body.p1295` — `参考文献`，章节标题，仅结构来源。
2. `body.p1296` — 中华医学会皮肤性病学分会银屑病专业委员会. 中国银屑病诊疗指南（2023版）[J]. 中华皮肤科杂志, 2023,56(7):573-625.
3. `body.p1297` — 黄丹,陈崑.银屑病相关流行病学调查进展[J].诊断学理论与实践,2021,20(01):48-52.
4. `body.p1298` — 李慧贤,胡丽,郑焱,等.基于全球疾病负担(GBD)大数据的中国银屑病流行病学负担分析[J].中国皮肤性病学杂志,2021,35(04):386-392.
5. `body.p1299` — Griffiths CEM, Armstrong AW, Gudjonsson JE, et al. Psoriasis. The Lancet. 2021;397:1301–15.
6. `body.p1300` — Armstrong AW, Read C. Pathophysiology, Clinical Presentation, and Treatment of Psoriasis: A Review. JAMA. 2020;323:1945–60.
7. `body.p1301` — Xin P, Xu X, Deng C, et al. The role of JAK/STAT signaling pathway and its inhibitors in diseases. Int Immunopharmacol. 2020 Mar;80:106210.
8. `body.p1302` — Krueger JG, McInnes IB, Blauvelt A. Tyrosine kinase 2 and Janus kinase‒signal transducer and activator of transcription signaling and inhibition in plaque psoriasis. J Am Acad Dermatol. 2022;86:148–57.
9. `body.p1303` — Deucravacitinib. FDA Multi-Discipline Review. 2022.
10. `body.p1304` — Feldman SR, Krueger GG. Psoriasis assessment tools in clinical trials. Ann Rheum Dis. 2005;64 Suppl 2:ii65-8; discussion ii69-73.
11. `body.p1305` — Bożek A, Reich A. The reliability of three psoriasis assessment tools: Psoriasis area and severity index, body surface area and physician global assessment. Adv Clin Exp Med. 2017;26:851–6.
12. `body.p1306` — Thomas CL, Finlay AY. The “handprint” approximates to 1% of the total body surface area whereas the “palm minus the fingers” does not. Br J Dermatol. 2007;157:1080–1.

`attached_source_refs=[]`。冻结计划中的 38 项 `context_units` 仅只读，未经 Codex 另行授权不得升格为附加来源。Package 111 止于 `body.p1291`、`body.p1292`、`body.t15.r0`、`body.t15.r1`；`body.p1293`-`body.p1294` 与 `body.p1309` 空白分隔均全局无主、不在冻结覆盖单元中，不得吸入本包；Package 113 从 `body.p1307` 起拥有 `body.p1307`-`body.p1308`，其中 `body.p1307` 仅作为本包前向只读语境，不得升格为本包来源或候选。

## 3. 先读源文，再区分两类语义

### 3.1 章节标题结构

- p1295 只提供“参考文献”结构与语境，不产生单例资格，也不授权从后续题录反向生成评估程序。

### 3.2 参考文献题录，非方案执行条款

- p1296-p1306 均为参考文献题录（指南、流行病学、GBD 负担、Lancet/JAMA 综述、JAK/STAT、TYK2、Deucravacitinib FDA 审评、评估工具、PASI/BSA/PGA 可靠性、handprint 约 1% BSA）。
- 语义说明必须明确“参考文献题录、非方案执行条款”；处置使用既有 `non_enrollment_execution`，不新增领域枚举。
- 题录中出现的银屑病指南、JAK/STAT、TYK2、Deucravacitinib、PASI/BSA/PGA、handprint 和 `1%` 均不能反向生成受试者阈值、评分公式、诊断标准或执行程序。
- 方案正文仍是执行权威。

### 3.3 候选处置结论

完成源文判断后确认：本包十二项来源均未形成独立的“真实参加研究前可核验受试者动作”。

- p1295 维持结构来源；
- p1296-p1306 维持 `non_enrollment_execution`；
- `required_candidate_source_refs=[]`，`pre_enrollment_source_refs=[]`；
- 全部十二项进入 `forbidden_candidate_source_refs`；
- 零候选不是预设，而是逐项原文依据后的结论；若后续发现真实前置控制被丢失，必须停止并回退。

因此不得把参考文献题录误成单例资格或方案执行程序，也不得用 `other_control_candidate` 强挂受试者工作流，也不得丢失任何真实前置控制。

## 4. 配置盲检

配置文件：

`configs/representative_group_package112_reference_list_evidence_authority_boundary.v1.json`

配置必须满足：

- `owned_source_refs` 恰为 p1295-p1306；`attached_source_refs=[]`；
- `required_candidate_source_refs=[]`；十二个来源均位于 `forbidden_candidate_source_refs`；
- `structural_only_source_refs` 恰为 p1295；
- p1296-p1306 为 `non_enrollment_execution`；
- workflow / procedure / action / visit 绑定为空；`known_targets.official_rules` 与 `required_procedures` 均为空；
- exception_semantics / clinical_qc 完整保留两类语义与 Package 111/113 边界；
- p1291/p1292/t15.r1 owner=111，p1295/p1306 owner=112，p1307/p1308 owner=113；
- `excluded_unowned_structure_refs` 精确记录 p1293、p1294、p1309，它们均不得进入 owned/attached/prompt；
- 38 项语境中无主项精确写入 `unowned_context_source_refs`；
- `claims_complete` 只能为 `false`。

## 5. 所有权、期别与源文回归

- 覆盖清单 p1295-p1306 的 `study_phase` 均为 `phase_ii`、`phase_scopes` 均为 `unknown`；
  `unit_kind` 分别为 `paragraph` 与十一项 `list_item`；source order 为
  `31910, 31920, 31930, 31940, 31950, 31960, 31970, 31980, 31990, 32000, 32010, 32020`。
- 各来源的 `source_span_ids` 与 `member_source_refs` 各自只含对应 paragraph/list_item。
- 38 项 context_units 与 owned 不相交，且不得作为本包候选、workflow binding、官方规则或必需程序来源。
- Package 111 的 p1291/p1292/t15 及以前、Package 113 的 p1307 及以后，以及无主的 p1293-p1294 与 p1309 空白分隔，均不得出现在本包 owned/attached 或 dry-run prompt 声明来源中。

## 6. 确定性模型外 dry-run 与预期证据

在仓库根目录运行：

```bash
.venv/bin/python \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py \
  --config \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package112_reference_list_evidence_authority_boundary.v1.json \
  --dry-run
```

预期观察：

- `owned_count=12`、`attached_count=0`、`unit_count=12`，`claims_complete=false`；
- `source_rows.json` 按 p1295-p1306 顺序包含十二项，全部 `role=owned` 且解析到 Package 112；
- `execution/batch.json` 的 owned IDs 只有上述十二项；structural-only 为 p1295；
  pre-enrollment 为空；official rules 与 required procedures 为空；
- `execution/prompt.txt` 只出现本包十二项的声明来源和逐字源文，不出现 p1291/p1292/t15、p1307/p1308 跨包来源、无主空白分隔，也不把 PASI/BSA/PGA/handprint/1% 题录写成方案执行阈值；
- `clinical-qc.json` 的所有 `agent_candidates` 仍为空，gate 标记为 dry-run skipped；零候选是源文判断结论，不是未水合借口。

## 7. 回归命令与停止条件

专项回归：

```bash
.venv/bin/python -m pytest -q \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61cy_package112_reference_list_evidence_authority_boundary.py
```

父级允许的相邻包回归由 Codex 在合并后执行。任一来源 SHA、frozen owner、source order、
phase scope、原文摘录、两类语义分层、零候选逐项依据、或 Package 111/113 隔离失败时，停止并深挖。
本 worker 未被授权修改共享代码；若出现共享代码阻塞，只报告可复现证据。

## 8. Codex 独立最终检查

本 checklist 只证明模型外准备闭包、源文驱动的参考文献/方案正文权威边界处置和确定性回归路径。它不证明：

- 临床候选内容已由模型解析或接受；
- publication gate、clinical QC 或 parent clinical acceptance 已通过；
- D001 全量来源、受试者档案、Patient Profile 或浏览器流程已完成；
- 真实资料中的参考文献引用效力或方案正文评估程序已经验证；
- 真实受试者已经完成任何参加研究前控制。

最终判定必须由 Codex 依据冻结来源、干跑证据、专项及相邻包回归和 parent clinical gates 另行完成。
