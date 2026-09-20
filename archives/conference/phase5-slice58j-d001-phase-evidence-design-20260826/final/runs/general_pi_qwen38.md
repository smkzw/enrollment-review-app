All evidence gathered and cross-checked. Producing the full participant output.

# Conference Participant Output: phase5-slice58j-d001-phase-evidence-design-20260826 - general_pi_qwen38

## Boundary Check

- 只读执行。未写入任何文件（包括指定报告路径 `runs/conference/.../general_pi_qwen38.md`，按要求由 runner 落盘）；未触碰生产路径；未运行 137 包中的任何语义包；未做最终医学/监管验收声明。
- 唯一执行动作是只读回归验证：`python3 -m pytest research/d001-ii-phase-closure/test_matrix_source_closure.py -q` → `4 passed in 0.08s`（当前 155/155 闭包与 `phase_closure.accepted=false`、`claims_complete=false` 断言仍成立）。
- 阅读范围：初始读集两份 + Source Of Truth 清单中的闭包矩阵/报告、交叉章节子集、两个检查点、期别合同三层代码、冻结清单、冻结计划与 137 包执行文件、混合表格原子化中断检查点、5.8d implement 段落。未读源 DOCX（冻结逐字摘录足够，且边界要求不扩展）。
- 我独立重算了全部关键计数，与检查点声明一致处标注一致，不一致或检查点未覆盖处单列（见下）。

## Independent Work Product

### 0. 结论先行（最高影响发现）

1. **60 行 `cross_phase_shared` 目前没有任何结构正向依据**：全 1,840 单元清单中 `shared` 期别范围只有 2 个单元（`su-f53dd8ce26569b198d0c8a26` 盲法、`su-34232d16a76ac7331b7222d3` “Ⅱ/Ⅲ期评估和程序一致”），且**两者都不在 82 行矩阵的 152 个引用单元里**。所以 `PHASE_SHARED_SOURCE_MISSING=60` 不是“等语义跑完就会消失”的缺口，而是“共享正向依据的来源物理上不在行的引用闭包内”。这直接决定证据视图设计：共享判定必须允许引用**章节级桥接单元**（作为证据来源单元），而不是只看行锚点单元。
2. **桥接上下文在包之间不可用**：`su-34232d16a76ac7331b7222d3` 只作为 context 出现在 pkg 75–81；pkg 36–40（流程表）、57–63（入排）、69–71（合并用药）、121（附录避孕）的 context 里**都没有**。若不修复，语义结果会把“上下文可用性差异”伪装成“临床差异”——同一类共同章节主张在结核包能引用桥接、在合并用药包不能。
3. **2 行共享声明与其自身锚点结构矛盾**：`pcm-row-c6eb8bbf8636dc83110216e6`、`pcm-row-689838943c7e4a51c5345e67` 标注 `cross_phase_shared`，但全部锚点单元范围是 `('phase_ii',)`。这不是缺证据，是**声明与结构冲突**，只能降级为 selected 或另行给出共享正向依据；语义包无法救这两行。
4. **妊娠混合单元是治疗后污染与原子化阻断的交点**：`pcm-row-b6b5156590be97880322fe9f`（妊娠检测节点与首次给药门控，`cross_phase_shared`）锚定 `su-f92576bc405dcf2453e25994`，范围 `('mixed',)`，段内同时含“筛选、基线、第12周（Ⅱ期）”与“第16、52周访视（Ⅲ期）”。发布合同 `PHASE_MIXED_REJECTED`（`protocol_control_matrix.py:2028-2029`）会硬拒；单单元四类处置无法表达成员差异（与 `CHECKPOINT_20260825_MIXED_TABLE_ATOMIZATION_INTERRUPTED.md` 的表 32 根因同构）。此行**必须先结构原子化或拆行**，任何语义包都不得先跑。
5. **重复计数已有现成结构**：12 个表5控制行全部以 `supplementary_requirement` 指向 EX-18 洗脱行 `pcm-row-fb14b9c2e9775f33bad2ea92`（9 个洗脱窗口锚点），但 `shared_assessment_identity` 为空——合同只对 `DUPLICATE_STATEMENT` 强制该身份（`protocol_control_matrix.py:759-760`），对补充关系不强制。**同一药物违规会被 EX-18 与表5 行各计一次**。
6. **“来源闭包通过”离“可发布”还差两层**：严格发布验证 `validate_protocol_control_matrix` 除 `_validate_phase` 外，还要求行单元在清单中有 disposition（`OFFICIAL_DISPOSITION_MISSING` 等，`:2377-2424`），而当前 `coverage_manifest.dispositions` 为空（0 条）；发布门禁 `protocol_control_gate._check_phase_applicability` 要求**全 1,840 单元**逐项可发布处置。152 单元证据视图只能证明“矩阵引用面”，永远不能据此把 `claims_complete` 翻真——这是伪完整声明的最大入口。

