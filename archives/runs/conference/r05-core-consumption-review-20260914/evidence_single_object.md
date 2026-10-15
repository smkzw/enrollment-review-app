I'll start with the assigned conference context and plan, then independently audit the evidence and consumption gaps before drafting the report.The source list is the R3 design, T5 plan, and the listed binding/judgment modules. I'll read those next and only pull adjacent definitions if a gap actually needs them.The contracts show `predicate_ids` and qualification statuses already exist. Next I’ll inspect how selection, frozen calculation, and judgment gaps actually consume them.I have enough source evidence to separate written-judgment proof from source eligibility, and to specify a reuse path that does not treat dual-lane agreement as adoption.

# Conference Output: r05-core-consumption-review-20260914 - evidence_single_object

## Output

### Role and boundary

独立只读审阅：研究者书面判断与多观察消费缺口。不写源码、不跑测试/模型/浏览器、不声称临床或产品验收。Codex 保留最终裁定。

额外读取（SoT 允许的相邻定义）：`qualified_binding_selection.py` 合同、`control_evaluation_spec.py`、`judgment_search.py`、`facts.py`（`assertion_basis`）、`predicate_binding.py`、`clause_pack.py`、`review_context_v2.py`、`review_method_adoption.py`、`eligibility_review_projection.py`、`component_review.py`、`fact_expectation_gaps.py`、`review_method_evidence.py`、`predicate_binding_candidates.py`、`control_calculation_experiment.py`、`clause_pack` 投影、`assessment.py`。未读项目 `AGENTS.md`。

---

### Highest-impact defect

**已找到的书面判断摘录不能变成谓词真值；若用资格双路一致去放开当前 PJ 拒绝，会把诊断/评分误当成研究者书面判断。**

这是本轮最危险的闭合方式，也是对“复用现有合同”最容易误读的一点。

- 资格核对证明的是来源可接纳与属性对应，不是“原文判断内容已核实”。
- 当前消费者对 `requires_professional_judgment` 一律拒绝可用选择，这在缺少 **检索摘录 ↔ 事实** 接合时是正确保护，不是应删的壳。
- 正面闭环必须先有接合与判断适用性证明，再在**单独的方法评测种类**授权后把 **编码后的 `value`** 交给现有求值器；不得让 `dual_agreement` 或 `requires_professional_judgment` 单独过闸。

---

### Evidence（观察）

**1. `EvidenceRequirement.predicate_ids` 真实存在，不是缺字段。**

```294:308:app/domain/contracts/rules.py
    # Optional explicit attribution to atomic predicates in the same component.
    # Absent/empty keeps legacy unattributed serialization; never infer from fact_type.
    predicate_ids: list[str] = Field(default_factory=list)
```

空列表序列化时删除该字段；非空时必须同时显式来源布尔、禁止流程/控制要求声明官方谓词归属；组件校验引用必须落在本组件唯一谓词上。`binding_qualification_support._source_policies_for_predicate`：空 `predicate_ids` 视为可见壳、状态 `unattributed`，不从单例/`fact_type` 猜配；非空且不含本谓词则跳过。

**2. 书面判断检索只证明覆盖，不证明判断。**

`JudgmentSearchCoverageSummary.professional_judgment_absence_proven` 恒为 `False`。`JudgmentSearchFoundCandidate` 只有页身份 + 通道 + 摘录文本/bbox，**没有 `locator_id` / `fact_id`**。

`_summary_gap_requirements` / `fact_expectation_gaps`：

| 检索状态 | 要求级缺口 |
|---|---|
| 无摘要 / 覆盖不全 | `OBSERVATION_UNVERIFIED` |
| `CANDIDATES_PRESENT` | `OBSERVATION_UNVERIFIED`（已找到待核实） |
| 双读未见且该要求非 `OBSERVED` | `PROFESSIONAL_JUDGMENT` |
| 双读未见但期望已 `OBSERVED` | 仍 `OBSERVATION_UNVERIFIED`（矛盾覆盖不是缺失） |

检索触发是 `required_source_types` 含 `investigator_assessment`，不是原子 `requires_professional_judgment`，也不是组件 `determination_mode`。

**3. 缺失判断进入求值的现有正路径（计算 v7）。**

