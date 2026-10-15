# Conference Output: r05-observation-consumer-review-20260915 - evidence_single_object

## Output

第 3 轮窄域最终复核完成（只读源码，未运行测试/导入/产品/模型/数据库/浏览器，未修改任何文件）。**总裁决：Codex 陈述的四项变更与实际源码一致，此前三轮的全部已识别缺陷（R1-F1/F2、R2-F1/F2/F3/F4）均已在源码层面验证修复；本轮仅发现 1 项陈述与源码的轻微出入（控制侧 wire schema 未做 required 手术，由契约层强制补偿，fail-closed 无正确性缺口）和 2 项无行动必要的边角观察。无新增 FAIL 级发现。**

### 一、逐项核验裁决（PASS/FAIL/UNVERIFIED + 证据行号）

**主张 1：window_order 显式枚举 + 生产者/门强制 — PASS（控制侧 wire schema 子项为 PARTIAL，见 N1）**
- 枚举与历史序列化：`observation_selection.py:44`（`Literal["not_applicable","within_window","before_window_check","unresolved"] | None = None`），`:46-51` 序列化仅在 None 时剔除（历史载荷保留）。
- 官方 wire schema 非空枚举：谓词生产者 `protocol_deconstructor.py:583-588`（`required` 追加 `window_order` + 四值 enum）✅。
- 两个生产者提示词均描述区分与来源支撑：`protocol_deconstructor.py:250-252`（含“不得默认退回采用更旧的有效记录。该顺序须引用方案依据”）、`protocol_control_deconstructor.py:1244-1245`（含“不默认改选更旧的有效记录”）✅。
- 共享校验器拒绝与时间约束存在性不匹配：`observation_selection.py:81-90`（真值表核对：有约束+not_applicable 拒绝；无约束+within_window/before_window_check 拒绝；unresolved 恒放行）；谓词侧挂载 `rules.py:266-270`（AtomicExpression 自身 time_constraint）。
- 控制 require_explicit 拒绝缺失：`control_evaluation_spec.py:95-96`（传入 require_explicit），`:123-131` `validate_control_evaluations` 对全部四层（applicability/trigger/obligation/exception）以 `require_explicit=True` 调用。
- 官方解构门拒绝缺失：`deconstruction_gate.py:3335`（`policy.selection is not None and policy.selection.window_order is None` → `OBSERVATION_POLICY_SOURCE_UNVERIFIED`；同时要求 policy 本身在场与摘录归属）。

**主张 2：排序助手按 window_order 分支 — PASS**
- 已知 window_order 前置门槛：`ordered_observation_selection.py:56-59`（None/unresolved 或与 time_constraint 存在性不匹配 → `observation_window_policy_unverified`）。
- 仅 within_window 过滤 FALSE：`:89-91`。
- before_window_check 保留全部候选参与严格支配排序，选中者 FALSE → `:106-109` 以 `observation_out_of_window` 失败且 excluded 只含被选事实（**不回退改选更旧记录**，R2-F1 的修复语义确认）；UNKNOWN → `:110` `observation_window_membership_unverified`。
- interval_condition 仍拒绝：`:80-81`。
- DTO 明示顺序与是否选取成功：`review_history.py:396-407` `_observation_selection_note`（四分支需求句 + “已按该要求选取记录…”/“目前尚未确定可采用的记录。”），谓词侧 `:429` 以 `bool(observation.fact_ids)`、控制侧 `:560-562` 以 `bool(audit.selected_fact_ids)` 分叉。

**主张 3：consumer v11 + model_fields_set 序列化对称 + 遗留条件等价 — PASS**
- v11 常量与 Literal：`qualified_binding_selection.py:24, 57, 153`；旧 v10 绑定的授权经 `_validate_authorization` 的版本等式（`authorization.consumer_algorithm_version != QUALIFIED_BINDING_CONSUMER_ALGORITHM` 即拒）被隔离，R2-F2 修复确认。
- 序列化仅在字段原本缺席时剔除：`observation_selection.py:21-26`（`"selected_fact_ids" not in self.model_fields_set` 才 pop）。构建方始终写入该键（`qualified_binding_selection.py:322`）→ 新选择哈希不变；旧载荷（无键）重载后重序列化形状与原始一致 → 哈希对称双向成立（R2-F3 修复确认）。`frozen_review_calculation.py:300` 的 `model_copy(deep=True)` 保留 fields_set，无复制失真。
- 遗留等价检查仅在字段在场时执行：`qualified_binding_selection.py:130-133`、`review.py:216-219`（均带 `"selected_fact_ids" in ...model_fields_set` 门槛）。
- 当前材料（consumer v11）明确要求字段：`qualified_binding_selection.py:208-213`；控制结果 v3 要求字段：`control_review_outcome.py:78-81`（v1/v2 由 `:69-74` 序列化整体剔除 ordering）。
- 历史侧 selected ⊆ context：`review_history_service.py:392`（R2-F4 修复确认）。未发现任何旧载荷重写路径（幂等重发布早退不变）。

