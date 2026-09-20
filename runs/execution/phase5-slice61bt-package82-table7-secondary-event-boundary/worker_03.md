Fallback state: running as `codebuddy-cli/deepseek-v4-flash` (declared same-platform fallback for `codebuddy-cli/glm-5.3-flash`). Delegated mode in effect. Starting by reading the initial read set.

Worker_03 confirmed. My assigned work item: **从条件反转、表格行列错配、t7/t12混同和跨包吞并角度做独立反例挑战** (independent counterexample challenge). The execution context notes "Source Of Truth: TODO — Codex must add authoritative source files". I need to locate the actual source material (freeze plan, coverage lists, structure blocks, DOCX-derived structures) in the workspace before I can challenge.

Let me explore the relevant directories.

Prior sibling tasks (79/80/81 packages) exist. Let me read the sibling reviews to understand the pattern, and find where the freeze plan data lives.

The sibling review confirms: 第82包 owns 表7正文 = `body.t12.r0-r4`; t12 is the structure-block index of DOCX 表7. Let me read the sibling worker_03 reports to replicate the accepted challenge pattern.

The sibling worker_03 report gives me the full pattern. Now let me locate the package-82 written contract and frozen plan data.

The written package-82 contract exists. Reading it now.

Contract confirmed. Now extracting package-82 ownership, context units, and verbatim `t12` rows from the frozen plan, coverage manifest, and structure block.

Package 82 owns exactly `body.t12.r0-r4` (5 units, 4 columns: 序列|继发事件的类型|示例|应记录的AE). Now extracting context units, sibling package ownership, and verifying against the structure block.

Notable: pkg82 frozen context includes `body.t7.r0` (phase-III efficacy table header) and `body.p1032` (表7 caption) — but NOT `p1030`/`p1031`, which the contract requires as prior read-only context. Now the verbatim structure block.

t12 confirmed 5×4; t7 confirmed 5×3 (efficacy intercurrent-events). Now the full verbatim t12 corpus plus neighboring paragraphs p1030-p1033.

Verbatim corpus established. The r3.c1 cell "在时间上**从与**初始事件中分离出来的…" looks suspicious — must verify against the original DOCX, along with the caption/table-numbering relationship (t12 physical vs 表7 caption) and the r3 cell wording.

Caption = `表 ` + SEQ field (`\* ARABIC`) + text — the "7" is auto-rendered. Now counting physical table position and extracting the table's verbatim cells from the DOCX.

Key finding: the caption's table is the 14th raw `<w:tbl>` — the structure-block ordinal t12 differs from raw table order. Verifying the structure block's own table sequencing and the rendered caption number of t7 (the 7th table).

Structure block confirmed: `p1032` (caption, block 2798) → `body.t12` (2799) adjacency; `t7` is a different table. DOCX cell[13] shows "在时间上**从与**初始事件中分离出来的…" — verbatim in source, not an artifact. Now confirming rendered caption numbers via SEQ count, plus coverage manifest and sibling package ownership.

SEQ captions confirmed: 表7 → the secondary-events table (t12); 表8 (AE严重程度分级) and 表9 (AE因果关系) follow in later packages. Now checking t7's own caption (before block 2179) and the coverage manifest + sibling package ownership.

Ownership map verified. Now checking the official flow-controls matrix anchors and the package-81 config/test patterns (sanctioned pattern reference).

Matrix: 58 rows, `claims_complete=false`, zero anchors in the pkg82 span — baseline holds. Now the sanctioned pkg81 config/test pattern.

Config schema captured. Now the pkg81 test pattern for negative-regression vocabulary.

All evidence gathered. One last quick check of the pkg81 config's `batching`/`ids`/`phase_applicability` fields to complete the pattern reference.

All evidence gathered and verified. Compiling the counterexample challenge report.

---

# Execution Output: phase5-slice61bt-package82-table7-secondary-event-boundary - worker_03

## Boundary And Context Check

