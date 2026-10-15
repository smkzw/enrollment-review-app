全部证据闭合。以下为本轮审阅报告。

# Conference Output: r05-repeat-binding-review-20260915 - evidence_single_object（第三轮：F1-F3 修复确认 + 旁置树计算 + 观察关系 v2）

## Output

### 〇、前轮修复最小确认

- **F1 已修**：`binding_qualification.py:312` 与 `qualified_binding_selection.py:51` 的 prompt Literal 均已含 `"binding-qualification/v5"`，与 `:27` 常量一致——`compose_qualification_summary`（support :881,:896）与授权 round-trip（services :399-401）不再被 Literal 拒绝。
- **consumer v16 已修**：`qualified_binding_selection.py:57`（授权）与 `:154`（selection material）的 consumer Literal 均已含 v16，与默认常量一致。
- **F2 已修**：提示改为“官方条款材料中的repeat_owner_predicate_ids”（`binding_qualification.py:158`），不再对控制族材料暗示不存在的字段。
- **F3**：按所有者决定不加限制（v3 空条件不破坏正确性），本轮未发现新的必须收紧的理由（所有读取按内容哈希闭合）。

### 一、实际缺陷（按影响排序）

**J1（中——同一条回指边双角色不产生结构疑问）**
- 位置：`app/domain/contracts/observation_relation.py:91-94`（`agreement_key` 把 `reference_kind` 纳入去重键）+ `app/domain/observation_relation_graph.py:61-65`（`by_reference` 按 `(child, reference_kind)` 分组判歧义）。
- 后果：两路同时把同一 `(left, right)` 的 `repeat_of` 声明为 `initial_observation` **和** `preceding_observation` 时：合同层两 key 不同、不判“同一观察关系重复”；图侧 `directed` 保留两个元组、`by_reference` 两组各一个 prior、不触发 `repeat_predecessor_ambiguous`；`repeat_edges` 输出两条同 `(child, prior)` 不同 kind 的记录。当 prior 组与 child 间隔超过一次复查时这是自相矛盾声明，却无任何 `structural_reasons` 标记。分派要求的“同角色多个目标仍冲突”已实现，“同目标多角色”未覆盖（注意仅一次复查时“初查即紧邻上次”两声明可同真，故不能一刀切判错）。
- 最小修订：图构建中对同一 `(child, prior)` 出现多个非 None reference 的情况：若 `acquisition_roles` 中 prior 组角色唯一且与其中一种 kind 一致则归一，否则追加 `repeat_reference_kind_conflict` 结构疑问；或在合同 `unique_coverage` 对同边双 kind 判重复并要求模型二选一。

**J2（低——`unclassified_fact_ids` 在 v2 语义被重定义）**
- 位置：`observation_relation_graph.py:92-93`。v1 语义是“无任何边连接的事实”；v2（origins 提供）改为“角色非唯一组的全部成员”。同名输出跨版本语义不同：v1 下角色明确但无边的孤立事实算 unclassified，v2 下不算。信息未丢（receipts 层另有 `facts_without_agreed_relationship` 保留无边语义，:73-74），但图内同名键漂移易误读。
- 最小修订：v2 改用独立键名（如 `origin_unresolved_fact_ids`）或在图中并列保留两种清单。

**J3（低——历史 material 缺旁置 outcome 时 KeyError 而非明确错误）**
- 位置：`repeat_trigger_calculation.py:61`（`outcomes[identities[key]]` 直接下标）与 `predicate_proposition_calculation.py:30`（`by_identity[...]`，`repeat_triggers_only=True` 时必查旁置身份）。若消费不含旁置 outcome 的历史版本 selection material 会抛 KeyError 而非带说明的拒绝。当前消费入口经 `verify_completed_binding_qualification` 强制当前提示/合同版本，历史 material 实际不可达——降为健壮性备注。最小修订：`.get()` 缺失时抛“选择结果缺少旁置条件身份，须用当前版本重新核对”。

**J4（备注）**：`repeat_trigger_calculation.py:72` 的 `condition_sha256` 直接对 `RepeatTriggerCondition.model_dump` 哈希，未做组件层那样的子序归一（`_repeat_condition_material` 排序 + `_expression_material` 交换归一）；同逻辑不同子序的条件会产生不同 sha。仅作记录锚、无消费比对，不影响正确性。

**完整消费还需要的证明（分派点 2 要求指出，均无消费者、不视为已完成）**：真实“复查触发成立并可用复查结果替代初查”的消费者至少还需要——(a) 触发证据属于哪次检查的作用域证明（本轮 observation_relation 图 + origins 仅双路同意、且 `clinical_scope_complete` 恒 False，不证明供给范围完整）；(b) 复查许可链：`repeat_scheme.permission` 与 investigator_discretion 的书面判断记录；(c) 次数与期限消费者（`maximum_repeats`、`time_limit` 需按 `reference_kind` 选择 initial/preceding/episode_anchor 锚）；(d) 结果采用规则（`result_use`/`result_combine` 替代或合并初查值）；(e) 访视覆盖证明。`replacement_authorized` 在 `RepeatTriggerCalculation`（`:20`，`init=False`）、图（`:84`）、汇总（receipts `:84,:90`）三处恒 False。

### 二、已确认边界

