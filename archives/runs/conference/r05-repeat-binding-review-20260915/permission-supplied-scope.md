全部核对完成。以下为第八轮审阅报告。

# 会议输出: r05-repeat-binding-review-20260915 - evidence_single_object（第八轮：许可条件分离 + 供给范围决策 + v3 消费者 + U1 修复确认）

## 输出

### 一、实际缺陷（file:line、反例、严重度、最小修复）

**V-A（中——许可条件的辅助计算无角色标记，触发/许可在计算层未分离）**
`app/services/repeat_trigger_calculation.py:62`（`for condition in component.repeat_trigger_conditions`）与 `app/projections/control_repeat_trigger_calculation.py:39`：对组件/控制的**全部**旁置条件求值并输出为 `RepeatTriggerCalculation`/`ControlRepeatTriggerCalculation`，输出**无字段区分**该条件是 `trigger_condition_id` 还是 `permission_condition_id` 引用。反例：方案 `trigger="unconditional"` + `permission="investigator_discretion"` + `permission_condition_id="perm-1"`（合同允许，`repeat_scheme.py:99-100` 只要求 trigger=source_condition 时带 trigger 引用）——计算器输出 condition_id="perm-1" 的结果（可能 TRUE）；未来触发消费者按"存在 TRUE 即触发成立"接线时，研究者许可命题的算术真值被误作触发。合同/提示/资格层已分离（提示 `protocol_deconstructor.py:427-431`、资格上下文 `binding_qualification_support.py:326-333`），唯独计算层未分离。最小修复：两个 dataclass 增加必填字段 `reference_role: Literal["trigger","permission"]`（由所有者 scheme 的 `ancillary_condition_ids` 解析；两类都是 untracked 新文件，无历史包袱），或计算器对纯许可条件单独容器输出。

**V-B（低-中——范围声明与选择结果可被分离消费）**
`app/services/qualified_observation_relation.py:168-175`：`supplied_scope`（scope="supplied_facts_only"、complete、reason_codes）与 `result_policy_selection` 是**并列字段**，无结构强制关联。用户决策要求"报告必须显式声明此范围"；当前任何读取 `result_policy_selection` 的未来消费者都可以不读 `supplied_scope`——供给范围语义（如 use_last_repeat 在缺失末次复查时会把现存末次当"最后"）会静默丢失。最小修复：把 selection 嵌套进 supplied_scope（或在其内复制 `scope`/`accounting_sha256` 指纹），使两者不可原子性分离地消费。

**V-C（低——初查缺失的原因码误导）**
`qualified_observation_relation.py:140-146`：`initial_groups` 为 **0** 个（初查不在供给内）与 **>1** 个共用 `repeat_initial_scope_not_unique`。0 个时应为"缺失"（语义不同：前者供给不全，后者归属冲突）。最小修复：分支出 `repeat_initial_scope_missing`。

**V-D（低——scheme 身份在数值侧仅记录不复核）**
`repeat_numeric_result.py:38-40,:64`：`scheme_sha256` 由 selection 复制进结果，但函数无 scheme 参数、无校验——"mandatory scheme identity"只在选择器侧成立。最小修复：增加可选 `expected_scheme_sha256` 参数由终态消费者传入比对。

**V-E（极低——合同宽松点）**：`repeat_scheme.py:93` 只禁 `forbidden` 与同 id；`permission ∈ {required, optional}` 携带 `permission_condition_id` 合法。解构层 `require_current_extraction:136-137` 仅对 investigator_discretion 强制。提示 `:430` 已约束"其他许可若原文没有额外批准要求填 null"——可接受的宽松，记录在案。

### 二、已确认边界（源码逐项）

**许可条件分离（不含 V-A 的计算层）**：
- 合同：`permission_condition_id` None 序列化省略（`:74-75`）→ **v1/v2/v3 旧材料字节保持**；非 v3/空白/forbidden/与 trigger 同 id 拒绝（`:90-94`）；`ancillary_condition_ids`（`:128-131`）对旧 scheme 退化为旧行为——**旧组件/控制不被意外拒绝**。
- 校验器：`rules.py:450` 与 `protocol_controls.py:1245` 统一遍历 `ancillary_condition_ids`，"不得夹带"闭包同时覆盖两类引用，来源闭合同口径（`rules.py:455-460`、`controls.py:1250-1262`）。
- 解构：`require_current_extraction` 三处调用（谓词 `:2153`、控制 `:476,:554`）；提示明确"不得与trigger_condition_id共用编号"、investigator_discretion 必须提供、"两类条件的作用范围均依原文，**不得从time_limit.reference推断触发对象**"（`protocol_deconstructor.py:427-431`；控制 `:1271`）——time_limit.reference 与触发范围在合同与提示层无推断路径。
- 资格父上下文：`repeat_owner_predicate_ids` 改按 `ancillary_condition_ids` 成员（support `:324`），新增 `repeat_permission_owner_predicate_ids` 仅在有许可引用者时附加（`:326-333`）——旧规则集的 pair body 无新键，重建一致。

