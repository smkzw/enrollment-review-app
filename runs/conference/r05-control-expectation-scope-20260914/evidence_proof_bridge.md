源审完成。核读了新执行器与父生命周期、候选读取器当前版、冻结输入合同、组合器、原子与谓词定义、§17.1.1/§17.3 及隔离实验入口。以下为报告。

---

# Conference Output: r05-control-expectation-scope-20260914 - evidence_single_object（源审：证明→计算桥）

## Output

### 一、新执行器生命周期审查（无阻塞性回归）
`ControlBindingJobExecutor` 继承 `PredicateBindingJobExecutor`，复用取消/原始回执/检查点/提交期双重复核（app/services/control_binding_job.py:55-90；父类 app/services/predicate_binding_job.py:97-104、143-180）：读步落 `accepted:False` 候选工件，summary 步要求双 lane 检查点同哈希且 `status=="unverified"`，`_verify_current` 以重建哈希不一致拒绝（control_binding_job.py:64-72），payload 自身哈希由合同校验闭环（control_atom_binding.py:66-67）。`read_control_candidates` 复用 `read_candidate_payload`，故 `PredicateCandidateReadError` 能被父类捕获（control_binding_candidates.py:132-150；predicate_binding_job.py:213）——错误类型链无断裂。注册面：执行器与入队函数仅在自身模块出现，无正常应用入口——符合“仅显式候选入口”。两处非阻塞发现：**R1** 继承 `__call__` 使控制作业的版本/路由/回执失败仍报 `PREDICATE_*` 错误码（predicate_binding_job.py:149、151、167、174），运维归因歧义，最小修复为子类覆写码前缀；**R2** 控制侧 `_candidate_artifact` 无父类的 `operand_checks` 形状核验（control_binding_job.py:81-90 vs predicate_binding_job.py:129-140）——今天没有类型化规格可核对，尚非缺陷，但正是下述桥的天然插入点。

### 二、AtomicPredicate 可复用性判定
**可复用，且只需显式选择路径。** `_evaluate_atomic(expression, context, fact_ids)` 在传入显式事实清单时不做任何类别匹配，只做数值/单位/极性/时间窗判定（app/domain/expression.py:448-537）；类别假设只存在于无清单时的 `subject.attribute` fact_type/别名回退（:451-459，R01 未闭）。`evaluate_bound_component_experiment`（:576-616）已示范“哈希冻结组件+上下文+逐谓词显式清单”的合法消费形态。控制条件原子携带的 `time_constraint` 与规则侧是同一类型（protocol_controls.py:853/895 引自 rules），直接落入 `AtomicExpression.time_constraint`（rules.py:247-250）——时间机制零改动复用。

**精确缺失的语义（阻碍直接复用的全部清单）**：
1. **判定模式判别器**：AtomicPredicate 隐含“值比较/存在”，控制原子需要显式三态——确定性操作数 / 语义关系 / 研究者书面判断。规则侧已有条款级 `DeterminationMode` 先例（clause_pack.py:17-20、35），原子级缺失。
2. **义务种类→可求值性映射**：`PROHIBIT_EVENT/PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE/REACH_CONDITION` 可作谓词求值（禁止类=事件存在性求值后在处置层取反）；`COMPLETE_OR_VERIFY/SCHEDULE_OR_VERIFY_VISIT/SELECT_BASELINE_VALUE/MUST_RECORD/MUST_PROFESSIONAL_ASSESSMENT/VERIFY_RESULT_VALIDITY` 是**履约/覆盖义务**，不是真值命题——必须走证据覆盖与判断检索通道，禁止伪装成谓词。
3. **操作数逐字来源**：value/unit 必须逐字引自原子 source_excerpts——复用 `FrozenPredicateIdentity.source_status: verbatim|unverified` 先例（predicate_binding.py:131、147-152）。
4. **时间用途声明**：求值成员窗（TimeConstraint 进 AtomicExpression）与来源有效期（已在 `ControlEvidenceSourcePolicy` 独立）不得互推；义务的 `temporal_scope/prospective_period` 与 AtomicPredicate 的 `occurrence_window/prospective_*` 字段形态对齐（rules.py:196-198），映射属发布时断言，非求值时推导。

### 三、最小桥方案（只加一个版本化合同，接既有消费者）
**Phase A（解构期类型化求值规格，仅新发布强制）**：`ControlConditionAtomDraft/ControlObligationAtomDraft` 增可选 `evaluation`：`{mode: deterministic|semantic|investigator_judgment, predicate?: <AtomicPredicate 形状含操作数逐字 span>, time_purpose}`；序列化缺省剔除保历史字节（既有模式，protocol_controls.py:1414-1423）。wire v4/提示 v2.0 由模型**带原文依据提出**规格；门禁只做结构校验：deterministic ⇒ 谓词完整且操作数 span ⊆ 原子摘录逐字；禁止类/REACH_CONDITION ⇒ deterministic 或 semantic；履约类义务 ⇒ 不得声明 deterministic；investigator_judgment 仅限 `requires_professional_judgment` 原子（并受 §17.2 不扩散约束）。代码不做散文转谓词，求值时不补造。
**Phase B（受试者证据选择）**：候选仍由本次执行器产出（唯一模型输入）；核验代码在 `_candidate_artifact` 增加对 deterministic 规格的 operand 形状核对（R2 插入点），通过后写入**版本化已验证绑定记录**：`FrozenControlAtomIdentity` + 选择 fact_ids/属性 + 规格哈希 + 回执——`accepted:false` 常态，翻转 true 只经 §17.1.1 隔离评测与接入批准。两个一致候选 ≠ 临床接受证明。
**Phase C（接通现有消费者）**：薄适配器 `evaluate_control_atoms`：按发布规格逐原子构造 `AtomicExpression`，显式 fact_ids 走同一 `_evaluate_atomic`（同实验入口的冻结方式），输出 `atom_truths` 直接喂 `compose_control_layers`（control_layer_evaluation.py:47-68 已是现成消费者，签名未变）。semantic 原子在隔离评测通过前一律 UNKNOWN（不是 false）；investigator_judgment 原子不经此求值，走判断检索+`professional_judgment` 报告路径；混合 modality 由处置层按原子施加（前轮已定，不进求值）。

### 四、现在可建 vs 保持禁用
**可建**：Phase A 合同+门禁+wire；候选 operand 形状核对；Phase C 适配器以**隔离形态**实现（镜像 `evaluate_bound_component_experiment`，不注册、不进 API）；组合器消费已是纯函数。**禁用至最终集中验证/评测批准**：任何生产路径消费 atom_truths（两守卫 frozen_review_calculation.py:37-38、evidence_expectations.py:219-222 保持）；accepted=true 翻转；适用性投影接入；semantic 模式采信。

### 五、源码不能裁决处（不发明默认）
1. semantic 模式的“已验证语义对应”接受标准——属 §17.1.1 隔离评测与用户接入确认边界，本报告不定义。
2. deterministic 规格由模型提出后是否需要第二模型独立复核（§17.1.1 有双源语）还是代码逐字核对即足——留 Codex/评测裁决。
3. 履约类义务的“完成”判定最终由覆盖通道还是人工办结通道闭合——T5 范围。

### 未验证部分
纯源审：未运行作业/评测/模型；执行器未在真实 JobRunner 上走查；wire v4 尚不存在（属建议）；两守卫存在性仅由源码确认。不构成临床或最终验收结论。