### 1. 独立复核的事实基线（我的重算，非引用检查点）

针对 152 个引用单元（155 锚点，82 行）：

| 维度 | 重算结果 |
|---|---|
| 唯一单元 | 152（全部存在于 `coverage_manifest.json`，无缺失） |
| 单元期别范围 | `unknown` 116、`phase_ii` 35、`mixed` 1 |
| 单元种类 | `list_item` 97、`table_row` 34、`paragraph` 19、`footnote_or_annotation` 2 |
| 标题簇 | 排除标准 55、表1Ⅱ期流程表行 22、方案摘要流程表列表项 19、访视安排Ⅱ期 12、表5禁止合并用药 12、入选标准 9、结核筛查 6、允许合并用药 5、其余零星 |
| 行×范围 | shared+`unknown` 56；shared+`phase_ii` 2；shared+`phase_ii,unknown` 1；shared+`mixed,unknown` 1；selected+`phase_ii` 4；selected+`phase_ii,unknown` 18 |
| 行问题 | `PHASE_UNRESOLVED` 76、`PHASE_SHARED_SOURCE_MISSING` 60，合计 136 |
| 当前干净行 | 仅 4 行（`20319f21...`、`74c39766...`、`13886b81...`、`f706d9b4...`，均 selected 且全锚点 `phase_ii`） |
| 被引用单元与 137 包关系 | 117 个 ambiguous 恰落于 **20 个包**：36,37,38,40,57,58,59,60,61,62,63,69,70,71,75,78,79,80,81,121；35 个 `phase_ii` 由 `_structurally_explicit_disposition` 确定性派生；1 个 `mixed` 无包可解（见 §4） |
| 包所有权 | 每单元恰属一个包（0 重复），137 包与 `expected_structure_unit_ids=1298` 与检查点一致 |

### 2. selected/opposite/shared/unresolved 依据视图设计

视图应是**派生工件**（建议新文件 `d001-ii-phase-evidence-view.json`，`schema_version: phase5/phase-evidence-view/v1`，恒定 `claims_complete=false`），绑定 `manifest_id + matrix_id + protocol_document_sha256`，三层责任：

**Layer A（确定性，无 Agent）**——全部可由现有合同与重算直接派生：
- 行→锚点→单元→`phase_scopes` join（每锚点记 `structure_unit_id, source_ref, source_span_ids, verbatim_excerpt`，已由闭包器回绑）；
- 结构显式派生：35 个 `phase_ii` 单元 → `selected_phase_applicable`（`_structurally_explicit_disposition` 规则，`app/protocols/phase_applicability.py:145-159`）；
- 行级 AND 语义：行状态 = 全部锚点单元状态的合取；任何锚点 `unknown/mixed/opposite` → 行阻断，**不允许部分行闭合**；
- 门禁码再生成：`PHASE_UNRESOLVED`、`PHASE_SHARED_SOURCE_MISSING`、`PHASE_MIXED_REJECTED`、`PHASE_SELECTED_SOURCE_MISSING`、`PHASE_OPPOSITE_SOURCE`；
- 时间锚点与流程阶段事实：47 行带 `time_anchors`（`first_dose_date` 43、`screening_date` 12、`baseline_date` 8、`study_completion_date` 9…），`minimum_evidence.due_workflow_stage_id`（`flow-d1-pre-dose` 44、`official-baseline` 25、`flow-screening` 7、`flow-baseline` 6）——这是区分“给药前门控”与“治疗期监测”的确定性输入；
- 上下文可用性记录：每单元所在包、包内是否含两个桥接单元（G8）。