**观察资格 v3 / consumer v18**：
- `OBSERVATION_CONSUMER_VERSION="qualified-observation-relation/v3"`（`:11`）——旧评测 manifest（v2 消费者）被 `require_observation_method:24` 拒绝（fail-closed，需新评测，符合"不跳过方法评测"）。
- consumer v18 两处 Literal 已加（合同 `:61,:165`）；旧 v17 material 的 `observation_relations`（v2 形态 dict）在新 `list[dict]` 字段下可读、存储哈希不变——**v17 读兼容成立**（新键仅出现在新产出中，无现存消费者按新键读取）。
- `supplied_scope`（`:168-173`）：用既有 `candidate_fact_accounting`（`:120-122` 按组身份过滤）+ `observation_scope_reasons`（`:123-126`）+ 图结构/origin/争议/notes 原因汇总（`:127-135`）——**只证明供给内核验完备**，`clinical_scope_complete: False` 恒定（`:177`）——用户范围决策未被当作上游页面完整性证据。
- `result_policy_selection` 调用纯选择器（`:141-144`），`asdict` 含 `replacement_authorized=False`；**最终 eligibility 不变**：`observation_relations` 仅写入 material（`qualified_binding_selection.py:482-488,:808`），无 outcomes/map/evaluator 消费。
- `qualified_operand_pairs` identity-local（`:150` 身份相等 + fact/locator/attribute 全匹配 + 同口径拒绝理由，`:147-158`）；quote/pair 完整性（`:70-93` 逐字子串 + 记录匹配）不变。
- 变更/哈希闭合：verify 重建回执 + 成员逐字段相等 + summary/评测绑定（`:28-43`）；material.selection_sha256 含新键。

**选择器与数值计算（上轮 U1 修复确认）**：
- `RepeatResultSelection` 必填 `graph_sha256/scheme_sha256/considered_group_ids`（`repeat_result_selection.py:10-12`），`result()` 统一填充——所有拒绝路径也带身份与 considered 集（`:33-38`）；`calculate_repeat_numeric_result:54-55` 强制 selection 与图同哈希——**同图绑定成立**。
- `as_material`（`repeat_numeric_result.py:23-35`）：`repeat-numeric-result/v1`、numerator/denominator 字符串化（大整数安全）——**精确有理序列化**；`context_sha256`（`:65`）；`replacement_authorized: False` 恒定；docstring `:25-26`（选择器）显式"scope_complete concerns the supplied review set, not all clinical history; known missing source obligations remain separate and are never cleared here"。
- 组内全部合格记录一致（`:98-100`）、跨组单位一致（`:104`）、AFFIRMED/bool/finite 守卫（`:89-97`）复核不变；两个函数仍**无产品调用者改变最终入排**（数值计算器无调用者；选择器仅经 v3 观察资格进 material 留存）。

### 三、集成缺口（与 bug 分开；均未声明完成）

1. 终态结果采用消费者：`result_policy_selection`/`RepeatNumericResult.as_material` 均无 evaluator/发布侧消费；`repeat_relation_unverified` 守卫不变。
2. 报告层显式声明供给范围（用户决策的"Reports must explicitly state this scope"）未接线——报告投影尚不输出 supplied_scope 文案。
3. 许可的书面判断绑定：judgment_content 到 permission 条件的"批准复查"命题映射仍缺（本轮仅到许可条件 DNF 真值；V-A 修复前该真值还与触发混同）。
4. 页面级判断搜索覆盖与 supplied_scope 的联合呈现未接线（两者是不同维度的缺失证据，须分别报告）。
5. 方法评测/审批需覆盖 observation consumer v3 与 permission 语义（旧 v2 评测已被正确拒绝，新评测记录尚待产生）。

### 四、未验证部分

全程只读，未运行代码/构造/测试/模型/浏览器。V-A 反例与 V-B 消费路径为源码推演（当前无消费者，风险在接线时兑现）；`asdict`/JSON 往返后 tuple→list 的哈希规范性依赖 canonical_hash 的既有序列化行为，未实证。本报告为有界增量源码审阅，不构成临床或整产品验收；运行测试按用户决定推迟，本轮不建议亦不执行。