`missing_judgment_predicates`：任一相关要求缺 `predicate_ids` → 整组返回空（不猜归属）；仅当谓词带 `requires_professional_judgment`、选择为空、且**全部**归属要求均为 `PROFESSIONAL_JUDGMENT` 时，才把该谓词标 `professional_judgment_missing`。`evaluate_component` 将其与 `professional_judgment_unverified` / `observation_unverified` 分开。`REASON_GAPS`：`professional_judgment_missing` → `PROFESSIONAL_JUDGMENT`；`professional_judgment_unverified` → `OBSERVATION_UNVERIFIED`。

**4. 资格维度是来源资格，采信旗标锁死为假。**

`BindingQualificationPairRecord`：`authorized_clinical_adoption` / `clinically_qualified` / `accepted` 均为 `Literal[False]`。`dual_agreement` = 两路 `public_agreement_key()` 相同（`source_admissibility, object_match, attribute_match, denial_scope, temporal_role, direct_operand_usable`）。自由文本原因不参与一致。`QualificationAdoptionAuthorization` 是另一道门：须已保存 `binding-adoption-authorization` gate + 评测清单。

`BindingEvaluationManifest.evaluation_kind` **只有** `binding_semantic_correspondence`。`require_evaluated_binding_method` 按 family/合同/提示/路由/consumer 版本对齐，**不区分书面判断内容评测**。

**5. 现有消费者把 PJ 与多观察全部打成空选择。**

`pair_direct_selection_rejection_reasons`：所有 `structural.pending_checks` 都变成拒绝原因。`candidate_value_shape` 对 **凡** `requires_professional_judgment` 的谓词都追加 `professional_judgment_applicability_unverified`；`assertion_basis` 的 operand_shape 为 `context_only`；可用选择还要求 `attribute_match == "direct"`。

`_select_facts_for_identity`：

- 官方谓词若 `requires_professional_judgment` → 立刻 `investigator_judgment_not_deterministic_value`，不看配对。
- 官方非 PJ：0 条 `no_usable_qualified_pair`；>1 条 `multiple_usable_pairs_without_selection_policy`；恰好 1 条才可用。
- 控制原子 `semantic` / `investigator_judgment` → `determination_mode_*_not_direct_arithmetic`。
- 控制 `observation_policy` 缺或 `unresolved` → `observation_selection_unverified`；`single` 且 ≠1 条 → 同；`any`/`all` → `observation_scope_completeness_unverified`。

选择材料仍 `accepted=False`。`calculate_frozen_review` 把未核实身份映射为空选择 + `unverified_predicate_ids`。

**6. 多观察：官方无政策合同；控制有政策但完整性未证明。**

官方 `AtomicPredicate` 只有 `occurrence_window` 等，**没有** `observation_policy`。`expression._evaluate_atomic`：多值 → `observation_selection_unverified`；`conflict_group_id` → `source_conflict`；不取最新、不取第一条。

控制侧 `ControlObservationPolicy.mode ∈ {single, any, all, unresolved}`，带原文范围。隔离计算 v3 只对**已供**观察做 ANY/ALL，注释写明不证明总体/访视覆盖。正式消费者对 any/all 仍拒绝。`source_validity` 时间用途另挂 `source_validity_requires_policy_evaluation` pending。

**7. `assertion_basis` 已是书面原文载体，但不是求值操作数。**

`ClinicalFactV2` 肯定/否定必须带 `assertion_basis`（对象、原文、locator、哈希）。资格结构核可将 `fact_attribute==assertion_basis` 的 `referenced_value` 取为 `assertion_text`。候选提示已写：检查结果、异常箭头、签字本身不构成书面判断。`evaluate_observed_value` 比较的是 `fact.value`/`unit`/`polarity`，不是断言文本。

**8. 组件 `determination_mode` 仍会扩散 PJ 旗标。**

`determine_component_mode`：任一原子 `requires_professional_judgment` → 整组件 `INVESTIGATOR_JUDGMENT`。投影注释称这只用于页调和，不是求值路由。检索侧已按 `investigator_assessment` 收口。这是上游标注/页策略问题，不是本轮消费主缺口，但会让页读把诊断/评分组件当成书面判断任务。

**9. 已实现、且不应再做成“又一份 accepted=false 汇总”的部分。**

- 要求级双读未见 → 归属谓词 `professional_judgment_missing`（须 `predicate_ids`）。
- 已找到摘录 → `OBSERVATION_UNVERIFIED`，不代入结论。
- 无归属 / 未来或其他节点 → 不猜缺失。
- 双路一致 ≠ 临床采信；授权对象与评测清单已存在。
- 显式选择求值（`evaluate_component` / `evaluate_bound_component_experiment` / 控制实验）已能吃空清单与单事实。
- 控制 `observation_policy` 合同与隔离组合已在。

