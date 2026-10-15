两份前端源已核实。以下为窄范围更正与重审建议。

# Conference Output: r05-repeat-binding-review-20260915 - evidence_single_object（第十轮：W1 更正 + 逐谓词证据角色合同重审）

## Output

### 一、W1 更正（撤销原发现）

上一轮 W1 不成立，系我的检索缺陷（`-maxdepth 2` 未覆盖 `src/components/review/` 深层路径，且文本检索词“供给”未匹配实际措辞“已提供的资料”；我误以 dist 与浅层列表断言“无 src 可审”）。正确证据：

- `frontend/src/domain/frozenReviewExport.ts:7`：`reviewEvidenceScopeNote = "本次审核仅依据本次已提供的资料及其核对结果。已知缺失和待核实事项另列；未提供的情况不作推断。"`——通用报告范围声明，非观察范围通过声明。
- **单份导出**：`:24-31`（“本次审核资料”首节内嵌）；**集合导出**：`sections()` 复用于每份（`:109,:114-117`）——单份/集合共享同一常量；**屏幕/打印**：`frontend/src/components/review/FrozenReviewReport.tsx:9`（import）与 `:96`（打印视图渲染）。
- “已知缺失另列”由独立段落承载（`frozenReviewExport.ts:76-86`“补充资料与核实事项”）——范围声明与缺口报告分离，符合用户决策。**无需新增后端字段仅为此文本**；此前 W1 的该项建议撤销。

### 二、触发-目标建议重审（替换上一轮 `condition_targets` 方案）

上一轮方案的两处不健全（分派指认，源码复核属实）：scheme 级“每条件一个角色”对**混合 DNF** 一刀切——同一触发/许可条件里“初查血压≥阈值”（采集谓词）与“正在使用某合并用药”或“研究者书面同意”（外部上下文谓词）并存时，整条件过滤到某采集组会错误排除后者的证据（它们不属于任何观察采集组）；且“普遍排除目标复查组”无法表达“后一次复查的声明触发=紧邻上次复查”的谓词（preceding 组本身是复查组）。

**最小来源绑定：条件内逐谓词证据角色合同。**

- **位置与形态**：扩展 `RepeatTriggerCondition`（`app/domain/contracts/rules.py:422-436`）新增 `predicate_evidence_roles: dict[str, Literal["initial_observation","preceding_observation","external_context","unresolved"]]`，键为条件内谓词 id（条件内唯一已由 `validate_nonrecursive_condition` 保证，`:429-433`）。缺省 `{}`；映射外的谓词一律按 `unresolved`。控制族对称扩展 `ControlRepeatTrigger`（`protocol_controls.py:1217-1219`，键为 `condition_atom_id`）。
- **角色语义**（计算侧，落在 `repeat_trigger_calculation.py:64-74` 与 `control_repeat_trigger_calculation.py` 的选择装配处）：`initial_observation`/`preceding_observation` → 该谓词的 `identity_outcomes.fact_ids` 进一步限定到图 `acquisition_roles` 对应角色的组内事实（preceding 组由 `repeat_edges` 中 `reference_kind="preceding_observation"` 的边解析；无该边→UNKNOWN）；`external_context` → 不过滤，直接用既有资格选择（外部上下文谓词的证据本就不在采集图内）；`unresolved` → 计入 `unverified_predicate_ids`（UNKNOWN，不猜）。
- **防自证由角色集实现，而非运行时排除规则**：v1 角色集**不含** “target_repeat”——目标复查组永不作为触发/许可证据，从根上落实“不用复查结果证明自身触发”，同时不误伤 preceding 复查组（它有专属角色）。被判定“哪一次是目标复查”由组装器作为输入识别（target_group_id，从计数上下文+图推导），不属于合同推断。
- **不从 `time_limit.reference` 默认角色**（期限参照≠证据范围），无疾病/模型启发式；角色必须由方案解构显式声明。
- **序列化兼容**：空映射省略（沿用 `preserve_legacy_repeat_conditions`/`preserve_old_repeat_conditions` 的 wrap-serializer 模式），旧组件/控制字节与哈希不变；非空映射禁止出现在旧版（校验器拒绝，同 `result_population` 的先例，`repeat_scheme.py:85-86`）。
- **投影与校验位置**（固定，非孤立 helper）：解构 wire schema/提示（双侧，wire 版本提升——在既有复查 DNF 提示中要求逐谓词声明角色，未明者留空）；`validate_repeat_trigger_conditions`（`rules.py:439-467`）/`validate_control_repeat_conditions` 校验映射键属于条件表达式；`predicate_binding.py` 的 `_repeat_condition_material`（`:217-219`）与组件哈希纳入映射；两个辅助计算器按角色装配选择；资格 `_condition_material` 透传给提示（观察/资格任务本身不变）。
- **证据复用判定**：**不需要扩展资格 schema/prompt，也不需要新模型阶段**。逐谓词的合格事实选择（`identity_outcomes.fact_ids`）与观察图（`acquisition_roles`/`repeat_edges`）都是既有证据；新增的只是方案侧角色声明（解构期一次产出）与计算器内的谓词级过滤/未决装配。观察任务的 origins/links 提示无需感知角色。

**阻塞设计选择（唯一）**：角色映射未声明（历史方案、provider 留空）时是否允许回退。建议维持全 `unresolved`（触发/许可恒 UNKNOWN，作为报告缺口呈现），而非按 `external_context` 宽松回退——后者会让旧方案静默获得更弱的防自证边界。所有者决策后实施；本报告非临床验收。
