审阅完成。四条主线（通用观察政策、逐事实范围对账、确定性排序与 any/all 消费、未选记录来源与历史兼容）已全链路核对。以下为完整会议输出。

---

# Conference Output: r05-observation-consumer-review-20260915 - evidence_single_object

## Output

只读全流程审阅已完成。未运行任何测试/产品/模型/数据库/浏览器，未修改源码。结论先行：**发现 2 项建议修订的代码级缺陷（F1 过度阻断、F2 报告文字失真），1 项与既定未完成范围一致的结构性恒未核实路径（F3），其余核心链路（对账词表匹配、排序确定性、any/all 三值消费、历史兼容与未选记录来源）证据核对通过。**

### 审阅范围与证据基础

按会议语境 Source of Truth 清单读取：`app/domain/contracts/{observation_selection,qualified_binding_selection,review,rules,control_evaluation_spec}.py`、`app/services/{ordered_observation_selection,qualified_binding_selection,frozen_review_publication,review_history_service,binding_candidate_comparison,binding_qualification_support}.py`（节选）、`app/domain/{expression,calendar_dates,publication}.py`、`app/llm/candidate_fact_accounting.py`、`app/api/v2/review_history.py`（节选）、`frontend/src/api/review-history/{reviewHistoryHttp,reviewHistoryTypes}.ts`（节选）、`frontend/src/components/review/FrozenReviewReport.tsx`（节选）、`frontend/src/domain/{reviewConditionNotes,frozenReviewExport}.ts`（节选）、`app/protocols/deconstruction_gate.py`（政策原文校验段）。

### 发现（按严重度排序）

**F1（中，代码缺陷——any/all 政策被无关门槛过度阻断）**
- 证据：`app/services/qualified_binding_selection.py:291-296` 中 `if review_context is None: return [], [], ["observation_scope_unverified"], None` 位于 `policy.selection is None`（any/all 必然走此分支，因契约 `observation_selection.py:56-57` 禁止非 single 模式携带 selection）之前。而 any/all 路径实际执行的 `observation_scope_reasons`（`ordered_observation_selection.py:20-37`）与 `_select_facts_for_identity`（`qualified_binding_selection.py:211-271`）均不消费 review_context；any/all 的冲突阻断实际由 `expression.py:536-538、551-560` 基于 `fact.conflict_group_id` 承担。`review_context_id` 来自候选任务载荷可选字段（`binding_qualification_support.py:761-763`），缺失时 any/all 条件一律假性 unresolved。
- 影响方向：保守（不会误通过，只会误阻断），但属于功能性缺陷且理由码误导。
- 最小修订：将该门槛下移至 `policy.selection is not None` 分支内（即仅排序路径要求 review_context，因其需要 `conflict_groups`，`qualified_binding_selection.py:317`）。
- 推论与不确定：若 Codex 的原意是“any/all 也必须绑定冲突注记上下文”，则应改理由码并补注释而非移动门槛——请裁定意图。

**F2（中，用户可见——未选出成功的条件仍显示“依据方案核对最近一次记录”）**
- 证据链：`qualified_binding_selection.py:311-326` 在 `select_ordered_observation` 失败（`fact_ids` 为空，如 `observation_tie_unresolved`）时仍构造并返回 audit；`qualified_binding_selection.py:514-526` 对 unresolved 结果保留 `observation_ordering`；`frozen_review_publication.py:151` 无条件将其写入 `PredicateObservation`；`app/api/v2/review_history.py:401-406` 只要 audit 存在即生成“依据方案核对最近（最早）一次记录。”。因此平局/窗口失败（truth=UNKNOWN）的条件旁会出现这句陈述性文字。reason_codes 仍如实携带不确定原因（`reviewConditionNotes.ts:14-16` 有对应文案），但该句本身言过其实。
- 最小修订（推荐 b）：(b) `_assessment_dto` 中仅当 `observation.fact_ids` 非空时生成 selection_note（一行门槛）；(a) 备选：`_select_with_ordering` 仅在成功时返回 audit——但这会同时隐藏失败情形下已知的窗口外记录。建议保留 not_selected 展示、只门控文字。
- 决策点：失败排序是否仍应向审阅者披露窗口外记录（我倾向披露）。