**Layer B（真实语义，限定 117 单元/20 包）**——复用现有 `PhaseApplicability*` 合同，不新增语义合同：
- 每单元产出候选期别（`phase_ii/phase_iii/shared`，禁止 `unknown/mixed`，wire 层已硬拒：`app/agents/phase_applicability.py:1006-1007`）× 证据极性 `supports/opposes/unresolved`（`PhaseApplicabilityEvidencePolarity`）；
- `final_disposition` 四值；`unresolved` 必须带 `unresolved_reason`；
- 关键扩展：**共享正向证据的来源单元允许是章节级桥接单元**（两个 `shared` 范围单元，或 Codex 指定的共同章节声明），以证据 `source_structure_unit_ids` 形式进入包（合同允许证据引用包内任意单元，`EVIDENCE_UNIT_OUTSIDE_FROZEN_PACKAGE` 只限包内）。否则 60 行共享永远无正向来源。

**Layer C（人工裁定，Codex）**——`PhaseApplicabilityManualOverrideRecord`（`pao-*`）链：覆盖不改身份（`before_resolution_id == after_resolution_id`），链式闭合由 `_validate_manual_history` 校验。桥接语句是否足够、EX-18/表5 去重、妊娠混合行拆法，都是这一层。

**行级验证函数（视图的输出契约）**：
- `selected` 行 ⇔ 每锚点单元 ∈ {`phase_ii`, `shared`} 且无 oppose/unresolved；
- `shared` 行 ⇔ 每锚点单元有干净 `shared` 支持，且支持证据至少引用一个 `shared` 范围单元或桥接语句（新增门禁，见 G1）；
- 行声明（人工 `phase_disposition`）与验证结果不一致 → 记录 `divergence`，不得静默跟随任一方向。当前已知 ≥2 行声明-结构冲突（§0.3）。

### 3. 异质结构的区分（八类，逐一给判定）

| 结构 | 实例 | 判定路径 |
|---|---|---|
| A. 官方 IN/EX 给药前控制（无期别标签章节） | 排除标准 55 单元、入选标准 9 | 单元 `unknown` 是章节固有属性，不是语义缺失。II 期适用性由锚点类型（`first_dose_date/screening_date BEFORE`）+ 官方编码确定性支撑为 selected；**共享**主张必须另找桥接/表2同条，不能从“未限定”推出 |
| B. 方案摘要流程表列表项 | 19 单元，如 `su-c3416d49...`（妊娠试验摘要，含 W16/W52 即Ⅲ期访视） | 跨期内容混排；“未限定期别”≠共用（包69 已实证）。只能按其所注释的表1/表2行获得期别信号；无法获得 → `unresolved` |
| C. 表1Ⅱ期流程表行 | 22 个 `table_row`，`phase_ii` 结构显式 | 确定性 selected。风险在脚注 `^1..^26`：脚注单元自身范围独立（如 `su-7bd7f855...` 治疗期标题下的 D1 前基线脚注），须逐脚注核对 |
| D. 表5禁止合并用药行 | 12 行，窗口形如“首次给药前6个月至试验结束” | 窗口文本本身横跨给药前+治疗期，`cross_phase_shared` 可能是对的，但**正向依据是语义的**（“至试验结束”措辞），12 个 `table_row` 单元全 `unknown`；且必须与 EX-18 去重（G4） |
| E. 访视安排Ⅱ期 | 12 单元 `phase_ii` | 确定性 selected；其中治疗期妊娠试验单元（`su-3f17be80...`）被行 `pcm-row-18127a0d...`（stage=flow-d1-pre-dose）引用 → 治疗后污染检查点（G3） |
| F. 跨期引用/混合单元 | `su-f92576bc...` 妊娠段 | 行级硬阻断；原子化或拆行（Q3） |
| G. 结核/妊娠/避孕/病毒学时间门控 | 结核 6、妊娠/FSH 3、附录避孕 2、病毒学 2、胸部CT 1 | 必须把“资格门控”（筛选/基线/首次给药前）与“治疗期监测”分开；判定依据是 time_anchor 方向与 `due_workflow_stage_id`，**不是标题位置**（脚注反例 `su-7bd7f855...` 标题在治疗期、内容是 D1 前） |
| H. 补充关系重叠 | 表5×12 → EX-18 `supplementary_requirement` | 单一评估身份声明（G4），否则重复计数 |

