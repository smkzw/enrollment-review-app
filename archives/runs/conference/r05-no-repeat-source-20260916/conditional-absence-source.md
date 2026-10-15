所有证据链已闭合（九个文件全文 + 相邻依赖：表达式层三值逻辑、控制层 DNF 求值、资格层选择函数、两处仓储、两处 wire 版本、版本标记）。以下为完整会议输出。

# Conference Output: r05-no-repeat-source-20260916 - evidence_single_object（第三轮：条件性缺席与辅助原件）

## Output

### 0. 角色与限制声明

继续同一有界只读角色（回退 `zcode`/`GLM-5.3-Flash`，effort max）：仅只读源码复核，未写文件、未运行测试/导入/对象构造/服务/DB/浏览器。**全部结论为静态源码级结论，非运行验收**。上轮 O1 的撤回理由（PartialDateRange 校验完整边界、DateValue 保留 precision、`_date_bounds` 展开）已接受，不再重报。

### 1. 政策链逐项核验（对照指定审重点，file:line 证据）

**(1) 隐式 NOT 缺证据变 FALSE — 已防住。** `_evaluate_logical` 的 NOT 为三值反转，UNKNOWN 保持 UNKNOWN（expression.py:125-131）；未核实谓词强制空选择并输出 UNKNOWN（:651-656、:699-701）。控制族 `_not` 同语义（control_layer_evaluation.py:65-67）。缺席链上，触发真值 UNKNOWN → `repeat_absence_trigger_unverified`，不采用（repeat_result_selection.py:61-63）；`calculations.get` 缺失时同样走未核实分支（resolution:144+152）。

**(2) 混合 AND/OR 被改写 — 未发现。** `_combine_bound_expression` 按原表达式树递归求值，无扁平化/重写（expression.py:711-716）；ALL/ANY 三值支配序正确（:111-124：ALL 中 FALSE>UNKNOWN>TRUE，ANY 中 TRUE>UNKNOWN>FALSE）。控制族 DNF `_all`/`_any` 同构（control_layer_evaluation.py:51-62），`evaluate_control_condition` 强制全原子三值齐全（:70-75）。

**(3) 初查被当已发生复查 — 已防住。** `_condition_targets` 零复查+唯一初查时产出 `(初查组ID, "initial_without_repeat", (trigger_condition_id,))`（repeat_condition_selection.py:154-161），只带触发条件、不带许可。迭代器重建 targets 并逐一核对 `(repeat_group_id, condition_id)` 与 kind（:304、:313-314）；resolution 校验计算的 `target_kind` 与行一致（:57）；`repeat_checks` 仅遍历 `repeat_ids`（:112-137），初查目标从不进入逐次检查；次数/期限校验要求 observed 集合恰等于 repeat_ids（:102-104），初查不计入。presentation 中初查固定标“初查记录”（presentation:28-29），缺席状态独立呈现（:11-15）。graph 侧若角色误标导致初查不唯一，resolution:145-146 阻断。

**(4) 目标集合/所有者/hash 串用 — 未发现通路。** resolution 以 `(owner, repeat_group_id, condition_id)` 三元组建键（:34、:45-48），计算的 owner_references 必须映射到 scheme 的 trigger/permission 引用（:53-54），parent、condition_sha256、target_kind、`scope_sha256=canonical_hash(整行v2)` 四重绑定（:55-58）；v2 行内嵌 owner、kind、condition_sha256、graph_sha256 及逐原子 scope（v2 :265-278），迭代器先按当前方案重建并核对行内容（:311-317）。旧计算行缺 `target_kind` → `raw.get` 为 None ≠ 行值 → 报错拒用（:57），配合版本门强制重算。

**(5) source roles — 正确。** `initial_without_repeat` 要求组角色为 initial 且取证 role 恰为 initial_observation（:14-17）；preceding/target 路径要求组角色 repeat（:18-21），无法挪用到初查目标；target_observation 对非许可条件重置为 None（:224-226）；None/unresolved → 未核实（:48-49）；external_context 保持独立、不参与采集对应核实，audit 标 not_applicable（:50-52），与“仍独立候选范围核实”一致。

