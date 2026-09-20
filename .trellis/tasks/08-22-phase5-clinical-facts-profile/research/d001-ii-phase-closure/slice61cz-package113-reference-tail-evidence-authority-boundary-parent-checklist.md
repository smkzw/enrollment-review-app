# Slice61cz Package 113 参考文献尾部与方案正文权威边界 Parent Checklist

## 1. 执行身份与冻结边界

- Task: `phase5-slice61cz-20260830`
- Group: `d001-ii-package113-reference-tail-evidence-authority-boundary`
- Frozen plan: `papl-e17d498106b6f71f440ff2be`
- Package 113: `pap-d042355fa4845796808fa256`
- Selected phase: `phase_ii`
- Protocol SHA-256: `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- Frozen plan SHA-256: `92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4`
- Structure blob SHA-256: `3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`

本执行只做模型外来源闭包、源文驱动的参考文献尾部题录/方案正文权威分层处置、Package 112/114
边界隔离、确定性 batch/prompt 干跑和专项测试。不得调用临床语义模型，不得发布 control point，
不得进入受试者、OCR、Patient Profile、浏览器或视觉流程。所有产物必须保持
`claims_complete=false`；`parent clinical acceptance` 仍由 Codex 决定。

## 2. Package 113 的唯一 owned 闭包与只读边界

冻结计划中 Package 113 严格且仅拥有以下两个来源单元，按原始文档顺序恢复：

1. `body.p1307` — Finlay AY, Khan GK. Dermatology Life Quality Index (DLQI)--a simple practical measure for routine clinical use. Clin Exp Dermatol. 1994;19:210–6.
2. `body.p1308` — 国家药品监督管理局.药品注册管理办法.2020.

`attached_source_refs=[]`。冻结计划中的 38 项 `context_units` 仅只读，未经 Codex 另行授权不得升格为附加来源。Package 112 止于 `body.p1306`；`body.p1306` 仅作为本包前向只读语境，不得升格为本包来源或候选；`body.p1309` 空白分隔全局无主、不在冻结覆盖单元中，不得吸入本包；Package 114 从 `body.p1310`（`附录`）起，不得吸入。

## 3. 先读源文，再区分权威层级

### 3.1 参考文献题录，非方案执行条款

- p1307 为 Finlay/Khan DLQI 论文题录。其标题不授权 DLQI 问卷、评分公式、切点、受试者资格或审查动作。
- p1308 为国家药品监督管理局《药品注册管理办法》题录。其标题不授权受试者级入排规则、申办方/研究中心流程、监管申报程序或资格判定。
- 语义说明必须明确“参考文献题录、非方案执行条款”；处置使用既有 `non_enrollment_execution`，不新增领域枚举。
- 方案正文仍是执行权威。
- DLQI 真实执行权威在方案正文 p826-p827 及附录 p1386、p1417-p1419，分别由 Package 74、125、128 持有；Package 113 不得从 p1307 题录反向复制、缩写或改写这些内容。
- Package 114 自 p1310 开始的附录内容同样保持独立所有权，不得被本参考文献包吸收。

### 3.2 候选处置结论

完成源文判断后确认：本包两项来源均未形成独立的“真实参加研究前可核验受试者动作”。

- p1307-p1308 维持 `non_enrollment_execution`；
- `required_candidate_source_refs=[]`，`pre_enrollment_source_refs=[]`；
- 全部两项进入 `forbidden_candidate_source_refs`；
- `structural_only_source_refs=[]`（章节标题“参考文献”已由 Package 112 的 p1295 持有）；
- 零候选不是预设，而是逐项原文依据后的结论；若后续发现真实前置控制被丢失，必须停止并回退。

因此不得把 DLQI 或药品注册管理办法题录误成单例资格、评分算法、注册程序或方案执行流程，也不得用 `other_control_candidate` 强挂受试者工作流，也不得丢失任何真实前置控制。

## 4. 配置盲检

配置文件：

`configs/representative_group_package113_reference_tail_evidence_authority_boundary.v1.json`

配置必须满足：

- `owned_source_refs` 恰为 p1307-p1308；`attached_source_refs=[]`；
- `required_candidate_source_refs=[]`；两个来源均位于 `forbidden_candidate_source_refs`；
- `structural_only_source_refs=[]`；
- p1307-p1308 为 `non_enrollment_execution`；
- workflow / procedure / action / visit 绑定为空；`known_targets.official_rules` 与 `required_procedures` 均为空；
- exception_semantics / clinical_qc 完整保留参考文献题录与方案正文权威分层及 Package 112/114 边界；
- p1306 owner=112，p1307/p1308 owner=113，p1310 owner=114；
- `excluded_unowned_structure_refs` 精确记录 p1309，不得进入 owned/attached/prompt；
- 38 项语境中无主项精确写入 `unowned_context_source_refs`；
- `claims_complete` 只能为 `false`。

## 5. 所有权、期别与源文回归

- 覆盖清单 p1307-p1308 的 `study_phase` 均为 `phase_ii`、`phase_scopes` 均为 `unknown`；
  `unit_kind` 均为 `list_item`；source order 为 `32030, 32040`。
- 各来源的 `source_span_ids` 与 `member_source_refs` 各自只含对应 list_item。
- 38 项 context_units 与 owned 不相交，且不得作为本包候选、workflow binding、官方规则或必需程序来源。
- Package 112 的 p1306 及以前、Package 114 的 p1310 及以后，以及无主的 p1309 空白分隔，均不得出现在本包 owned/attached 或 dry-run prompt 声明来源中。
- Package 74 的 p826-p827、Package 125 的 p1386 和 Package 128 的 p1417-p1419 是可核对的 DLQI 正文/附录权威，必须与 p1307 题录保持分离，不得进入 Package 113 的 owned、attached 或 dry-run prompt。

## 6. 确定性模型外 dry-run 与预期证据

在仓库根目录运行：

```bash
.venv/bin/python \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py \
  --config \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package113_reference_tail_evidence_authority_boundary.v1.json \
  --dry-run
