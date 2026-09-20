# Execution Output: phase5-ex07-issue-refinement-20260902 - worker_03

## Boundary And Context Check

- 只读核查任务，未修改任何源文件、测试或生产路径。除 pytest 运行产生的缓存外无写入。
- 初始读集两份文件已读：`context/phase5-ex07-issue-refinement-20260902_execution_context.md`、`plans/codex_execution_phase5-ex07-issue-refinement-20260902.md`。工作区 `AGENTS.md` 在初始上下文中已提供。
- 执行上下文 "Source Of Truth" 段为 TODO（Codex 未填授权源清单）。推断：以当前工作树 + HEAD 为核查基准，未读任何生产路径。此为假设，已记录。
- 工具使用：Read、Bash（grep/git/sed/pytest/python3 扫描脚本）。无浏览器/网络使用。

## Work Performed

### 1. `app/protocols/deconstruction_gate.py` 只读核查（证据）

- `TIME_ANCHOR_UNRESOLVED` 唯一产生点：`deconstruction_gate.py:2272-2284`（`_temporal_semantics`）。触发条件 `constraint is None and is_unanchored_lookback`；`is_unanchored_lookback`（2082-2091 行）要求：谓词文本含显式时长窗口、无预期锚点（`expected`/`component_expected` 来自 1768-1809 行的 `anchor_markers` 词表）、无上下文审核锚点（“筛选时/基线时”）、含“内”、且非频率定义/资料时效/未来计划。`affected_refs=[predicate.predicate_id]`，`level` 取默认「阻止发布」。
- `PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING`：`deconstruction_gate.py:2932-2943`（`_source_coverage`）。`affected_refs=[official_code, *缺失 span ids]`、`repair_scope=[official_code]`，锚定在冻结来源 span id 上。
- 关键对比：精化场景中“同一来源”的两侧身份不对称——旧问题带 span 级稳定定位，新问题只带模型自拟的 `predicate_id`（跨修订不稳定）。这正是误判为无关新问题的根源。
- `DECONSTRUCTION_GATE_VERSION` 工作树已升为 `protocol-deconstruction-gate/2026-09-02.1`（HEAD 为 `2026-08-19.3`）。
- 门禁强度核查：`TIME_ANCHOR_UNRESOLVED` 为「阻止发布」，合法精化后草稿仍不可发布——精化豁免本身不削弱发布门禁（与目标一致）。

### 2. 现有跨项目测试核查（证据）

- `tests/v2/protocols/test_deconstruction_gate_slice3.py`：5 处 `TIME_ANCHOR_UNRESOLVED` 断言（2265/2321/2409/2469/2575 行），分别锁定“无锚回溯保留为解释缺口”、“筛选时上下文防止局部示例误报”、资料时效优先、频率定义优先。夹具均为合成通用文本。
- `tests/v2/protocols/test_protocol_deconstructor_adapter_slice3.py:1173-1207`：比较器契约三条——新指纹即回退、同码换 predicate 即回退、问题数下降但有新指纹仍回退。worker_01 的豁免必须以问题码对（仅 `PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING → TIME_ANCHOR_UNRESOLVED`）收窄，才能与这三条兼容（它们不涉及该码对）。
- `tests/v2/protocols/test_generic_semantic_contract_fault_injection.py`：合成故障族注入，覆盖 coverage-missing 的有无两向。
- `tests/v2/protocols/test_protocol_control_anti_overfit_chain_wide.py`：链级硬编码静态扫描的既有先例（词表：D001/MG-K10-SAR、银屑病/特应性皮炎、PASI/EASI 等、药物名、第N周/week N/N% 模式），但其 `_CHAIN_FILES` 只覆盖 control 链，**不含** `app/agents/protocol_deconstructor.py` 与 `app/protocols/deconstruction_gate.py`——解构链目前无任何词汇扫描覆盖（缺口，见建议）。

### 3. TIME_ANCHOR_UNRESOLVED 是否需要稳定来源定位（评估）

**结论（推荐）：需要稳定定位才能完成“同一来源”证明，但不必改门禁 issue 结构；最小路径是在比较器侧推导定位。**

- 推荐方案（零 schema 变更）：worker_01 的比较器利用已有数据做两步确定性证明：
  1. **同一父规则**：coverage-missing issue 的 `official_code` == 精化后谓词所在 rule 的 `official_code`（经 component→rule 归属，纯结构遍历）。
  2. **同一来源定位**：取 coverage-missing issue 中的缺失 span ids，与精化后该 component_draft 的 `source_refs` 求交非空；或用 `source_input.source_materials`（span_id→text 映射在两个调用点均在作用域内）验证新谓词 `exact_source_clauses` 逐字出现在其中某个缺失 span 的文本中。方案文本不可变，因此以 span id / 逐字文本为键的证明跨修订尝试稳定，不受 `predicate_id` 漂移影响。