**(6) 纯条件真值未泄漏到结果消费者 — 核实通过。** 触发真值只经四个出口：(a) 作为 `absence_trigger_truth` 门控 selection 的缺席政策（selection:60-66），FALSE 仍须通过 ：67-69 初查角色/范围守卫、:72 structural、:74 roles、:92 祖先链后方可采用初查；(b) 存入 resolution["absence_trigger"] 审计（:176）；(c) presentation 三态文本“已核实未触发/已触发但未见复查结果/尚未核清”（:11-15）；(d) 经 `evidence_fact_ids` 以“核对依据，不作为检查结果值采用”呈现（:67-70）。不进入资格求值，不直接改变原子结果。

**(7) 辅助原件缺失/冲突校验 — 无遗漏。** `evidence_fact_ids` = source_fact_ids ∪ repeat_checks 各操作数 used_fact_ids（含内嵌 written_permission）∪ absence_trigger（evaluation_result.py:31-38）；两处仓储闸门：history:408 与 control 仓储:88 要求 ⊆ 冻结 context，否则拒绝展示/范围违规；报告为 unselected_fact_ids 加载对应定位（history:648）。**冲突闸闭合确认**：predicate 族辅助条件经 `_evaluate_atomic` 对选中事实检查 `conflict_group_id` → source_conflict（expression.py:582-585），语义命题同（predicate_proposition_calculation.py:21-22）；控制族经 `conflict_groups` 显式传入（control_repeat_trigger_calculation.py:50-52）。两族均已设闸，无不对称缺口。

**(8) 历史内容 hash — 未改变。** scheme 序列化器省略 None（repeat_scheme.py:121-122），新枚举值仅影响新方案；新校验器 ：139-140 仅对新值触发（并经 ：150-151 保证 trigger_condition_id 非空）。`RepeatResultSelection` 字段形状未变；`evidence_fact_ids` 为只读 property，无序列化面。resolution 新键 `absence_trigger` 只出现在新产物，旧存档经 `.get` 读取（presentation:11、evaluation_result:34）兼容，存档不改写。版本标记全部证实：`dnf-v13`（deconstructor:132）、`phase5/control-agent-wire/v18`（control:116）、资格 consumer/v26（qualified_binding_selection 合同默认）、`component-review/v30`（frozen_review_calculation.py:27）、`frozen-review-publication/v12`（frozen_review_publication.py:31）。两处解构提示均已写入新政策并强制完整 trigger_condition_id 引用（deconstructor:447、control:1310）。

**(9) 未实现边界 — 与声明一致。** 现有复查仍走原逐次路线（`_condition_targets` 有 repeats 即逐次带 ancillary 全条件）；多次许可、聚合+排序、当前节点计数在代码中仍以 UNKNOWN/未实现闸门存在，无完成声称。

### 2. 缺陷结论

**本轮未发现确证缺陷，无需修复**（不凑数量）。两条诚实标注的低危稳健性观察，均失败关闭、不产生错误采用：

- O-a：`evidence_fact_ids` 属性内 `EvaluationResult.model_validate(raw)`（evaluation_result.py:37）对被篡改/畸形存档会抛 pydantic ValidationError 而非领域错误；仓储闸门语义上更宜返回 ReviewHistoryIncompleteError/ScopeViolationError。最小修正（可选）：属性内 try/except 视为不可信并返回空集由 ：408/:88 闸门拒绝。不改也不产生错误结果。
- O-b：`identities[atom_id]`（repeat_condition_selection.py:222、:59 触发计算侧）在条件表达式引用无已发布身份的原子时 KeyError——依赖上游冻结发布装配合同保证；畸形输入崩溃而非静默通过，属可接受失败模式。如需收紧可在装配层加存在性校验。

### 3. 未验证项声明

全部结论为静态阅读：`_evaluate_atomic` 的窗口/冲突行为、缺席链在真实数据上的端到端行为、资格 v26 工厂对冲突事实进入 `allowed` 范围的实际排除率，均未经运行验证。`repeat_observation_ordering.py` 与 `repeat_result_resolution.py` 之外的聚合/排序闸门沿用上轮结论（文件未列入本轮读取集、无变化声称）。多次许可、复查聚合与排序、当前节点计数仍未声称完成——本轮源码与此一致。