### 4. 确定性 / 语义 / Codex 责任边界

- **确定性可派生（今天就能算，无需任何模型）**：§2 Layer A 全部；35 个 `phase_ii` 单元的处置；4 个干净行；2 个声明-结构冲突行的检出；20 包映射与单一所有权；`mixed` 行的发布硬拒预测；152/155 回源与逐字核验；身份稳定性（`pap/par/pac/pae` 派生规则）。
- **必须真实语义 Agent**：117 个 ambiguous 单元——但**先修复上下文**（把两个桥接单元注入 pkg 36–40/57–63/69–71/121 的 context 或由 Codex 指定等价正向来源），再跑。表5 行的“至试验结束”共享语义、共同章节（研究治疗/入选标准）是否对两期共用，都是语义问题。
- **必须 Codex 临床裁定**：(a) 桥接语句是否构成 60 行共享的正向依据（Q1）；(b) EX-18 与表5 的单一评估身份（Q2）；(c) 妊娠混合单元原子化 vs 拆行（Q3）；(d) “筛选/基线检查可重复、≤7天合并”（`su-14cbbde2...`）这类 II 期脚注能否支撑 `cross_phase_shared`（`pcm-row-c6eb8bbf...`）；(e) manifest dispositions 回填是否属于 5.8d（Q6）。
- **不得由语义 Agent 承担**：原子化（结构层，见 5.8d 混合表格根因）、行级去重策略、`claims_complete` 任何翻转。

### 5. 最小代表包（证明闭包，而非全跑 137 包）

**闭包是集合性质**：最终必须覆盖全部 20 个含引用单元的包（117 单元），但**证明门禁有效**只需覆盖全部异质风险类的最小集。提议 **11 包**（按风险类选取，非数量抽样）：

| 包 | 风险类 | 选择理由 |
|---|---|---|
| 69 | 共同章节正向证据 + “未限定≠共用” | 包69 探针已暴露三类共享问题；6 个矩阵引用单元；**无桥接上下文** |
| 70 + 71 | 表5 混合窗口语义 | 12 行表5 控制的语义核；71 还是单单元包边界 |
| 37 | 流程表摘要跨期混排 | 含妊娠/随机/结核摘要项（`su-c3416d49...` 等），升级诱惑最大；**无桥接上下文** |
| 36 | 流程表筛选项目 + ICF | 入选前控制基线类 |
| 57 | 入选标准共同章节 | 共同章节正向证据代表；**无桥接上下文** |
| 60 | EX-18 洗脱（9 锚点多单元行） | 与表5 的重复计数对照（G4） |
| 79 | 结核 + 妊娠混合 + FSH | 治疗后污染 + 混合阻断；**有桥接上下文** |
| 121 | 附录避孕（签署ICF至末次给药后3个月） | 全研究期义务；**无桥接上下文** |
| 75 + 78 | 胸部CT / 病毒学 | **有桥接上下文**的对照组 |

