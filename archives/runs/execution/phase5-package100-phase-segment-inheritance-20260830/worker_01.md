# Execution Output: phase5-package100-phase-segment-inheritance-20260830 - worker_01

## Boundary And Context Check

已在同一会话重新读取：

- `context/phase5-package100-phase-segment-inheritance-20260830_execution_context.md`
- `plans/codex_execution_phase5-package100-phase-segment-inheritance-20260830.md`
- `memory://root/memory_summary.md`

本 worker 继续执行只读诊断：

- 未修改源代码、测试、原始临床材料或冻结基线。
- 未覆盖 `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/`。
- 未创建新版本基线或报告文件。
- 未清理、格式化或改写工作区中的既有变更。
- 报告中的修复影响属于诊断或内存模拟结果，不代表 Codex 最终验收。

## Work Performed

### 1. 追踪阶段语境数据流

确认当前链路为：

```text
StructureBlock source blocks
  -> build_phase_applicability_graph
  -> phase projection
  -> full protocol coverage manifest
  -> phase applicability plan / package context
```

关键实现位置：

- `app/protocols/phase_detection.py`
  - `_scope_from_text`
  - `_establishes_scope_context`
  - `_body_contexts`
  - `_scope_with_context`
  - `_effective_table_scopes`
  - `build_phase_applicability_graph`
- `app/protocols/full_protocol_coverage.py`
  - `_paragraph_clauses`
  - `_paragraph_atom_slices`
  - `_phase_scopes_for`
  - `build_resolved_full_protocol_coverage_view`
  - `build_full_protocol_coverage_manifest`
- `app/protocols/phase_applicability_planning.py`
  - `PhaseApplicabilityContextCatalog`
  - `_package_context_units`
  - `_build_phase_applicability_chunks`
  - `plan_phase_applicability_batches`
- `app/protocols/section_index.py`
  - `_effective_scopes`

### 2. 复现 D001 真实统计章节缺陷

冻结结构中统计章节的实际范围如下：

| Ref | 内容/结构 | 当前 scope |
|---|---|---|
| `body.p1168` | `统计学考虑`，outline level 0 | `UNKNOWN` |
| `body.p1169` | II/III SAP 说明 | `MIXED` |
| `body.p1170` | `统计假设`，outline level 1 | `UNKNOWN` |
| `body.p1171` | `Ⅱ期为探索性研究，不做检验假设。` | `PHASE_II` |
| `body.p1172` | 明确 III 期目标及“如下的假设检验”引导语 | `PHASE_III` |
| `body.p1173` | `假设如下：` | `UNKNOWN` |
| `body.p1174` | `H_0` | `UNKNOWN` |
| `body.p1175` | `H_1` | `UNKNOWN` |
| `body.p1176` | `Alpha = 0.025` | `UNKNOWN` |
| `body.p1177` | `多重性校正`，outline level 2 | `UNKNOWN` |
| `body.p1178` | 明确 III 期段落 | `PHASE_III` |
| `body.p1179` | `样本量计算`，outline level 1 | `UNKNOWN` |
| `body.p1180` | `Ⅱ期临床阶段` | `PHASE_II` |

`body.p1172` 的真实文本包含：

> `针对上述主要估计目标的均采取如下的假设检验：`

当前 `_establishes_scope_context` 对该段返回 `False`，因为现有检测仅覆盖：

- 结构标题；
- 窄范围的普通期别标题；
- 期别访视表标题；
- 固定形式的“适用于以下要求”等措辞。

因此 p1173–p1177 没有从 p1172 获得 III 期语境。

### 3. 确认通用边界合同

当前缺陷不是 D001 专属词汇缺失，而是普通段落阶段语境建立条件过窄。

建议的通用合同：

1. 只有局部明确的单一期别 scope 才能建立 successor context。
2. 普通段落必须同时具有语法上明确的前向引导关系，例如“如下”“以下”“下列”等，才能传播到后续定义、假设、公式、列表或说明。
3. `MIXED`、`SHARED`、无期别标记的段落不得建立单一期别 successor context。
4. 普通叙述、历史、交叉引用、一般性阶段提及不得扩散。
5. 后续更深层标题可以继承上下文。
6. 同级标题和祖先级标题必须关闭上一上下文。
7. 普通段落建立上下文时，必须保留其最近外层结构标题的 outline level；不能将 `context_heading_level` 置为 `None`，否则嵌套标题无法正确判断继承或关闭。