```

预期观察：

- `owned_count=2`、`attached_count=0`、`unit_count=2`，`claims_complete=false`；
- `source_rows.json` 按 p1307-p1308 顺序包含两项，全部 `role=owned` 且解析到 Package 113；
- `execution/batch.json` 的 owned IDs 只有上述两项；structural-only 为空；
  pre-enrollment 为空；official rules 与 required procedures 为空；
- `execution/prompt.txt` 只出现本包两项的声明来源和逐字源文，不出现 p1306 跨包升格、p1310 附录、无主空白分隔 p1309，也不把 DLQI 或药品注册管理办法题录写成方案执行阈值、评分算法或注册程序；
- 来源身份门禁必须拦截似是而非的输出，包括“DLQI评分在0-30分之间”、“DLQI总分至少4分视为具有临床重要性”、“DLQI评分细则见附录6”及“依据药品注册管理办法提交临床试验申请”；这些拦截依赖 p1307/p1308 的禁止候选来源身份，不依赖穷举关键词。
- `clinical-qc.json` 的所有 `agent_candidates` 仍为空，gate 标记为 dry-run skipped；零候选是源文判断结论，不是未水合借口。

## 7. 回归命令与停止条件

专项回归：

```bash
.venv/bin/python -m pytest -q \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61cz_package113_reference_tail_evidence_authority_boundary.py
```

父级允许的相邻包回归由 Codex 在合并后执行。任一来源 SHA、frozen owner、source order、
phase scope、原文摘录、权威分层、零候选逐项依据、或 Package 112/114 隔离失败时，停止并深挖。
本 worker 未被授权修改共享代码；若出现共享代码阻塞，只报告可复现证据。

## 8. Codex 独立最终检查

本 checklist 只证明模型外准备闭包、源文驱动的参考文献尾部/方案正文权威边界处置和确定性回归路径。它不证明：

- 临床候选内容已由模型解析或接受；
- publication gate、clinical QC 或 parent clinical acceptance 已通过；
- D001 全量来源、受试者档案、Patient Profile 或浏览器流程已完成；
- 真实资料中的参考文献引用效力或方案正文评估/监管程序已经验证；
- 真实受试者已经完成任何参加研究前控制。

最终判定必须由 Codex 依据冻结来源、干跑证据、专项及相邻包回归和 parent clinical gates 另行完成。