75/78 与 37/57/69 构成**上下文依赖性对照实验**：同类共享主张，一组能引用桥接、一组不能。若结果系统性分裂，证明必须先修复上下文（G8）；若两组同样保守（全 `unresolved`），说明桥接缺失时合同行为安全。剩余 9 包（38,40,58,59,61,62,63,80,81）在门禁被这 11 包证明后作为**闭包补全**运行——仍然只跑 20/137，其余 117 包与 82 行矩阵无关，永远不必为闭包而跑。

### 6. 验收门槛（可测试阻断）

- **G1 共享正向依据**：`cross_phase_shared` 的每个锚点单元必须有干净 `shared` 支持，且支持证据的 `source_structure_unit_ids` 至少含一个 `shared` 范围单元或指定桥接单元。测试：60 行在无桥接注入时全部失败；仅“未限定/标题邻近/方案总体名称”不得通过（对应 `_validate_effective_disposition` 的 `SHARED_UNSUPPORTED`，需增加来源范围约束）。
- **G2 mixed/unknown 硬阻断**：任何含 `mixed`/`unknown` 锚点的行不得获得可发布处置；`mixed` 另触发 `PHASE_MIXED_REJECTED`。测试：`pcm-row-b6b5156590be97880322fe9f` 必失败。建议研究层审计增加 `PHASE_MIXED_MEMBER_SPLIT_REQUIRED` 码（当前 `_phase_audit` 只归入 `PHASE_UNRESOLVED`，原子化需求不可见）。
- **G3 治疗后污染**：行 `due_workflow_stage_id`/time_anchor 属给药前集合时，锚点单元若位于治疗期/随访期标题且无 `BEFORE first_dose` 语义支撑 → `TIME_WINDOW_CONTAMINATION` 阻断。测试：`su-3f17be80...`（治疗期妊娠试验）在 `pcm-row-18127a0d...` 中必须失败或显式豁免；脚注 `su-7bd7f855...`（标题治疗期、内容 D1 前）必须能凭 time_anchor 通过——**判定必须锚点语义化，不能标题化**。
- **G4 重复计数**：同一官方父码下，`supplementary_requirement` 关联的行必须声明 `shared_assessment_identity` 或显式标记“细化不另计”；否则 `DUPLICATE_ASSESSMENT_UNDECLARED`。测试：表5×12 → EX-18 全部触发。
- **G5 跨期错误共享**：对侧期（Ⅲ）单元不得支撑 selected/shared 行（已有 `PHASE_OPPOSITE_SOURCE`）；特别核对流程表摘要中含 Ⅲ 期访视（W16/W52）的单元不得成为 Ⅱ 期行的正向依据。
- **G6 伪完整**：证据视图恒 `claims_complete=false`；任何 `accepted=true` 不得在存在未决引用单元时发出；视图不得声称发布就绪（发布要求全 1,840 单元 + manifest dispositions，见 Q6）。测试：把 4 个干净行喂给发布门禁仍应因清单级缺口失败。
- **G7 逐字回源**：全部证据摘录经空白规范化后必须是所引冻结单元的连续子串，片段 ⊆ 单元片段（`EVIDENCE_EXCERPT_NOT_VERBATIM`/`EVIDENCE_SPAN_UNIT_MISMATCH`）。
- **G8 桥接可用性审计**：每个共享判定的记录必须携带该包 `context_unit_ids` 中桥接单元的在场标志；不在场而判共享 → 强制 Codex 裁定或改 `unresolved`。

### 7. 反例清单（对应成功判据的四类事故）