### 4. 建立正反例矩阵

当前正例缺口：

- III 期明确段落后接“假设如下”；
- 明确期别段落后接定义；
- 明确期别段落后接公式、假设、统计列表；
- 前向引导语下的嵌套标题继承。

已确认的负例：

- `Ⅲ期研究采用优效设计。` 这类无前向引导关系的普通叙述不应传播。
- II/III 混合段落即使含“如下”，也不应建立单一期别上下文。
- 同级结构标题应关闭旧上下文。
- 祖先级结构标题应关闭旧上下文。
- 一般性的期别提及或交叉引用不应重标后续中性段落。
- 同一表格中存在局部期别语境时，不能把一个单元格的期别扩散到无关单元格。

### 5. 量化当前 D001 基线

直接从冻结结构块加载并运行当前代码所得：

- 输入结构块：`3581`
- 图结构块：`3405`
- 投影块：`282`
- coverage manifest units：`1848`
- expected ambiguous IDs：`1245`
- applicability packages：`131`

图 scope 计数：

- `UNKNOWN`: `2055`
- `PHASE_III`: `727`
- `PHASE_II`: `586`
- `MIXED`: `35`
- `SHARED`: `2`

manifest scope 计数：

- `UNKNOWN`: `1227`
- `PHASE_II`: `312`
- `PHASE_III`: `289`
- `MIXED`: `18`
- `SHARED`: `2`

当前源引用与冻结 manifest 的直接比较：

- 比较引用数：`1848`
- scope 差异：`0`

结构 blob 证据：

- SHA-256：`3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`
- 大小：`1,423,501` bytes

### 6. 模拟最小修复对 Package 100 的影响

仅在内存中将 p1173–p1177 模拟为显式 III scope，未写 manifest、plan 或任何 artifact。

模拟结果：

- expected ambiguous IDs：`1240`
- package count：`131`
- Package 100 owned：
  - `body.p1168`
  - `body.p1169`
  - `body.p1170`
- Package 101 从 `body.p1179` 开始，随后为 `body.p1186`–`body.p1196`
- Package 102 从 `body.p1197` 开始，随后为 `body.p1200`–`body.p1205`

这与“Package 100 不再拥有 III 假设构造”的 checkpoint 目标一致，但仍只是模拟证据，不能替代新版本 artifact 和 Codex 验收。

### 7. 发现独立的 `section_index` 传播风险

`section_index._effective_scopes` 是第二套独立传播逻辑。当前其结果为：

- p1172 为 III 后，p1173–p1179 均被传播为 III；
- 同级标题 `body.p1179`（`样本量计算`）也被错误保留为 III；
- 该实现没有与 `phase_detection` 相同的 heading-depth closure 规则。

统计学章节当前不是主要 eligibility section，因此该差异未必直接改变当前 eligibility index，但它构成通用阶段适用性合同分裂风险。

建议：

- 下游统一使用 `phase_detection` 的 effective graph scope；或
- 抽取并复用相同的结构边界辅助逻辑；
- 禁止下游在遇到 `UNKNOWN` 时无条件继续沿用上一期别，尤其不能跨越同级或祖先标题。

### 8. 检查当前 planner context 漂移

使用当前代码从原始结构重新构建计划时：

- 包所有权序列保持与冻结计划一致；
- 但 context 量显著增加：
  - 当前 context units：`11439`
  - 最大 context size：`269`
  - rendered context total：`12684`
- 冻结计划：
  - context units：`7383`
  - 最大 context size：`197`
  - rendered context total：`8628`

131 个包的 context 集合均存在差异。Package 100 当前代码 context 比冻结计划多出 9 个当前专有引用：

- `body.p311`
- `body.p316`
- `body.p347`
- `body.p358`
- `body.p364`
- `body.p365`
- `body.p366`
- `body.p868`
- `body.p885`

这属于 planner/context 实现漂移，独立于本次阶段继承缺陷。新基线比较必须同时检查 ownership 和 context，不能只比较包 ID 或 owned refs。

## Artifacts And Evidence