- **Fallback statement**: I am executing as the declared `codebuddy` fallback `codebuddy-cli/deepseek-v4-flash` (primary role was declared `codebuddy-cli/glm-5.3-flash` but was unavailable before a resumable session existed). Same bounded role, initial read set, output path (`runs/execution/phase5-slice61bt-package82-table7-secondary-event-boundary/worker_03.md`), quality gates, and conference-pass protocol. Capability note: analysis is read-only; I performed no code writes, no test runs, no model invocation, no publication — exactly per the work item.
- **Assigned work item** (worker_03): 独立反例挑战 — read-only attack on 条件反转/反事实条件、表格行列错配、t7/t12混同、跨包吞并 (plus 例外强度 per the written contract's work item 3), with executable acceptance recommendations in the established config/test vocabulary. No edits authorized or made.
- **Initial read set read**: `context/phase5-slice61bt-package82-table7-secondary-event-boundary_execution_context.md`, `plans/codex_execution_phase5-slice61bt-package82-table7-secondary-event-boundary.md`.
- **Additional context required and obtained** (the module shell's "Source Of Truth" was TODO; the contract, frozen plan, structure block, DOCX, and sibling-package pattern are referenced but not embedded):
  - The written package-82 contract: `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice61bt-package82-table7-secondary-event-execution-contract.md`
  - Frozen plan + coverage manifest + structure block: `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/{frozen_phase_plan.json,coverage_manifest.json,structure/blobs/protocol_blocks/3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json}`
  - Original DOCX: `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/source-input/blobs/protocol_sources/362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98.docx` (unzipped to `/tmp/p82_docx_check`, disposable)
  - Pattern reference (sanctioned by contract §权威来源 5): pkg81 accepted config `configs/representative_group_package81_ae_diagnosis_secondary_event_boundary.v1.json` and test `test_slice61bs_package81_ae_diagnosis_secondary_event_boundary.py`; official matrix `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-official-flow-controls.json`
  - Peer worker reports of THIS task (`runs/.../worker_01.md`, `worker_02.md`) were **not** read (no peer review per execution rules). Note: pkg82 config/test do not yet exist in `configs/` or the test directory — the challenge is therefore forward-looking against the contract, mirroring the accepted pkg81 pattern.
- **Ground truth established** (all verbatim, cross-checked DOCX ⇄ structure block ⇄ frozen plan ⇄ coverage manifest):
  - Package 82 = ordinal 82, id `pap-2979ce0b01f057b9f4f0de11`, `selected_phase=phase_ii`, owns exactly 5 units: `body.t12.r0`–`r4`. `r0` is the table header (structural only per contract).
  - Table geometry: **5 rows × 4 columns** — 序列 | 继发事件的类型 | 示例 | 应记录的AE. Every row has exactly 4 cells; `c2` (示例) of rows r2 and r3 each contain **two paragraphs** (two examples per row).
  - Verbatim cell text (structure block == DOCX, verified cell-by-cell):
    - `r1`: `1 | 轻度/中度/非严重/无需干预治疗的 | 如果呕吐（事件A）导致健康成人轻度脱水（事件B），无需额外治疗，在eCRF上应仅报告呕吐。 | 事件A`
    - `r2`: `2 | 重度或严重继发性事件 | [p0] 如果呕吐（事件A）导致严重脱水（事件B），则应在eCRF上分别单独报告这两个事件。 [p1] 如果重度胃肠道出血（事件A）导致肾衰竭（事件B），两个事件均应在eCRF上单独报告。 | 事件A、事件B`
    - `r3`: `3 | 在时间上从与初始事件中分离出来的具有重要医学意义的次级不良事件 | [p0] 如果头晕（事件A）导致跌倒（事件B1）和继发性骨折（事件B2），所有三个事件均应在eCRF上单独报告。 [p1] 如果中性粒细胞减少（事件A）伴发感染（事件B），两个事件均应在eCRF上单独报告。 | 事件A、事件B`
    - `r4`: `4 | 无法确定的 | 如果不清楚事件之间是否有关联，应在eCRF上单独记录所有不良事件。 | 事件A、事件B`
  - `r3.c1` wording **"在时间上从与初始事件中分离出来的具有重要医学意义的次级不良事件"** is verbatim in the DOCX (cell[13]) — the odd "从与" sequence is source-faithful, not an OCR artifact. The contract's shorthand "在时间上分离" is a paraphrase; config must use verbatim text.
  - Caption binding: `p1032` (block_order 2798, "表 7 应记录的继发于其它事件的不良事件") directly precedes `body.t12` (block_order 2799). In the DOCX, the caption is `表 ` + **SEQ field** (`<w:instrText> \* ARABIC </w:instrText>`) — "7" is render-time auto-numbered, not literal. SEQ counter sequence in document: 表1 Ⅱ期流程表, 表3 试验用药品信息, 表4 给药方案, 表5 禁止合并用药, 表6 实验室检查, **表7 继发事件**, 表8 AE严重程度分级, 表9 AE因果关系.
  - Physical positions: document.xml has 25 `<w:tbl>` (24 top-level `body.t0`–`t23` + 1 nested `t4.r9.c1.t0`). The caption's table is the 14th raw `<w:tbl>` / 13th top-level table → structure-block namespace `body.t12` is the authoritative id.
  - `t7` (block_order 2179, follows `p507` "伴发事件及处理策略：" — **no "表X" caption**) is 5 rows × 3 cols (伴发事件 | 处理策略 | 备注), phase-III efficacy intercurrent-events content (PASI75应答、复合策略/疗法策略) — a **different table from 表7**.
  - Ownership map (frozen plan): pkg79 `p1007`–`p1014`; pkg80 `p1015`–`p1026`; pkg81 `p1027`–`p1032`; **pkg82 `t12.r0`–`r4`**; pkg83 `p1033`–`p1042`; pkg84 `p1043`–`p1054`; pkg85 `p1055`–`p1066`.
  - Coverage manifest: `p1030`@1342, `p1031`@1343, `p1032`@1344, `t12.r0`@1345, `r1`@1346, `r2`@1347, `r3`@1348, `r4`@1349, `p1033`@1350.
  - Official matrix `d001-ii-official-flow-controls.json`: 58 rows, `claims_complete=false`, **zero anchors** in `p1025`–`p1054` / `t12` / `t7` (zero baseline holds for pkg82's span).
  - pkg82 frozen `context_units` (39 units): includes `body.p1032` (caption) and **`body.t7.r0`** (phase-iii efficacy header, `phase_scopes=['phase_iii']`) but **NOT** `p1030`/`p1031` (contract §边界: "第 81 包 body.p1030-p1032 必须作为前接只读语境") and **NOT** `p1033` (contract: "第 83 包 body.p1033 必须作为表内 A/B 记号说明"). All t12 units carry `phase_scopes=['unknown']`.

## Work Performed

Read-only counterexample challenge across the five mandated attack surfaces. For each: source anchor → attack vector (counterexample) → why it is a defect → executable acceptance condition (config/test vocabulary per the accepted pkg81 pattern: `owned_source_refs`, `structural_only_source_refs`, `expected_disposition_by_source_ref`, `exception_semantics_by_source_ref` with `semantic_role/base_rule/exception_rule/preserve_keywords/forbidden_inversion`, `candidate_forbidden_markers_by_source_ref`, `later_package_boundary.expected_owners_by_span`, `forbidden_candidate_source_refs`, `required_candidate_source_refs=[]`, zero `official_rules`).

### 1. 条件反转（含反事实条件与例外强度）— 四行条件分支不得压平或反转

- **CE-1a r1 条件成分反转/丢失**（`t12.r1.c1` = "轻度/中度/非严重/无需干预治疗的"）：四修饰语为 **OR 型并列**（轻度或中度或非严重或无需干预治疗）。攻击形态：(i) 写成 AND（"既轻度又中度…"，语义不可满足，规则失效）；(ii) 删除任一修饰语（如删"无需干预治疗"）后把"仅报告事件A"外推到所有轻度/中度继发事件 —— 合同明令"不得外推到所有继发事件"；(iii) 把"仅报告事件A"反转成"分别报告 A、B"（结果列反转，与 `r1.c3='事件A'` 冲突）。
- **CE-1b r1 示例限定丢失**（`t12.r1.c2`）：示例含"健康成人轻度脱水…**无需额外治疗**"——"无需额外治疗"是行条件与示例的联结限定；攻击形态是删除"无需额外治疗"，使规则脱离治疗需要判定。
- **CE-1c r2 例外强度抬升为通用病种门槛**（`t12.r2.c1` = "重度或严重继发性事件"，`c2` 两示例）：合同明令"示例不是新增的通用病种门槛"。攻击形态：(i) 把"重度胃肠道出血→肾衰竭"或"呕吐→严重脱水"升格为"凡重度X必分别报告"的通用病种规则；(ii) 删"继发性"限定，使"重度或严重事件"脱离"继发"因果关系语境（A导致B），变成对任何重度事件生效；(iii) 把"严重"与**SAE 严重性判定**（严重不良事件定义，第78包域）混同——本表"严重"指继发事件严重程度，不是 SAE 严重性门槛。
- **CE-1d r3 合取条件弱化**（`t12.r3.c1` = "在时间上**从与**初始事件中分离出来的**具有重要医学意义**的次级不良事件"）：合同明令"保留'在时间上分离'与'具有重要医学意义'的合取限定；不得只凭先后发生即拆分"。攻击形态：(i) 只凭时间先后（前因后果）即拆分——丢弃"具有重要医学意义"；(ii) 弱化为析取（时间分离**或**重要医学意义任一条即可）；(iii) 用 B1/B2 示例（头晕→跌倒→继发性骨折）推导"级联事件一律分别报告"——级联事件是 `p1031`（第81包）的引导示例，不是本行独立条件。
- **CE-1e r4 触发条件偷换**（`t12.r4.c1` = "无法确定的"，`c2` = "如果不清楚事件之间是否有关联"）：触发条件是**事件之间关系无法确定**。攻击形态：(i) 写成"证据不足/证据缺口"（记录不完整 ≠ 关系无法确定，违反项目"不collapse gap reason"原则）；(ii) 写成"入排待补证"或"筛选/基线必做"（合同明令禁止）；(iii) 把"关系无法确定"偷换成"严重程度无法确定"或"诊断无法明确"（后者是 `p1029` 第81包域）；(iv) 结果反转："无法确定时合并记录"（与 `c3='事件A、事件B'` 冲突）；(v) 路由到给药前病史/伴随疾病（`p1023` 第80包域）。
- **验收建议**: 每行 `exception_semantics_by_source_ref` 的 `base_rule` 用**逐字**单元格文本（含 r1 尾"的"、r3 的"从与"、r4 尾"的"），`preserve_keywords` 逐行覆盖条件词（r1: ["轻度","中度","非严重","无需干预治疗","仅报告呕吐","事件A"]；r2: ["重度或严重继发性事件","分别单独报告","事件A、事件B"]；r3: ["在时间上","分离","具有重要医学意义","次级不良事件","单独报告"]；r4: ["无法确定的","不清楚事件之间是否有关联","单独记录所有不良事件"]），`forbidden_inversion` 覆盖 CE-1a..1e（OR不AND化、不删修饰语、不删"无需额外治疗"、示例不升格门槛、"严重"不与SAE判定混同、r3合取不弱化、r4不写成证据不足/入排待补证、结果列不反转）。

### 2. 表格行列错配 — 5×4 几何与单元格归属不得拆散

- **CE-2a 列串行错配**（表头 `t12.r0` = 序列|继发事件的类型|示例|应记录的AE）：准备/序列化若按行拼接不按列分隔，示例（c2）文本会混入类型（c1）或应记录的AE（c3）。攻击形态：把 r2 的示例句"如果呕吐…分别单独报告"截为类型列内容，使"分别单独报告"被误读为行条件。
- **CE-2b 行移位（最危险的单点错配）**：`r1.c3='事件A'` 是四行中**唯一**"仅报告A"的结果列，`r2`/`r3`/`r4` 的 `c3` 均为"事件A、事件B"。若行错位（r1.c3↔r2.c3 互换或整体偏移一行），规则整体反转：r1 变成"分别报告"、r2 变成"仅报告A"。负向回归必须逐行断言 c3 归属。
- **CE-2c 表头行处置**（`t12.r0`）：合同明令 r0 仅作结构。攻击形态：(i) 把 r0 当规则行发射候选（"序列|继发事件的类型|…"成为伪规则）；(ii) 把 r0 从准备证据中删除，使列名丢失、四列语义不可读。验收：`structural_only_source_refs == ["body.t12.r0"]`，r0 不进入 `expected_disposition_by_source_ref` 语义处置。
- **CE-2d 多段落单元格拆分**（`t12.r2.c2.p0+p1`、`t12.r3.c2.p0+p1`）：每行示例是两个段落（两个并列示例）。攻击形态：把 p1 拆成独立行（伪造 r2a/r2b），或丢弃 p1 只留 p0（示例截断，尤其 r2 丢失"重度胃肠道出血→肾衰竭"例、r3 丢失"中性粒细胞减少伴发感染"例）。验收：准备证据中 r2/r3 的 excerpt 必须完整包含 p0+p1 两段且归属同一行。
- **CE-2e 单元格完整性**：已核实 DOCX 该表恰 20 个 `<w:tc>`（5×4），无合并单元格、无嵌套表（对比文档中存在 `t4.r9.c1.t0` 嵌套表，t12 无此风险）。验收：断言 5×4 几何与 20 单元格一致，任何行/列数漂移即失败。
- **验收建议**: 准备证据按 `rX.cY.pZ` 保序输出，excerpt 以列分隔符区分四列；专项负向回归复用 pkg81 测试的 excerpt/verbatim 断言风格（`test_owned_unit_excerpts_verbatim`），并新增"r1.c3=='事件A' 且 r2..r4.c3=='事件A、事件B'"的行归属断言。

### 3. t7/t12 混同 — 表7(caption) 必须绑定 t12，不得绑定 t7

- **CE-3a 表号撞车**: 渲染题注"表 7"（`p1032`，SEQ 域渲染值）对应的结构块是 `body.t12`（block_order 2799）；而 `body.t7`（block_order 2179，无"表X"题注，3 列 伴发事件|处理策略|备注）是 **Ⅲ期疗效"伴发事件及处理策略"表**（PASI75、复合策略/疗法策略、ICH E9(R1) intercurrent-events 语义），与 `p1031`"具体示例见表7"引用的表**不是同一张**。攻击形态：模型/配置看到"表7"即按 `t7` 查找，把疗效 intercurrent-events 语义注入 AE 继发事件记录规则（把"伴发事件处理策略"当成继发事件上报规则）。
- **CE-3b 冻结上下文已含 t7**: pkg82 的 frozen `context_units` 含 `body.t7.r0`（`phase_scopes=['phase_iii']`，表头"伴发事件|处理策略|备注"）。若准备阶段把它作为"表7相关上下文"直传，混淆风险成为真实注入面。验收：`attached_source_refs` 中若保留 `t7.r0` 必须在注记中标明"Ⅲ期疗效域 intercurrent-events 表，非表7，与继发事件记录语义无涉"；更优：从 pkg82 提示中剔除 t7.r0（它不属于本包闭包所需）。
- **CE-3c 编号来源混用**: "7"是 SEQ 渲染值，物理位置随计数口径不同（raw `<w:tbl>` 第14个 / 顶层第13个 / 结构命名 `t12`）。验收：一切断言以结构块 `body.t12` 命名空间为准，不得按 raw DOCX 物理序做数字断言。
- **CE-3d 题注域**: 后续 SEQ 渲染"表 8 AE严重程度分级""表 9 AE因果关系"分别对应更后包内容（严重程度分级 → pkg83+ 域，因果关系 → pkg90 域）；表号连续编号不得与"包号"混淆。`p1032` 题注本身属 pkg81（结构标题），pkg82 只作前接只读语境引用。
- **验收建议**: config/清单显式标注"表7 := body.t12（p1032 题注绑定）"；`later_package_boundary.note` 记录 t7≠表7；负向回归断言 t7 单元格（如"复合策略""PASI75"）不出现在 pkg82 任何拥有/发射/准备 excerpt 中。

### 4. 跨包吞并 — 只拥有 t12.r0-r4，其余只读且不发射

- **CE-4a 前接只读缺口（反向吞并风险的另一面）**: 合同要求 `p1030-p1032` 作为前接只读语境、`p1033` 作为表内 A/B 记号说明，但冻结计划的 pkg82 context **缺 `p1030`、`p1031`、`p1033`**。若 worker_02 只按冻结 context 准备提示，表四行将脱离 `p1031`"根据主要原因确定是否独立"的统领句和 `p1033` 的 A/B 记号，模型只能用常识补全（pkg81 已发生的同类缺陷，父级已修复并要求"直接引用正文必须进入只读提示"）。验收：准备证据必须显式包含 `p1031`、`p1032`、`p1033`（`p1030` 为标题，视需）；三者角色为 attached/只读，**不得进入 `owned_source_refs`**。
- **CE-4b p1031 决策规则回流**: `p1031`（第81包）的"根据其主要原因确定是否应记录为独立不良事件"是表的统领决策。攻击形态：pkg82 config 把"是否独立"的决策规则抄入表行规则（如表行 base_rule 以"根据主要原因判断"开头）——即上游吞并 pkg81；或相反，表行 emit 后 pkg81 又凭表行补写四类规则（pkg81 已验收为不得补写）。验收：pkg82 四行 base_rule 均以**表单元格原文**为唯一规则文本，不重述 p1031 决策句。
- **CE-4c p1029 实验室值通道混同**: `p1029`（第81包）"无法诊断时记录症状/体征**或实验室异常值本身**"与 pkg83 `p1039-p1042`（实验室异常**必须**报告为AE）是孪生义务。表四行的 r4"无法确定"通道不得与 p1029 的无法诊断通道、或 pkg83 的实验室异常必报标准互相改写。验收：r4 的 forbidden_inversion 显式排除"实验室异常值""无法明确诊断"措辞；p1034-p1042 仅在确有防混同必要时进入只读（合同授权），所有权恒为 pkg83。
- **CE-4d 表注 p1033 吞并**: `p1033`"注：以上示例将初始事件记为事件A，继发事件记为事件B"是表内记号说明，与表的 `应记录的AE` 列（A/B 记号）语义交织，但所有权归 pkg83。攻击形态：因 A/B 记号依赖而把 p1033 划入 owned 或允许其发射。验收：`expected_owners_by_span` 中 `body.p1033` → 83；pkg82 只读引用，`forbidden_candidate_source_refs` 不含 p1033（它是上下文，不是候选源——参照 pkg81 对 t12 的处理：上下文永不发射断言）。
- **CE-4e p1026/p1028 边界回流**: p80 `p1026`（单一事件项一个术语）与 p81 `p1028`（诊断术语优先/合并条件）不进入表行规则（表行是"记录什么AE"的类别规则，不重述术语/合并原则）。攻击形态：r1"仅报告事件A"被解释为"合并成一个事件"并借用 p1028 合并条件——"仅报告事件A"是上报类别选择，不是术语合并。
- **CE-4f 后向包只读元数据**: `p1043-p1054`（pkg84 生命体征异常/既存疾病）、`p1055+`（pkg85 特殊肝功能SAE）、`p1098+`（pkg92 SAE报告时限）只保留所有权元数据，不入提示。
- **验收建议**: `owned_source_refs` **恰为** `["body.t12.r0","body.t12.r1","body.t12.r2","body.t12.r3","body.t12.r4"]`；`later_package_boundary.expected_owners_by_span` = {t12.r0..r4→82, p1033..p1042→83, p1043..p1054→84, p1027..p1032→81}；`required_candidate_source_refs==[]`；`forbidden_candidate_source_refs` 覆盖五个拥有单元；负向回归：任何 owned 之外 span 不发射候选（复用 pkg81 `UNOWNED_CONTEXT_REFS` 只读断言模式）。

### 汇总接受门槛（可执行）

1. 五拥有单元逐项且仅处置一次；`owned_source_refs == [body.t12.r0 … body.t12.r4]`；`t12.r0` 仅结构归属，`t12.r1-r4` 保持 `post_treatment_execution`。
2. 四行条件-结果逐字保留且按行绑定：r1 仅"事件A"（OR 修饰语不 AND 化、不删"无需额外治疗"、不外推）；r2 重度或严重继发事件分别报告（示例不升格门槛、"严重"≠SAE判定）；r3 时间分离∧重要医学意义合取（不只凭先后拆分）；r4 关系无法确定才全部单独记录（不写成证据不足/入排待补证、结果不反转）。
3. 表几何 5×4、单元格 20、r2/r3 示例双段落完整、c3 行归属断言（r1="事件A" vs r2-r4="事件A、事件B"）。
4. 表7 := t12（p1032 题注 SEQ 绑定）；t7 不得充当表7，`t7.r0` 上下文须注记Ⅲ期疗效域或剔除；断言不出现"复合策略/PASI75"等 t7 语义。
5. 准备证据含 `p1031`/`p1032`/`p1033` 只读前接；`expected_owners_by_span` 正确；任何 owned 之外 span 零候选。
6. 官方矩阵零行锚定 t12 跨度、`official_rules==[]`、`claims_complete=false`、无预筛/筛选/基线门槛措辞、无 IN/EX 合成。
7. 不补写删除/历史机制/日期算法/严重程度推断等产品机制（合同明令）。

## Artifacts And Evidence

No files created or modified (read-only work item). Evidence objects read (all inside authorized workspace):

| Evidence | Role |
|---|---|
| `context/phase5-slice61bt-..._execution_context.md`, `plans/codex_execution_phase5-slice61bt-....md` | initial read set |
| `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice61bt-package82-table7-secondary-event-execution-contract.md` | written package-82 contract (目标/权威来源/边界/工作项) |
| `.../frozen_phase_plan.json` | pkg82 (ordinal 82, `pap-2979ce0b01f057b9f4f0de11`) owned=5 (t12.r0-r4); pkg79-85 ownership map; pkg82 context 39 units incl. `t7.r0` + `p1032`, missing p1030/p1031/p1033; t12 units `phase_scopes=['unknown']` |
| `.../coverage_manifest.json` | p1030@1342 … t12.r0@1345 … t12.r4@1349, p1033@1350 |
| `.../structure/blobs/protocol_blocks/3946ea2c….json` | verbatim t12 cells (20), t7 cells, p1030-p1033; caption→t12 adjacency (block 2798→2799); t7 follows p507 伴发事件及处理策略 |
| `.../source-input/blobs/protocol_sources/362443131f0d…docx` (word/document.xml) | 25 `<w:tbl>`; caption = "表 "+SEQ field renders 7; SEQ sequence 表1..表9; the caption's table = 14th raw tbl; verbatim cells match structure block incl. r3.c1 "从与初始事件中分离出来…"; r1.c1 尾"的"、r4.c1 尾"的" 在原文 |
| `.trellis/tasks/.../d001-ii-official-flow-controls.json` | 58 rows, `claims_complete=false`, zero anchors p1025-p1054/t12/t7 |
| `.../configs/representative_group_package81_ae_diagnosis_secondary_event_boundary.v1.json` | sanctioned config schema (owned/structural/disposition/exception_semantics/later_package_boundary/batching/ids) |
| `.../test_slice61bs_package81_ae_diagnosis_secondary_event_boundary.py` | sanctioned test vocabulary (verbatim excerpts, later-boundary counts, UNOWNED_CONTEXT_REFS, forbidden markers, zero matrix anchors) |

Key numbers for the pkg82 test contract (consistent with pkg81 test): DOCX SHA-256 `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`; structure SHA-256 `3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`; plan id `papl-40b1237a22e538a278b4fd5e` (per pkg81 report; plan SHA-256 `f0aa7e4bccad782ad5472c1f446f079e26343f694ad3ddca401bfbef89f38250`).

## Commands And Observations

| Tool | Target | Observation |
|---|---|---|
| Glob/Grep | worktree `.trellis/tasks/**`, `第82包\|t12\|表7` | located written contract under `research/d001-ii-phase-closure/`; pkg82 config/test not yet created (worker_02 scope) |
| Read | initial read set (2 files) | module shell only; contract not embedded (Source Of Truth was TODO) |
| Read | written package-82 contract | boundaries confirmed: owned=t12.r0-r4 only; r0 structural; p1030-p1032/p1033 as prior/read-only context; 4 rows are condition branches; t7≠表7; no product mechanisms |
| Bash python | frozen_phase_plan.json | pkg82 owned=5 (t12.r0-r4); pkg79-85 ownership map; pkg82 context 39 units: p1032 present, p1030/p1031/p1033 **absent**, t7.r0 present, t12 `phase_scopes=['unknown']` |
| Bash python | coverage_manifest.json | t12.r0@1345..r4@1349, p1033@1350 |
| Bash python | structure blob | verbatim t12 5×4 cells; t7 5×3 (Ⅲ期疗效伴发事件); caption p1032→t12 adjacency (block 2798→2799); t7 follows p507 伴发事件及处理策略 (no caption) |
| Bash unzip+python | original DOCX document.xml | 25 `<w:tbl>` (24 top-level + 1 nested); caption = "表 "+SEQ `\* ARABIC` (renders 7); SEQ sequence 表1-表9 (表7=继发事件); caption's table = 14th raw tbl; t12 cell texts match structure block verbatim (incl. r3.c1 "从与"、r1/r4 尾"的") |
| Bash python | official-flow-controls.json | 58 rows, `claims_complete=false`, zero anchors in p1025..p1054/t12/t7 |
| Read | pkg81 config + test (pattern, sanctioned) | config schema and test vocabulary for executable acceptance recommendations |

No commands modified any repository file. Temporary extraction artifacts were created under `/tmp/p82_docx_check` (outside repo, disposable).

## Blockers Or Missing Environment

- None blocking. No environment or tool missing; all verification was performed with Python stdlib (`json`, `re`) and `unzip`.
- **Residual items for Codex (not blockers)**:
  1. **冻结上下文缺口（closure defect）**: pkg82 frozen `context_units` 缺合同强制的前接语境 `p1030`/`p1031`/`p1033`（仅含 `p1032`）。worker_02 准备阶段必须超出冻结列表补齐这三项为只读 attached（pkg81 已修复同类"直接引用正文必须进入只读提示"缺陷，父级复核确认）。请 Codex 确认补齐范围（是否连带 p1034-p1042 按"确有防混同必要时"条款）。
  2. **`t7.r0` 上下文处置**: pkg82 冻结 context 含 `body.t7.r0`（Ⅲ期疗效 intercurrent-events 表头）。建议从 pkg82 提示剔除或强制注记"非表7"；请 Codex 确认（若为冻结计划打包伪影，worker_01 应记录）。
  3. **`phase_scopes=['unknown']`**: 表7 四行的期别归属未解析。pkg82 config 的 `phase_applicability` 不得借此声称 phase_ii-only 独占；合同以"治疗期 AE 记录规范"为处置依据。请 worker_01/Codex 确认期别语义。
  4. **`r3.c1` 语病原文**: "在时间上**从与**初始事件中分离出来的…" 已逐字核实存在于 DOCX；如后续修订应记录为受控保真决定，不得静默"修正"。

## Rerun Requests Or Next Step

- **Next safe step for Codex**: (a) worker_02 实现 pkg82 配置/清单/测试时，纳入本报告 CE-1..CE-4 全部负向回归（四行条件不反转/不压平、示例不升格门槛、r3 合取不弱化、r4 不写成证据缺口、5×4 几何与 c3 行归属、r2/r3 双段示例完整、表7:=t12 标注、t7 不混入、p1031/p1032/p1033 只读补齐、owned 之外零候选）；(b) worker_01 核对 t12 期别 unknown、t7.r0 上下文来源及冻结上下文缺口；(c) Codex 对残项 1/2/4 作裁决。
- **No rerun requested**: this work item is complete; the full counterexample set is delivered above with executable acceptance conditions.
- **Report file**: delivered in this response per runner-managed path; no file was written by me.