| # | 反例 | 事故类型 | 门槛 |
|---|---|---|---|
| C1 | `su-c3416d49...`（妊娠试验流程表摘要，含 Ⅲ 期访视）因“未限定期别”判 `shared` | 未限定升级为共用 | G1 |
| C2 | `pcm-row-b6b5156590be97880322fe9f`：妊娠阳性筛选门控与 W16/W52（Ⅲ期）治疗期监测同单元同行 | 治疗后污染 + 跨期混排 | G2/G3 |
| C3 | 6 个月生物制剂窗口违规同时计入 `pcm-row-fb14b9c2...`（EX-18）与 `pcm-row-7d1c9444...`（表5） | 重复计数 | G4 |
| C4 | 表5 行窗口“首次给药前…至试验结束”被语义包判为仅 `phase_ii`，或把 Ⅲ 期流程表单元当 Ⅱ 期依据 | 跨期方向错误 | G5 |
| C5 | 以“155/155 回源、`source_closure.accepted=true`”宣称闭包完成，忽略 136 期别问题、`dispositions=0`、全清单发布要求 | 伪完整声明 | G6 |
| C6 | `pcm-row-c6eb8bbf...`/`pcm-row-689838943c7e4a51c5345e67` 保持 `cross_phase_shared` 而全部锚点是 `phase_ii` | 声明-结构冲突被语义结果洗白 | G1 + 行声明-验证 divergence 字段 |
| C7 | pkg79 判共享（有桥接上下文）而 pkg69/70 判 unresolved（无桥接），被解读为临床差异 | 上下文可用性伪影 | G8 |
| C8 | 35 个多锚点行（最多 9 锚点）中用任一 `phase_ii` 锚点放行整行，掩盖同排 `unknown` 锚点 | 部分行闭合 | 行级 AND（§2 Layer A） |

## Evidence And Assumptions

**证据（均可复核）**
- 行/单元/范围计数与 20 包映射：对 `d001-ii-control-matrix-closed.json`、`d001-ii-control-matrix-closure-report.json`、`coverage_manifest.json`、`slice58i-v2-plan/execution/...slice58i-v2.json` 的现场重算（§1），与 `plans/` 中“152/116/35/1、60/22”声明一致；“仅 4 干净行”“shared 范围全清单仅 2 个且不在引用集”“桥接仅存于 pkg75–81 上下文”“单元单一包所有权”为本次新增事实。
- 门禁语义：`app/protocols/phase_applicability.py:145-159,386-461,491-613`；`app/domain/contracts/protocol_control_matrix.py:2010-2051,2028-2029,2079-2095,2377-2424`；`app/protocols/protocol_control_gate.py:160-235`；`app/domain/contracts/phase_applicability.py:48-62,240-318,378-397`。
- “未限定≠共用”政策已入提示合同：`app/agents/phase_applicability.py:1389-1393,1424-1426,1590-1591`；wire 层禁 `unknown/mixed` 候选：`:1006-1007`。
- 混合表格根因先例：`CHECKPOINT_20260825_MIXED_TABLE_ATOMIZATION_INTERRUPTED.md`（批次32 把 Ⅱ/Ⅲ 成员错误归为共用）。
- 回归：`test_matrix_source_closure.py` 4 passed（含 `phase_closure.accepted is False`、`full_claims_complete_allowed is False`、`claims_complete is False` 断言）。

**假设（[INFERENCE] 处已标）**
- 两个 `*-closed.json` 是当前权威输入（检查点声明）；`frozen_phase_plan.json` 仍是 217 包 v1 身份，137 包以 `slice58i-v2` 执行文件为准（其 `batch_count=137` 与检查点一致）。
- [INFERENCE] 桥接单元注入 context 不需要重冻结清单（只改包构建输入，`package_id` 会变，身份随之重派生）；若 Codex 认为 `package_id` 稳定性优先，则改走 Codex 裁定路径。
- 未读源 DOCX；所有原文判断基于冻结逐字摘录（边界允许）。
- `manifest_dispositions=0` 意味着当前闭包矩阵**不能**通过 `validate_protocol_control_matrix` 的发布验证 [INFERENCE：未实际调用该函数跑矩阵，仅依代码路径与字段事实推断]。

## Risks, Gaps, And Verification Needs