---

### Inference（推论）

书面判断有四态，现有代码覆盖了前三态的**缺口标记**，缺的是第四态的**生产者+接合+单独授权**：

1. 尚未核对 → `OBSERVATION_UNVERIFIED`
2. 已找到待核实 → `CANDIDATES_PRESENT` / `OBSERVATION_UNVERIFIED`
3. 本次资料未见 → 归属 + 空选择 + `professional_judgment_missing`
4. 已核实对应判断 → **无合同把 found 摘录接到事实，无独立内容评测种类，消费者拒绝所有 PJ 配对**

因此缺口不是“再加一个 accepted=false 汇总”，而是：

| 缺失件 | 现有可复用 | 不能拿来顶替 |
|---|---|---|
| 摘录↔事实接合 | 页身份 + `locator.excerpt` / `locator_excerpt_sha256`；`assertion_basis.locator_id` | `JudgmentSearchFoundCandidate` 自身（无 locator/fact） |
| 判断适用性 | `predicate_ids` + `investigator_assessment` + `source_policy_status=present` + `object_match` + `source_admissibility` + 非空 `assertion_basis` | 仅 `requires_professional_judgment`；仅 `dual_agreement` |
| 判断内容/编码 | 既有语义对应（`value` 的 `attribute_match=direct`）+ 隔离评测 | 资格 `public_agreement_key`；`evaluation_kind=binding_semantic_correspondence` 整单批准 |
| 多观察 | 官方：保持未核实。控制：`ControlObservationPolicy`；any/all 仍须范围完整证明 | 最新值、第一条、默认 ANY/ALL |
| 求值 | 核实后把 **一条** `fact.value` 交给 `evaluate_component` | 用 `assertion_basis` 文本当比较数；新推理器 |

`pending:professional_judgment_applicability_unverified` 被当成配对拒绝，等于把“适用性未核”和“来源不合格”混成同一空选择。应拆原因，**在接合完成前仍不得标 usable**。

授权语义对应方法后，consumer v1 仍只会放出**单观察确定性算术**。这与缺口一致，不能据此宣称书面判断/多观察已闭合。

---

### Recommendation（最小完整闭环，复用现有合同）

不新建调度器、不自动造事实、不把 dual_agreement 当采用。

**步骤 A — 保持现有三态（已实现，勿回退）**

继续：检索覆盖合同、`predicate_ids` 不猜配、空选择缺失、`CANDIDATES_PRESENT` 不代入、资格 `accepted=False`、正式计算拒绝手工夹带（`qualified_binding_selections` 与手工 map 互斥）。

**步骤 B — 新增接合记录，不改 `judgment-search/v1` 身份**

新小合同（建议名仅作规格，Codex 定名）：每条 found 摘录尝试确定性对齐到已发布事实 locator：

- 键：`requirement_id` + 页三项身份 + excerpt 文本哈希 + `locator_id` + `fact_id`
- 成功条件：页身份一致 **且** 摘录等于 `locator.excerpt`（或哈希相等）**且** 该 locator 属于该 fact **且** `assertion_basis` 存在且 `locator_id` 匹配
- 0 条匹配：保持要求级 `OBSERVATION_UNVERIFIED`（摘录还不是事实）
- >1 条匹配：`unresolved`，不取第一条
- 禁止从摘录自动 publish 新事实

`predicate_ids` 从该 `EvidenceRequirement` 投影到接合行；无归属则接合不可用于任何谓词。

**步骤 C — consumer v2：拆适用性，仍默认空选择**

版本：`qualified-binding-selection-consumer/v2`（v1 行为不变）。

- 非 PJ 官方：仍仅 1 条可用配对；>1 → `multiple_usable_pairs_without_selection_policy`（本轮**不**给官方谓词发明 `observation_policy`）
- 控制 `single`：保持；`any`/`all`：本轮仍 `observation_scope_completeness_unverified`（完整性证明不在本闭环）
- PJ：删除“无条件 `investigator_judgment_not_deterministic_value`”
  - 无接合 / 政策非 `present` / 来源类型无 `investigator_assessment` / 无 `assertion_basis` → 空选择 + `professional_judgment_unverified`（不要写成 missing）
  - 适用性满足但 `attribute_match != direct` 于 **`value`**、或操作数是 `assertion_basis`/`record_time` → 仍未核实
  - 适用性满足且恰好 1 条 `value` 直接可用 → 可进入选择清单
  - >1 条 → 多观察未核实，不选最新