**F3（低-中，与既定未完成范围一致——source_validity + 单项排序恒未核实）**
- 证据：`qualified_binding_selection.py:420-430` 收集 `time_purpose == "source_validity"` 且 single+time_constraint 的规格；`source_validity_operand_calculable`（54-59、86-87 行）会解除其 `source_validity_requires_policy_evaluation` 待办使配对免于拒绝；但 `ordered_observation_selection.py:71-73` 对 `time_purpose != "event_membership"` 且带时间约束者一律返回 `observation_window_policy_unverified`。净效果：该类身份永远无法经排序路径 usable。
- 判定：与会议语境"Known pending: conditional retest requires a richer source-backed policy"一致，属已声明的开放范围而非隐性假完整；但“配对级解除待办 + 身份级必然失败”的组合易误导后续维护者，建议在 420-430 行处加一行约束说明，待富政策落地时一并收口。不要求现在改逻辑。

**F4（低，语义不对称——事实级 vs 属性级对账）**
- 证据：`ordered_observation_selection.py:27-37` 以事实级状态 `candidates_in_both_lanes` 构建候选集合，而 operands 只取 value 属性可用配对（`qualified_binding_selection.py:227-229`）。某事实 date_range 合格但 value 属性被拒时，candidates ⊋ operands → `observation_operand_set_unverified` 假性 unresolved。方向保守（拒绝静默丢弃有候选事实），判定为有意设计；建议在 docstring 注明，不改代码。

**F5（信息，核对通过——确定性与 any/all 消费）**
- 排序：严格区间支配唯一胜者（`ordered_observation_selection.py:87-96`），平局与部分日期歧义分类正确（三候选含重叠区间情形验证无误）；窗口成员判定用 `DateValue(lower_bound, precision)` 重建区间经 `calendar_dates.py:26-39` 展开，部分日期跨界返回 UNKNOWN 而非臆断；迭代顺序确定（66、100 行 `sorted`）。
- any/all：`expression.py:499` 先按 fact_id 排序，`536-550` 逐事实求值后 Kleene ANY/ALL 合并（117-130），任一冲突（551-560）或窗口 UNKNOWN（515-522）阻断为 UNKNOWN。reason 去重保序，输出确定。
- 对账：`binding_candidate_comparison.py:10-20` 的 9 种状态词表与消费方匹配（仅接受两种、其余保守未核实）；`_accounting_rows` 按 fact_id 排序（34 行）+ `canonical_hash` sort_keys=True（`publication.py:10-18`）→ `accounting_sha256`/`policy_sha256` 稳定可复算。

**F6（信息，核对通过——未选记录来源与历史兼容）**
- 旧版隔离：`review.py:200-225` fixture/v1 禁止 observation_ordering 且序列化剔除该键；选择材料 v1-v3 禁止回填排序与原文含义键（`qualified_binding_selection.py:186-228`），selection_sha256 重算口径与创建口径一致。
- 历史重校验：`review_history_service.py:385-396` 对存储 audit 重验政策存在性、`policy_sha256` 对当前条款包复算、not_selected 事实属于冻结上下文；`586-599` 聚合未选事实 locator 并经 FactAuthorityValidator 验证。
- UI/导出：DTO 携带上下文事实 locator（`review_history.py:414-419`），前端 strict-keys 解码（`reviewHistoryHttp.ts:485-513`），报告与导出渲染 not_selected 及可点击证据（`FrozenReviewReport.tsx:117-122、205-208`；`frozenReviewExport.ts:39-43`）；`reviewConditionNotes.ts` 覆盖排序/对账全部理由码，无缺词。
- 已知限度：`accounting_sha256` 在历史读取端不复核（该处无对账数据），仅作完整性指针——可接受，如实记录。

**F7（信息）** 控制族报告无未选记录审计、`claims_complete` 守卫（`protocol_control_matrix.py:1804+、2409+`）保持 false 默认及禁断校验——均与会议语境声明的开放范围一致，未见虚假完整声明。

### 给 Codex 的质疑与决策点

1. **F1 意图裁定**：`review_context` 门槛是错放还是对 any/all 的有意额外约束？若有意，理由码应区别于 `observation_scope_unverified`。
2. **F2 文案门控**：是否接受“保留 not_selected 披露、仅门控 selection_note”的方案 b？
3. **次要**：`expression.py:532-535` 在 any/all 分支前计算的 `observed_values` 于该分支闲置（仅 551 行单值路径使用）——纯冗余计算，无行为差异，可留待顺手清理。

### 边界声明

只读审阅，未运行测试/产品/模型/数据库/浏览器，未写入任何源码或 runner 管理的报告路径。以上 F5-F6 的“核对通过”指静态证据链一致性，不构成临床、监管或用户验收；最终采信与修订由 Codex 决定。无阻碍项，无需回退链。