**1. expression.py 重构**：`_evaluate_bound_predicates`（`:608-675`）逐行保留旧 `evaluate_component` 的校验序列（清单精确集合 :624-636、未核实须空清单 :637-642、书面判断缺口 :643-649、命题结果范围 :650-660、结果组装 :661-673）；`predicate_fact_ids=None` 仍走旧类别路径（:502-507）。`evaluate_component`（:705-732）仍只 `[expression]+exception_expression` 两树。`evaluate_bound_expression`（:686-702）必填显式清单（:694-695“不能按类别补选”），不构造伪 RuleComponent、返回 `EvaluationResult` 不进 `ComponentEvaluation`；`_evaluate_atomic` 的 repeat_scheme/semantic/occurrence/prospective 守卫不变（:488-495）。产品内 `evaluate_bound_expression` 唯一调用者是旁置计算（rg 确认），无越权入口。

**2. repeat_triggers_only 与旁置树计算**：默认 False——`frozen_review_calculation` 调用不带参数，正式计算仍只算 trigger/exception（旧行为保留）。`repeat_triggers_only=True` 时 entries 换为 `component.repeat_trigger_predicates`（:24-25），命题结果按谓词 id 过滤到各条件、不混条件（repeat_trigger_calculation :67-68）。`calculate_repeat_trigger_conditions`：sealed + `require_unchanged`；scope 四元组、anchor_dates、事实集合与冻结输入一致（:37-43）；逐事实核对 fact_type/value/unit/polarity、`effective_date`（经 `_phase3_date_value` 保精度、未知日期不借记录时间——`eligibility_review_projection.py:176-188`）、`evidence_span_ids == locator_ids`（:44-51）；未核实旁置身份强制空清单（:65-66）；每条件独立求值。无产品上层调用（显式入口、未接线，不冒充完成）。

**3. observation_relation 五文件**：合同 v1 缺 version 保持历史序列化（:23-28）、v2 输入由 input 层显式构造（input :64）；`same_acquisition` 禁带 reference_kind（:80-81）；`ObservationOrigin` 的 initial/repeat 须本条原文 quotes、不得仅凭日期（:103-111）；origins 逐条覆盖 reviewed_fact_ids（:135-138）、旧结果省略保持序列化（:121-126）。LLM：提示明确“不得因最早、无回指或单条称初查”（llm :74-76）、kind 三值区分（:62-64）、不计算次数/时限/阈值、不判许可、不选结果（:78）；`build_observation_relation_messages:47-48` 拒旧版组；`validate:99-100` 拒无 origins 回答——**旧回应不当新方法证据**；repeat_of 无 kind 拒（:107-108）；两端 quotes 与摘录逐字子串核对（:109-117）。input：scheme 收集只取正式条件所有者（谓词族 trigger/exception :39-42；控制族四层投影 :46-48——旁置原子按合同 `validate_control_repeat_conditions:1257-1258` 不得嵌套 scheme）；每要求一组防 pair 爆炸；coverage 恒 `clinical_scope_complete: False`；单组超限拒绝不截断（:23-24）。receipts：双路须不同独立模型（:49-51）；只有双路完全同 key（含 kind）的关系进图；对称差记 disputed；各路完整 dump 保留（:81-82）；三 false 恒置（:84,:90）。job：复用判断内容任务基类（enqueue 层同模型双道拒绝；`verify_completed_content_job` 强制当前 job_type/contract/prompt/purpose——版本变更后旧任务不可消费）。

**4. 图**：同一复查同时明确指向初查（initial_observation→A）与紧邻上次（preceding_observation→B）时，`by_reference` 按 (child, kind) 分组、各一 prior，不误作两个前次（graph :61-65）；同角色多 prior → `repeat_predecessor_ambiguous`（:64-65）；环检测经 `TopologicalSorter`（predecessors 不分 kind 聚合，覆盖全部有向边）→ `repeat_relationship_cycle`（:66-69）。v1 hash 兼容：3 元边 + 无 origins → graph v1 且不含 `source_origins/acquisition_roles`（:72-73,:86-93），旧字节不变；4 元边或 origins → v2。新版种类不会当 fact_id：边校验只取 `edge[1:3]` 为身份、kind 居 `edge[3]`（:18-22）。origins 只同意且非 unresolved 的角色进图（receipts :63-66）；未确定清单保留（`unresolved_origin_fact_ids` :78-80）；同次组角色聚合仅作关系候选——组内冲突记 `same_acquisition_origin_conflict`（:45-46）、`initial_marked_as_repeat`（:55-56）、`repeat_reference_origin_conflict`（:57-58）均为结构疑问，组角色多值输出 "unresolved"（:88-90）；`clinical_identity_verified/replacement_authorized` 恒 False（:84）。

**初查/前次/未明确不可互换**：reference_kind 三值互斥（合同 Literal、校验 :107-108、图 edge[3] 校验与按 kind 分组）；origins role 三值互斥且 unresolved 不进图；unspecified 不被提升为 initial（提示 :63-64“不能把一般的复查回指当作紧邻上一次”+ 分组逻辑）。未发现方案、疾病或模型硬编码——全部结构来自冻结输入与合同校验，提示仅含方法学规则。

### 三、未运行验证

- 本轮完全只读：未运行 Python/内存构造/测试/应用/模型/浏览器，未写文件，未读原件/密钥/个人历史。
- J1 场景（同边双 kind 双路同意）与 J3 的 KeyError 均为源码推演，未构造数据实证。
- `JudgmentContentJobExecutor` 与 `_verify_call_sequence` 基类内部未通读（仅核对参数化签名与 reconstruct/enqueue/verify 挂接点）；`tests/v2/test_expression_temporal_candidate_scope.py` 为新增未读（按约定回归集中在产品完成后执行，本轮不评）。
- `calculate_repeat_trigger_conditions`、observation_relation 入队/校验均为显式入口、无产品上层调用；不对此作速度/质量数字结论，最终结果采用、期限与次数消费者待实现，临床声明保持 false。
