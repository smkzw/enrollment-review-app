# 执行输出: phase5-ex07-issue-refinement-20260902 - worker_02

## 边界与上下文检查

- 已按提示读取初始读取集：`context/phase5-ex07-issue-refinement-20260902_execution_context.md` 与 `plans/codex_execution_phase5-ex07-issue-refinement-20260902.md`。
- 我被分配的项目（第 2 项）：在 `tests/v2/protocols` 增加服务级和比较器级反例，证明合法精化可保存但仍不可发布，外来来源、不同规则、不同未解析问题和普通新问题继续被拒绝。
- 初始读取集不足以确定被测接口与门禁/服务的既存测试形态，因此按提示以工具补充只读检查（详见“已执行工作”）。仅写入一个新测试文件；未修改任何应用代码、生产路径或他人工件。
- **重要观察**：worker_01 的实现（`app/agents/protocol_deconstructor.py` 中新增 `_refined_time_anchor_fingerprints` 与改写后的 `regressing_rule_codes`）在本会话进行中（文件 mtime 2026-09-02 04:02）落入了同一工作树。我的测试按公共接缝契约编写，与该实现兼容，最终 16/16 通过。

## 已执行工作

新增文件 `tests/v2/protocols/test_issue_refinement_counterexamples.py`（16 个测试，比较器级 9 + 服务级 7）。

场景构造（全部通用，无项目/病种/药物/评分/时间点特异逻辑）：在共享通用夹具（`confirmed_fixture`，IN-01/EX-01 两父规则）上给 EX-01 冻结目录新增一段实质性来源 `span-ex-note`（“既往3个月内患有严重神经系统疾病”，无锚点日期的既往回溯）。基线草稿只欠该片段的子规则承接，真实门禁报 `PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING`（refs 含 `EX-01` 与缺失 span id）；精化稿新增子规则承接同一片段，其原子条件无时间约束且回溯范围无锚点，真实门禁改报 `TIME_ANCHOR_UNRESOLVED`（refs 为谓词 id）。这正是被允许的唯一精化形态。

比较器级（直接调用公共比较器 `regressing_rule_codes`，签名未变）：
- 合法精化（同父规则 + 新未解析锚点所属子规则的 source_refs 引用缺失片段）→ 返回空集，不算回归（`test_comparator_accepts_same_source_coverage_to_unresolved_refinement`）。
- 干净承接缺口且无新增问题 → 仍不算回归（防止修复破坏“改进”判断）。
- 外来来源两变体：新锚点子规则引用同规则另一片段（`span-ex`）或其他父规则片段（`span-in`）→ 拒绝。
- 不同规则：覆盖缺失在 IN-01、新锚点在 EX-01 → 仅 EX-01 被拒，证明精化证明不得跨规则借用。
- 不同未解析问题：缺口被干净承接后，既有谓词（`predicate-alt`，属另一子规则、引用 `span-ex`）上新出现的未解析锚点 → 拒绝。
- 普通新问题：同位置出现 `TIME_ANCHOR_MISSING` 或 `NEGATION_NOT_BOUND_TO_SOURCE` 等非精化目标编码 → 拒绝（编码对白名单边界）；精化之外夹带任何其他新指纹 → 整体拒绝；无任何覆盖缺失前科时的新锚点 → 拒绝。

服务级（`ProtocolWorkbenchService.apply_feedback` 原文理解纠错流程，注入受控修订器）：
- **真实门禁**合法精化 → 修订保存成功（revision_number+1、新子规则落盘、diff 仅 EX-01），且 `get_integrity` 仍 `publishable=False`、阻断问题为 `TIME_ANCHOR_UNRESOLVED`、`PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING` 消失 —— 即“可保存但仍不可发布”，证明发布门禁未被削弱。
- **真实门禁**精化候选夹带普通新问题（否定比较无原文支撑）→ `FEEDBACK_REVISION_FAILED`，修订保持原样。
- **微型确定性门禁**（`RefinementBoundaryGate`，只表达两类问题编码，定位语义与真实门禁一致）隔离指纹边界：外来来源两变体、不同规则缺口（IN-01 缺口下 EX-01 新锚点）、既有谓词上的另一未解析问题 → 全部 `FEEDBACK_REVISION_FAILED` 且草稿修订不变。