授权读取的权威路径：

- `context/phase5-package100-phase-segment-inheritance-20260830_execution_context.md`
- `plans/codex_execution_phase5-package100-phase-segment-inheritance-20260830.md`
- `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/coverage_manifest.json`
- `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/frozen_phase_plan.json`
- `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/structure/blobs/protocol_blocks/3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json`

冻结计划关键标识：

- `plan_id`: `papl-40b1237a22e538a278b4fd5e`
- manifest ID：`d001-ii-phase-closure-20260827-slice59i-table-caption-rebaseline-manifest`
- protocol：`D001-02-002:v1.0:phase-ii`
- phase：`phase_ii`
- Package 100 ID：`pap-101e8c3b73a8b084cdcfa140`

当前冻结 Package 100 原始 owned refs：

```text
body.p1168
body.p1169
body.p1170
body.p1173
body.p1174
body.p1175
body.p1176
body.p1177
body.p1179
```

未生成或写入以下对象：

- 新版本 coverage manifest；
- 新版本 frozen phase plan；
- comparison report；
- worker report 文件。

## Commands And Observations

运行的聚焦回归命令：

```text
./.venv/bin/pytest -q \
  tests/v2/protocols/test_metadata_phase_slice2.py \
  tests/v2/protocols/test_real_protocols_slice2.py \
  tests/v2/protocols/test_slice58h_cross_heading_packing.py \
  tests/v2/protocols/test_phase_applicability_package_selection.py
```

结果：

```text
52 passed, 5 warnings in 20.88s
```

观察：

- 测试全部通过。
- 5 个 warning 为 Swig deprecation warnings。
- 该测试结果验证当前基线回归，不验证尚未实施的阶段继承修复。
- D001 scope、graph、manifest、plan 统计来自对真实结构 blob 的 Python 模型重建。
- Package 100 修复影响来自内存模拟，未产生持久化文件。

## Blockers Or Missing Environment

- 本 worker 的授权范围是只读诊断，无法实现 source/test 修复。
- 新版 artifact 尚未生成；因此无法提供真实的 hash、mtime、全部 package context 对比结果。
- `section_index` 与 `phase_detection` 的双重传播合同是否在本 Package 100 范围内统一，需要 Codex 决策。
- 当前 context 量与冻结基线存在全量漂移；即使 ownership 稳定，也不能据此假定模型输入稳定。
- 当前会话无法向名为 `Main` 的父会话发送独立 hub 消息；全部发现已在本报告中完整返回。

## Rerun Requests Or Next Step

1. 由 worker 02 实现最小通用修复：
   - 识别局部明确期别 + syntactically explicit forward lead-in；
   - 保留最近外层 heading level；
   - 只允许结构边界内的后续继承；
   - 保持 `MIXED`、`SHARED` 保守语义；
   - 不加入 D001 专属词汇或固定 refs。

2. 增加正例回归：
   - p1172 风格的 III 假设引导段；
   - 后续假设、公式、定义、列表；
   - 更深层标题继承。

3. 保留并扩充反例回归：
   - 普通期别叙述不扩散；
   - 混合期别引导语不建立单一期别上下文；
   - 同级标题关闭；
   - 祖先标题关闭；
   - 无前向关系的交叉引用不扩散；
   - 表格单元格上下文不跨局部边界扩散。

4. 由 worker 03 在新的 versioned artifact 目录中重建 D001，并比较：
   - source bytes、SHA-256、mtime；
   - 全部 graph/manifest refs；
   - 全部 scopes；
   - expected ambiguous IDs；
   - 全部 package ownership；
   - 全部 package context sets；
   - Package 1–99 的源 ownership 和临床语义稳定性。

5. 新 Package 100 验证条件：
   - owned 仅为 `body.p1168`、`body.p1169`、`body.p1170`；
   - p1173–p1177 为显式 III/read-only context；
   - p1179 保持 unknown 并移动到 Package 101；
   - 无 Package 99 refs；
   - 无旧 Package 100 语义输出残留。

6. Codex 最终验收前，单独审查 `section_index._effective_scopes` 是否必须切换为 phase graph authoritative scope；不得把 harness、回归测试或包序列稳定误判为 `parent_clinical_acceptance`。