1. **语义结果的上下文伪影是当前最大系统性风险**（C7/G8）：不修桥接可用性就跑 20 包，得到的差异不可归因于临床，会污染后续人工裁定。验证方式：11 包最小集本身即为对照实验。
2. **妊娠混合行无合法语义路径**：现合同下任何包对它产出结果都会被发布层拒绝或误导；必须先原子化/拆行（Codex 决定 Q3）。在其解决前，证据视图应把 `pcm-row-b6b5156590be97880322fe9f` 标为 `blocked_structural`，不是 `unresolved_semantic`。
3. **行声明与验证结果的双向风险**：人工 60/22 处置是待核对主张；视图若默认跟随人工标注会洗白 C6 冲突，若默认否定会浪费已确定性闭合的 4 行与 35 个结构显式单元。设计已用 `claim_disposition` vs `verified_disposition` + `divergence` 双向记录规避。
4. **重复计数未被任何现有门禁覆盖**（G4 是新增）；合同仅对 `DUPLICATE_STATEMENT` 要求 `shared_assessment_identity`。
5. **发布链路缺口超出 5.8d 表述**：全清单处置 + manifest dispositions（Q6）。若不在本轮声明范围，必须在检查点中显式记录为“已知未完成”，否则 4 干净行会被误读为“可发布子集”。
6. 需要 Codex 验证的后续：桥接注入后重跑 11 包；混合单元原子化的结构验收；`validate_protocol_control_matrix` 对当前 closed 矩阵的实际失败清单（由 Codex 或有写权限的执行者运行）；5.8e 上对同构门槛的泛化抽查。

## Recommended Next Step

Codex 按序裁定后执行（全部在现有合同内，无新语义合同）：

1. **先答 Q1（桥接语句是否构成共享正向依据）**——它决定 60 行是否有机械可走路径；未答前，一切共享主张按“不足”处理（安全侧）。
2. 由有写权限的执行者生成 `d001-ii-phase-evidence-view.json`（§2 三层），先把 Layer A 确定性部分落盘：35 单元结构派生、4 干净行、2 冲突行、1 混合阻断行、136 问题再生成、20 包映射与桥接在场标志。此步零模型调用，可立即证伪/证实本报告全部确定性结论。
3. 修复上下文（桥接注入或等价裁定）后，按 §5 跑 11 包最小集，执行 G1–G8；用 75/78 vs 37/57/69 的对照结果决定是否放行其余 9 包。
4. 妊娠混合单元走 Q3 决定（原子化或拆行），期间该行保持 `blocked_structural`。
5. 全程保持 `claims_complete=false`；117/137 包之外永不运行；最终医学验收与 5.8d 关闭由 Codex 独占。

**给 Codex 的限定问题**
- **Q1** `su-34232d16...`/`su-f53dd8ce...` 是否接受为共同章节（研究治疗、入选/排除、检查评估）的共享正向依据？是 → 注入 pkg36–40/57–63/69–71/121 context 后重跑；否 → 60 行逐章人工裁定。安全暂定：不足。
- **Q2** 表5 十二行是 EX-18 的规范细化（单一评估）还是独立控制？安全暂定：单一评估，违规只计一次。
- **Q3** 妊娠混合单元：结构原子化，还是把 `pcm-row-b6b5156590be97880322fe9f` 拆为“资格门控行（selected）+ 治疗期监测行（不入 Ⅱ 期矩阵）”？两者都需要写操作；语义包不得先跑。
- **Q4** 是否授权把证据视图作为新研究工件落盘（schema 如 §2）？
- **Q5** 11 包最小集是否照单执行？包 69 用修订后 v2 提示重跑还是复用 `slice58h-v2-plan/merged-package69-probe/post-fix2-result.json` 作基线？
- **Q6** manifest dispositions 回填与全清单 1,840 单元发布要求是否属 5.8d 范围？（决定“矩阵可发布”是否被期别闭包之外的条件阻断。）

（本输出为完整会议产物；未做最终医学验收，慢速补全点：无——证据、门槛与问题清单已闭合。）