## 工件与证据

- 唯一写入工件：`tests/v2/protocols/test_issue_refinement_counterexamples.py`（新文件，16 个测试，`py_compile` 通过）。
- 关键只读证据（观察）：`app/protocols/deconstruction_gate.py` 中 `PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING` 的 `affected_refs=[official_code, *missing_span_ids]`（约 2937 行）、`TIME_ANCHOR_UNRESOLVED` 的 `affected_refs=[predicate.predicate_id]`（约 2278 行）及其触发条件（`is_unanchored_lookback`，约 2082 行）；`app/services/protocol_workbench_service.py` 的 `apply_feedback` 精化/拒绝流（约 1352-1545 行）与 `_validate_source_error_scope` 中 `parent_catalog_mappings` 不可变（约 1760-1771 行）；会话开始时的旧版 `regressing_rule_codes` 无条件把新指纹判为回归（修复前行为证据）。
- 修复锁定证据（实测）：用 monkeypatch 把 `_refined_time_anchor_fingerprints` 置空以模拟修复前比较器，合法精化用例返回 `{'EX-01'}`（即原误判）；当前实现返回 `set()`。证明验收用例确实复现并锁定该修复，而非恒真。

## 命令与观察

- `.venv/bin/python -m pytest tests/v2/protocols/test_issue_refinement_counterexamples.py -q` → **16 passed**。
- `.venv/bin/python -m pytest tests/v2/protocols/test_protocol_deconstructor_adapter_slice3.py tests/v2/protocols/test_redeconstruction_backend.py tests/v2/protocols/test_deconstruction_gate_slice3.py tests/v2/protocols/test_generic_semantic_contract_fault_injection.py -q` → **238 passed**。
- `.venv/bin/python -m pytest tests/v2/protocols -q` → **2 failed, 1378 passed**（含我的文件）；`--ignore` 我的文件后同样 **2 failed, 1362 passed**，证明两个失败与本工件无关：
  1. `test_protocol_replay_harness.py::test_d001_p803_p805_read_only_checkpoint_rebuilds` —— 单测隔离运行即失败，属确定性既存失败（D001 回放只读重建，不在我的授权范围内，未触碰）。
  2. `test_protocol_transport_transient_retry.py::test_retry_warnings_preserve_chinese_recovery_semantics` —— 单文件运行通过；与任一既存文件（如 `test_redeconstruction_backend.py`）合跑即复现失败，属既存的模块间顺序依赖，与我的新文件无关。
- 开发期发现并修正的测试设计缺陷（记录为边界有效性证据）：外来来源服务级反例初版让两个新子规则误用同一 `predicate_id`，导致比较器的 owner 查找用锚定组件的来源证明了外来组件的问题；改为独立谓词 id 后反例如实拒绝。这说明反例确实走的是真实来源定位查找路径。

## 阻碍或缺失环境

- 无阻碍。会话中途工作树并入 worker_01 实现属并行调度事实，已如实记录；我的测试未因此返工（接口契约一致）。
- `tests/v2/protocols` 全量运行中的 2 个既存失败（见上）超出本工件授权范围，留待 Codex 处置。

## 重跑请求或下一步

- 供 Codex 验收的确认点：本报告的接口假设为 `regressing_rule_codes(previous_draft, previous_issues, revised_draft, revised_issues, selected_codes)` 签名不变、精化证明由修订稿 `component_drafts` 的 `source_refs` 与缺失片段求交得出 —— 与 worker_01 落地实现一致，无需其返工。
- 建议后续（非本工件范围）：排查 `test_protocol_replay_harness.py` 的 D001 只读重建失败与 transient-retry 的顺序依赖是否源自工作树未提交的 Phase 5 改动。
- 验收后可按流程归档；未做任何最终临床/监管/视觉验收判断，Codex 仍为最终验收权威。
