API 与全链核对完成。以下为第五轮审阅报告。

# Conference Output: r05-repeat-binding-review-20260915 - evidence_single_object（第五轮：观察对应证据接线端到端）

## Output

### 一、缺陷与备注（无高/中严重度缺陷）

**P1（低-中，口径需所有者确认——观察资格的值级严格性）**
`app/services/qualified_observation_relation.py:73-75`：`pair_direct_selection_rejection_reasons(record, source_validity_calculable=...)` 未传 `written_content_verified`。对 `requires_professional_judgment` 的复查所有者配对，`professional_judgment_applicability_unverified` 恒入拒绝原因（该 pending 检查仅在书面判断核验时才可消解）——此类位置的观察链接/origins 永远进 `source_unresolved`。方向保守（不会产生不安全肯定），但观察链接引用的是**记录位置**（同次采集/复查回指），不是判断值本身；若方案中复查所有者多为研究者判断类，观察图会系统性空置。最小修订（若确认需放宽）：对 quote 资格按所引 `fact_attribute`（如 date_range 等位置性属性）判定，或显式传入书面判断核验结果。接线后应以真实分布复核此口径。

**P2（低——空观察任务也会激活授权绑定）**
`app/services/prepared_review_publication.py:65-66` 以 `identity_coverage` 非空判定转发：当某族存在复查方案所有者但**全部**无候选来源时，coverage 仍非空（各组带 `no_observation_sources_in_candidate_input` 原因，`observation_relation_input.py:77`），空观察任务（零模型调用）仍被转发并进入授权/评测绑定。结果 `select_qualified_observation_relations` 返回空列表，无实质影响；仅授权域被不必要地激活。可接受的记录性行为，标注备查。

**P3（备注——授权哈希域构造风格不一致）**
`app/services/qualified_review_command.py:178-181`：`content`/`proposition` 在 auth_id 哈希中恒以 `None` 占位，`observation` 用条件展开。无 observation 时与旧 auth_id 域一致（重放幂等保持，配合 `:40-42` 的不覆盖校验安全）；三种可选依据两种构造风格，未来追加第四类时易出错。建议统一为条件展开或统一 None 占位。

**P4（确认非缺陷的边界 case）**：资格任务无 `review_context` 键时 `qualified_review_command.py:108` 跳过一致性检查——但观察任务的输入装配层强制 `material["review_context_id"] == context_id`（`observation_relation_input.py:34-35`）且资格源校验要求 payload 与 source 的 context 键一致（`qualified_observation_relation.py:28-29`）——无 context 的旧资格任务无法产出可消费的观察任务，闭环成立。

### 二、已确认边界（按分派点）

**1. 评测目的与审批复用**：`ObservationEvaluationManifest`（`observation_method_evaluation.py:7-9`）以 `observation_relationship_fidelity` 独立 kind 继承判断评测合同；`review_method_evidence.py:6,42` 将其加入 `read_method_evaluation` 的联合类型——复用既有持久化 manifest/scoring-report 读取与 `read_review_method_approval` 审批链，本模块不生成审批（读取器仅校验，`:39-44`）。

**2. `qualified_observation_relation.py`**：`verify_qualified_observation_relation`（:24-39）经现有 `verify_completed_observation_relation` 重建回执；candidate/context/frozen/comparison 哈希与资格源逐项相等（:27-29）；summary 逻辑/工件哈希绑定 adoption（:30-31）；**组员配对逐字段相等**且族一致（:33-36）；`require_observation_method`（:10-21）绑定来源资格方法、合同、提示、汇总版本、双路路由与 `OBSERVATION_CONSUMER_VERSION`。`select_qualified_observation_relations`（:42-121）：每个被引 (fact_id, locator_id) 必须有可接纳资格记录（:62-84）；**同位置多属性配对保留为列表**（:59，不覆盖）；至少一条 admitted 仅许可对应关系（docstring :45）；`qualified_source_pair_ids` 保留（:60,:81,:115）；无效/不确定引文与争议链接原样保留（:98,:106,:114,:116）；过滤图仅用资格化链接/origins（:117-118）且 `clinical_scope_complete/replacement_authorized` 恒 False（:119）；不因丢弃来源推断缺失（:46）。