- 辅助通道：候选稿 `UnresolvedItem`（`app/domain/contracts/normalization.py:15-18`：`code/affected_scope/source_refs`）本身不含 predicate id，天然是定位型身份；线上契约示例已见 `TIME_ANCHOR_UNRESOLVED` 的 unresolved item 携带 `source_refs=["span-ex"]`（adapter 测试 359-363 行）。合法精化通常同时产生门禁 issue 与 unresolved item，可用于交叉印证。
- 不推荐方案（改门禁 `affected_refs` 加 span id）及理由：(1) 与同检查其他时间类 issue（均只用 predicate_id）不一致；(2) `_repair_issues_for_rules`（`protocol_deconstructor.py:3200-3238`）按 rule/component/predicate id 白名单过滤 `affected_refs`，span id 会在修复作用域化时被剥离，造成指纹不对称；(3) 触碰持久检查点需再次升版；(4) 波及面大于本任务“最小精化比较”边界。
- 不确定项：若 Codex 未来要求 issue 自带来源定位以满足审计（项目规则“每个实质性评估保留来源定位”），需把 `_repair_issues_for_rules` 白名单与 `DECONSTRUCTION_GATE_VERSION` 一并处理——这是独立决策，非本任务必需。

### 4. 新增实现硬编码扫描（证据）

按既有链级扫描词表对相关文件执行静态扫描（脚本内联于命令，未落盘）：

| 文件 | 结果 |
|---|---|
| `app/agents/protocol_deconstructor.py`（比较器所在，worker_01 目标区） | CLEAN |
| `app/protocols/protocol_control_gate.py` | CLEAN |
| `app/protocols/deconstruction_gate.py` | 2 处命中（见下） |

- `deconstruction_gate.py:763` 注释含「斑块状」：**本次工作树新增**（HEAD 为 0 处）。仅注释、非逻辑，但若按链级扫描标准把该文件纳入清单即违规。建议改为中性示例（如把 `"斑块状"` 换成任意“XX状”构词示例）。
- `deconstruction_gate.py:3059` 修复提示含「12周」（示例文本‘随机前12周/4周’）：HEAD 已存在，非本次新增；属用户可见文案，是否中性化由 Codex 决策。
- 指纹比较器本体（`regressing_rule_codes`/`_issue_fingerprints_by_rule`，`protocol_deconstructor.py:3277-3313`）为 HEAD 既有代码（diff 无新增行），扫描 CLEAN。

## Artifacts And Evidence

- 无新建工件（只读任务；报告由 runner 落盘）。
- 关键证据位置：`app/protocols/deconstruction_gate.py:2272-2284`（UNRESOLVED 产生点）、`:2082-2091`（触发条件）、`:2932-2943`（coverage-missing 产生点）、`:55`（门禁版本）；`app/agents/protocol_deconstructor.py:3277-3313`（指纹比较器）、`:3200-3238`（refs 白名单过滤）、`:4381`（自动修复流调用点）；`app/services/protocol_workbench_service.py:1391,1486`（服务级调用点，`source_input` 在作用域内）；`app/domain/contracts/normalization.py:15-18`（UnresolvedItem）。

## Commands And Observations

- `grep -rn "TIME_ANCHOR_UNRESOLVED\|PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING" app tests`：确认产生点与测试分布；`protocol_deconstructor.py` 中无 `TIME_ANCHOR_UNRESOLVED`，即 **worker_01 的精化实现截至本核查时点尚未落盘**（worker 并行进行中）。
- 内联 python 扫描（复用链级测试词表）：`deconstruction_gate.py` 命中「斑块」「12周」，其余 CLEAN。
- `git show HEAD:...` 对照：确认「斑块状」为工作树新增、「12周」与指纹逻辑为 HEAD 既有。
- `.venv/bin/python -m pytest tests/v2/protocols/test_deconstruction_gate_slice3.py tests/v2/protocols/test_protocol_deconstructor_adapter_slice3.py -q` → **171 passed**（默认 python3 缺 sqlalchemy，改用项目 `.venv`）。
- 同法运行 `test_generic_semantic_contract_fault_injection.py` + `test_protocol_control_anti_overfit_chain_wide.py` → **57 passed**。基线全绿。

## Blockers Or Missing Environment

- 无环境阻塞（`.venv` 可用）。
- 两项未完成验证（非本人可完成）：(1) worker_01 的精化实现落地后的最终硬编码扫描须重跑（本次扫描的是当前工作树增量，其精化代码未落盘）；(2) worker_02 的反例测试尚未可观察，集成后需按其测试复核比较器契约兼容性。
- 执行上下文 Source Of Truth 为空 TODO，已按“工作树+HEAD”假设执行，请 Codex 确认。

## Rerun Requests Or Next Step

- 给 Codex 的精确建议/问题：
  1. **不需要**为 `TIME_ANCHOR_UNRESOLVED` 做门禁 schema 变更；worker_01 在比较器内用「official_code 归属 + 缺失 span ids ∩ component_draft.source_refs（或 span 文本逐字包含 exact_source_clauses）」即可确定性地证明同一父规则与同一来源。若 Codex 仍倾向 issue 级定位，须联动 `_repair_issues_for_rules` 白名单与门禁升版，属独立决策。
  2. 建议随手修复 `deconstruction_gate.py:763` 注释中的「斑块状」为中性构词示例（一行注释改动，非本 worker 授权范围，请指派）。
  3. 请决策：是否将解构链文件（`app/agents/protocol_deconstructor.py`、`app/protocols/deconstruction_gate.py` 等）纳入 `test_protocol_control_anti_overfit_chain_wide.py` 的 `_CHAIN_FILES`（顺带解决 ：3059 既有「12周」示例的处置口径）。
- 复跑点：worker_01/02 落盘后，重跑本报告第 4 节扫描脚本 + 第 2 节所列测试文件即可闭环。