**主张 4：本增量内被忽视的决定性缺陷排查 — PASS（未发现新缺陷；两项边角观察见下）**
- 哈希对称：如上逐向验证，含 raw-dict 哈希（`qualified_binding_selection_hash`）与 validator `model_dump` 重算在旧/新两种形状下一致。
- 空选择：失败排序的审计以 `selected_fact_ids: []`（字段在场、序列化保留）进入材料，满足 v11 要求；DTO 如实显示“目前尚未确定…”；控制仓储 used==selected==∅ 成立。
- 时间不确定性：UNKNOWN 永不过滤（仅 within_window+FALSE 过滤）；选中者 UNKNOWN → 未核实而非臆断；before_window_check 下非选中事实的 UNKNOWN 窗口状态只影响其自身，不产生不实标注（败者按 `not_governing_observation` 报告，日期主张独立于窗口状态，准确）。

### 二、残余事项（均非 FAIL）

**N1（轻微，陈述出入）：控制侧 wire schema 未做 required 手术。** 谓词生产者有 `protocol_deconstructor.py:583-588` 的 schema 手术；控制生产者（`protocol_control_deconstructor.py:1123, 1155`）直接返回 `model_json_schema()`，其中 `window_order` 在 JSON schema 层仍是可选可空。强制性由提示词（`:1244-1245`）+ 契约层 `validate_control_evaluations`（require_explicit=True）在重建时拒绝补偿——失败方向为 fail-closed（模型省略 → 重建被拒），无正确性缺口。可选的一行对齐：在控制生产者 schema 函数做同样的 required 追加。是否值得做由 Codex 定（会改变控制解构的提示/schema 版本指纹）。

**N2（装饰性）：旧政策（window_order=None）走 `_observation_selection_note` 的 else 分支**，输出“尚未核实应先选取记录还是先限定时间范围。…已按该要求选取记录…”两句并存略显别扭；仅影响 hypothetical 的 pre-window_order 存量运行展示，且 evaluator v14 门槛（`frozen_review_calculation.py:165`）强制新计算重新冻结上下文，新运行不可达该组合。无需行动。

**UNVERIFIED（如实申报）：**
1. 解构模型实际输出中 window_order 分类与方案原文的一致性——静态审阅无法证明语义正确；缓解链已核实在源：提示词要求引用方案依据、双路资格核对、解构门摘录核验、unresolved 逃生口。运行时验证按用户决定推迟到整机测试。
2. 存量数据库中是否存在 v1/v2 控制快照或旧审计行——边界内禁库，采用“源码级向后省略”论证（已验证成立：None/缺省字段在序列化时剔除，旧哈希可复算）；如 Codex 需要实证，须另行授权只读查询。

### 三、给 Codex 的最终建议

1. 四项变更可按“源码核验通过”纳入综合；R2-F1 的语义裁定已通过 window_order 选择器落地，遗留风险收敛为“解构分类的语义正确性”，属已声明的运行时验证范围。
2. N1 的控制侧 schema 对齐为可选小改，若采纳注意它会改变控制解构 wire 指纹并需重走相应门。
3. 本角色三轮全部发现的状态：R1-F1 ✅修复、R1-F2 ✅修复、R2-F1 ✅修复（window_order）、R2-F2 ✅修复（v11）、R2-F3 ✅修复（model_fields_set）、R2-F4 ✅修复（`:392`）；R2-F5/R2-F6 维持“可选/无需行动”。

边界声明：只读审阅；以上 PASS 均为静态源码证据链结论，不构成临床、监管、视觉或用户验收；条件复检（conditional retest）仍属已声明开放范围，本报告未将其记作已实现；Codex 保留最终采信权。