`professional_judgment_applicability_unverified` 只在步骤 B+C 的适用性条件全满足时从 pending 清除；**dual_agreement 不得单独清除它**。

**步骤 D — 求值不改算法**

`evaluate_component` / `component-review/v7` 保持。核实后消费的是编码 `value` + 极性 + 单位。`assertion_basis` 只作法源。禁止为 PJ 走数值比较伪装（控制规格已禁止 `requires_professional_judgment` 出现在确定性 `predicate` 上）。

**步骤 E — 采用批准必须换评测种类，不能复用语义对应清单**

扩展 `BindingEvaluationManifest.evaluation_kind`（或并列 manifest）：书面判断适用性/内容对应 ≠ `binding_semantic_correspondence`。

`QualificationAdoptionAuthorization.consumer_algorithm_version` 字面量今日锁 `.../v1`，PJ 可用选择必须绑 v2 + 新 kind。`ReviewMethodApproval.clinical_case_signoff` 保持 `False`。语义对应批准不得激活 PJ 身份。

**步骤 F — 明确不在本闭环**

- 控制 any/all 范围完整性
- 官方“最近一次/复查替代”政策字段（须解构带原文再复用 `ControlObservationPolicy` 形态）
- 历史空 `predicate_ids` 回填（须方案原文再发布）
- 自动采信、注册 API、阶段测试（用户已后置）
- 用组件 `determination_mode` 当谓词语义

---

### Unavoidable decisions for Codex

1. **接合键**：仅用页+摘录相等，还是下一步给 found 候选持久化 `locator_id`？建议本轮只做不可变接合记录，不改 `judgment-search/v1` 字节。
2. **PJ 方法评测**：新 `evaluation_kind` vs 新 job family。建议先新 kind + consumer v2，不新队列。
3. **官方多观察**：本轮保持 >1 未核实，还是现在就给 `AtomicPredicate` 加政策字段？建议保持未核实；无原文政策就加字段等于猜政策。
4. **控制 any/all**：是否挤进本闭环？建议否。

---

### Uncertainty

- 未扫真实 ClausePack 中 `predicate_ids` 与 `investigator_assessment` 的填充率；历史空归属会让缺失判断路径普遍走不通。这是发布/解构问题，不是消费侧可猜的。
- 未验证 found 摘录与 `locator.excerpt` 在现网是否逐字一致（OCR/手写通道可能失败，失败应保持未核实）。
- `FrozenFactRecord` 不强制 `assertion_basis`，若冻结投影丢断言，接合会失败。
- 未跑运行时；以上为源码合同观察。
- 组件级 `INVESTIGATOR_JUDGMENT` 扩散对页读的实际影响未在本任务验证。

---

### Objections

1. **反对**把 `dual_agreement` 或放开 PJ pending 当作“已核实判断”。那会把诊断/评分事实送进求值。
2. **反对**再堆一层仅 `accepted=false` 的资格汇总来宣布 T5 判断缺口闭合。三态缺口已在；缺的是接合 + 独立评测 kind + consumer v2。
3. **反对**给官方谓词默认 ANY/ALL/最新。与 §17.1 / §17.2 直接冲突。
4. **反对**用 `requires_professional_judgment` 或组件 `determination_mode` 当作检索义务或语义真理。检索已正确绑 `investigator_assessment`。
5. **反对**用 `assertion_basis` 文本做 `evaluate_observed_value` 操作数；文本是法源，比较的是编码 `value`。
6. **反对**让现有 `binding_semantic_correspondence` 批准覆盖 PJ 身份。

---

### Bounded questions for Codex

1. 是否确认：**禁止**从 found 摘录自动创建 `ClinicalFact`，无匹配事实时保持 `OBSERVATION_UNVERIFIED`？
2. PJ 正面消费是否必须新 `evaluation_kind`，语义对应批准明确不覆盖？
3. 官方多观察本轮是否冻结为“>1 一律未核实”，政策字段留给解构有原文之后？
4. 历史无 `predicate_ids` 的已发布规则：保持永久未归属，还是另开带原文的规则再发布？消费侧不得猜配。

**安全暂行路径（上述未答前）：** 不启用 PJ 可用选择；不多观察猜政策；不把 dual_agreement 当采用；规格按步骤 B–E 记录，待 Codex 裁定 1–3 后再改 consumer 字面量。计算 v7 缺失路径与资格 v1 确定性单观察路径可继续作为未启用链存在。