**3. 选择合同 v17**：两处 consumer Literal 含 v17（`qualified_binding_selection.py:61,:165`）；授权 `observation_relation` 仅限当前 consumer 与授权版本（:86-89"历史授权不能补入本次复查对应依据”）——**旧算法不能携带新证据**；material 的 observation 字段缺省省略（:199-201）保持旧序列化，relations 无 adoption 拒绝（:209-210），哈希 material 含在场 observation 字段（:230 dump 全量）；`selected_fact_ids` 显式规则保留 v16 语义（:142-147）且 v17 加入强制记录集合（:231）。

**4. 选择服务**：授权 gate input refs 含观察 job/评测（`qualified_binding_selection.py:165-170`）；`verify_qualified_observation_relation` + `select_qualified_observation_relations` 在授权存在时执行（:474-484），结果仅写入封存 material（:802-804）——**不进 outcomes/组件清单/control_map 计算**：`repeat_relation_unverified` 的四层强制不变（`_select_with_ordering` :289-291 与主循环 re-add），不选择结果，不用图证明缺数据；`_AUTHORIZATION_WAIVED_REASONS` 未变。最终入排对带复查方案的条件保持 UNKNOWN（上轮已核的求值器守卫与清单排除无变化迹象）。

**5. 命令与发布**：`submit_qualified_review` 绑定 subject/episode 到 context（:54-57）；`observation_jobs` 键 ⊆ 资格任务、值非空且唯一（:89-92）；每族评测 kind 匹配恰一份 manifest 并经 `require_observation_method` 绑定（:163-169）；adoption 带 summary 哈希与评测摘要（:170-174）；gate 幂等不覆盖（:28-42）。`frozen_review_publication.py`：`PUBLICATION_VERSION = "frozen-review-publication/v7"`（:31）入 request_hash（:50）；观察评测加入评测集且须在已审批 manifests 内（:82-86）+ kind 校验（:95-96）；方法 publication/evaluator/consumer 版本绑定（:99-102）；**工厂内源重验证**（:103-105 重建选择，全部 verify 链在工厂内重跑）；PredicateObservation 的 reason_codes 合并 outcome 未决原因（:156-159）——`repeat_relation_unverified` 传播到最终观测记录而非被吞没。

**6. 准备工作流 v6 与转发/API**：`CONTRACT v6`（`prepared_review_workflow.py:26`），`READABLE_CONTRACTS` 含 v1-v6（:27）；每族一个观察子任务（:357-363，CHILD_TYPES :35-36）；`require_current_review_tasks` 强制六任务当前版本（:44-59）——**旧 v5 任务可读但不可用当前版本续算/发布**（`_advance :209` 与 `prepared_review_publication :20` 双重拒绝）；`_dependencies_complete` 的 expected 按合同版本分层——v5 保持其原始命题子任务期望（:277-278），观察子任务仅 v6 期望（:279-280,:287-288）——**孤儿/缺失/重复/类型不符/候选溯源错误均显式拒绝**（:289-305）；取消/重试沿用 worker 所有权与回执边界，重试拒绝路由变化（:406-407）。零相关配对不调模型（`judgment_content_job.py:111-112` 空 pairs 仅 summary 步）；`prepared_review_publication.py:52-66` 仅转发已验证且 coverage 非空的观察任务。API `qualified_review.py:27-30`：qualification max2、判断/命题/观察 job 映射各 max2——命题双族（修复旧 max1）与观察 ID 均支持。前端任务种类显示按所有者声明已支持（UI 文件不在本轮读集，未核）。

**K1 修复确认**：`control_calculation_experiment.py:35` `purpose: Literal["four_layer","auxiliary_repeat_trigger"]`，`:45-48` four_layer 序列化省略 purpose——旧字节兼容、辅助哈希域显式。

### 三、未验证部分（运行时不确定性）

- 全程只读：未运行任何代码/构造/测试/模型/浏览器；全部结论为源码推导，无运行/临床 PASS。
- P1 的保守偏差实际影响面（专业判断类复查所有者的占比）无法从源码确定，需接线后以真实分布复核。
- 前端任务种类显示、`observation_relation` 任务在真实作业库中的生命周期（取消传播/恢复）未核（分别属 UI 与运行时行为）。
- `_enqueue_content_job`/`_reconstruct_judgment_content_lane_state` 基类内部沿用上轮已核签名，本轮未重读全文。
- 已知待办（本轮不视为缺陷、不扩围实现）：复查结果采用、期限/次数范围消费者、方法审批的完整链路在真实评测数据上的执行；最终入排对复查保持 UNKNOWN 直至真实的来源资格策略消费者完成。
