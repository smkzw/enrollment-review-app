全部五个核对点与接线证据已闭合。以下为本轮审阅报告。

# Conference Output: r05-repeat-binding-review-20260915 - evidence_single_object（第二轮，D1/D3 修订与控制族增量）

## Output

### 一、实际缺陷（按影响排序）

**F1（高——主链路断裂；两处 Literal 滞后于 v5）**
提示版本常量已升为 `"binding-qualification/v5"`（`app/domain/contracts/binding_qualification.py:27`），但两个消费合同的 Literal 未同步加入 v5：

- `app/domain/contracts/binding_qualification.py:312`：`BindingQualificationSummary.prompt_version` 的 Literal 仍为 `["binding-qualification/v2","/v3","/v4"]`。而 `compose_qualification_summary` 在 `app/services/binding_qualification_support.py:881` 显式写入 `"prompt_version": BINDING_QUALIFICATION_PROMPT_VERSION`（=v5），`:896` `BindingQualificationSummary.model_validate(material)` 对显式传入值执行 Literal 校验——v5 不在集合，**每次资格任务 summary 组装即抛 pydantic ValidationError**，新资格任务无法完成。
- `app/domain/contracts/qualified_binding_selection.py:51`：`QualificationAdoptionAuthorization.qualification_prompt_version` Literal 同样不含 v5。`build_receipt_verified_qualified_binding_selections` 入口（`app/services/qualified_binding_selection.py:399-401`）做 `model_validate(authorization.model_dump(mode="json"))` round-trip——直接构造不传该字段时 pydantic 默认不校验默认值（对象可创建、字段值为 v5），但 dump 会输出 v5，回读显式校验即被拒——**任何正式选择消费在入口崩**，且比直接构造失败更隐蔽。

证据链：常量 v5（合同 :27）↔ Literal 截止 v4（:312；授权 :51）↔ 显式传入/round-trip 消费点（support :881,:896；services :399-401）。`_validate_authorization` 的 `qualification_prompt_version != verified["prompt_version"]` 比对逻辑本身正确，问题纯在合同字面量。
最小修正：两个 Literal 集合补入 `"binding-qualification/v5"`（一处合同、一处授权合同，各一行）。

**F2（低——提示与材料不一致）**
v5 资格提示（`app/llm/binding_qualification.py:158`）写明 "repeat_owner_predicate_ids仅说明所关联的复查规则"，但控制族 `_parent_source_context`（support :328-354）只附加 `repeat_trigger_condition` 与 `condition_id`，**没有** owner 对应物（谓词族有 `repeat_owner_predicate_ids`，:319-325）。控制族配对的提示引用了一个其材料中不存在的字段名。最小修正：提示按族区分表述，或给控制族补 `repeat_owner_atom_ids`（由 `evaluation.repeat_scheme.trigger_condition_id` 反查）。

**F3（低——合同宽松，无消费者风险）**
`ClausePack.validate_control_scope`（`app/domain/contracts/clause_pack.py:71-74`）禁止 v1/v2 夹带复查条件，但不禁止 “v3 但无复查条件”。投影层不会产生该组合（`clause_pack.py:132-134` 仅在存在复查条件时升 v3），手工构造的此类 pack 合法但无实际读取风险（哈希内容寻址）。建议在案记录或加一条对称校验。

### 二、已确认边界（按分派核对点）

**1. ClausePack v3（上轮 D1 修复成立）**：合同新增 `repeat_trigger_conditions` 字段且空时序列化省略（`clause_pack.py:34,38-43`，旧 v1/v2 字节不变）；投影透传（`projections/clause_pack.py:123`）并仅按“是否存在复查条件”升 v3、有补充目录时 v3 可携带目录、无目录 v3 合法（:132-152；合同 :68-70 保持 v1/v2 语义、:71-74 禁旧版夹带）；`clause_to_rule_component` 透传（`eligibility_review_projection.py:812`）。条件与来源要求（含 `predicate_ids` 引用复查谓词）经同构类型原样往返，重组侧 `RuleComponent` 校验因条件在场而通过（`rules.py:486-514` 与 :447-459 的上轮两个失败模式均消除）。

**2. binding-qualification/v5 与选择消费 v16**：提示 :157-160 补齐 role/layer=repeat_trigger 语义边界（旁置复查条件、不继承来源资格、不反推触发成立、不决定复查获准与结果采用）。选择层 expected 含旁置（`qualified_binding_selection.py:208`）、outcomes 保留旁置（:696-704 无过滤），`control_map` 排除 repeat_trigger 层（:705-706），谓词族维持 :596-597 排除。`repeat_relation_unverified` 仍不可豁免（`_AUTHORIZATION_WAIVED_REASONS` :44-47 仅两项；`_select_with_ordering` :280-282/:290-291；:555-557/:665-667）。（该路径因 F1 当前不可达。）

**3. 控制冻结身份与四层投递**：`FrozenControlAtomIdentity.condition_id` 进入哈希材料且序列化省略 None 保持旧身份字节（`control_atom_binding.py:23,35-40,51`）；`project_control_atom_identities` 默认仅四层、`include_repeat_triggers=True` 投影旁置并做 `(protocol_control_id, atom_id)` 全局唯一检查（`control_atom_binding_input.py:8-31`）。候选（`control_binding_candidates.py:60,126-131` 强制完整覆盖）、资格材料/政策/父上下文/结构核对（support :171,:237,:328,:602）、命题输入（`proposition_evidence_input.py:31`）、书面判断（`judgment_content_input.py:44-56`，经 `_condition_material` 补入的 `condition_id`，support :246）、选择（:208,:439,:453）、条件算术（`control_operand_calculation.py:42`）**全部 True 口径，无漏接的身份查找**。条件组不混同：`_source_policies_for_control` 用 `identity.reference.key` 与 `ref.key` 三/四元组精确匹配（support :176,:183），跨条件同 (group,atom) 位置不会互撞。最终计算只投四层：`frozen_review_calculation.py:196-208` 以 `final_identities = control_selections`（四层）过滤 ordering/relations/gaps/unverified；`evaluate_control_layers_experiment` 的 identities 默认四层且 selections 键集须恰好相等（`control_calculation_experiment.py:157-160`），旁置关系/未决理由即使误传也会在此被拒（fail-closed 双保险）。

**4. ControlEvidenceAtomReference 与 compose_control_layers**：仅 repeat_trigger 要求且只允许 condition_id（`control_evidence_dependency.py:24-28`）；key 普通/复查为三/四元组（:9-11）；发布 gate 以默认 `require_explicit=True` 强制每项最低证据显式归属（`protocol_control_gate.py:3993,:4289`）；判断原件关联与资格政策消费统一走 key 函数（`judgment_content_input.py:45-52`；support :176-184）。`compose_control_layers` 对旁置资料引用恒记 UNKNOWN、注释明确"不是第五层"（`control_layer_evaluation.py:170-177`），`atom_truths` 键集须恰为四层（:81-90），activation/remaining 只消费四层原子——未发现过度阻断或误消解链条；旁置原子的确定性算术仅进候选工件且 `accepted=False`（`control_binding_job.py:103-144`）。

**5. 控制水合与版本**：水合原子 id 命名空间携带 `repeat_condition_id`（`protocol_controls.py:2906-2911`）；`validate_control_repeat_conditions` 补跨条件全局原子唯一性（:1232-1238；草稿层因无 id 空转，水合 :1433 与发布 :1722 生效）、复查条件禁止 waives/activates/嵌套、来源逐字闭合、不得夹带未引用条件（:1249-1263）。waives：草稿层完整边界校验（:1366-1390），水合层非例外层携带即拒（:2896-2903）、有触发 DNF 时例外必须声明作用分支（:3000-3003）、waives ⊆ triggers（`control_layer_evaluation.py:113-114`）——稿件/水合校验等价对齐。版本：wire12（`protocol_control_deconstructor.py:115`，合同 Literal :810 拒旧 wire）、prompt2.8（:117）、执行10（`protocol_control_execution.py:115`，:839 版本不匹配即拒）、gate12（`protocol_control_gate.py:58`，execution :966 检查点比对）、控制候选 v3（`control_binding_candidates.py:26`；job 合同 v6 且 spec 表用动态常量，support :74-81）。旧响应不能冒充新方法：候选/资格 payload 版本强制当前值（support :370-371,:1016）+ 消息哈希回执重建 + 评测 manifest 逐字段比对（`review_method_evidence.py:11-27`）——但注意因 F1，v5 资格链当前无法产出新任务结果，旧 v4 任务结果则被显式拒绝。

**复查采用仍未实现**（已声明缺口，非隐式开启）：`result_use`/`result_combine` 无任何计算消费者；旁置身份的 usable 结果仅存 `identity_outcomes` 与候选工件。

### 三、未运行验证

- 本轮完全只读：未运行测试/应用/模型/浏览器，未做内存构造（遵守本轮收紧边界；上轮 D1 的内存构造复现未重复）。
- F1 的触发判定是源码级推断，依据 pydantic v2 语义（显式传入值必经 Literal 校验；`validate_default=False` 使默认值绕过校验、故 round-trip 失败而直接构造不失败）——未运行验证，建议修复后以一次 `model_validate` 构造冒烟确认。
- 上轮 D1 修复的确认是纯源码审读（三层透传链与同构类型闭合），未做往返运行验证。
- `stable_protocol_control_atom_id` 内部实现、`protocol_control_gate.py` 全文（约 4700 行）未通读，仅核对版本常量、依赖校验调用点与相关片段；`tests/` 中 `repeat_trigger` 仍零引用（上轮 D2 观察未变，按约定回归集中在产品完成后执行）。

**致 Codex 的有界问题**：F1 的两处 Literal 补 v5 是否随本轮直接修（一行×2），还是与 F2 提示措辞一并处理？若 F1 不修，v5 资格链与选择消费在当前工作树上不可用，本轮其余已确认边界均无法在运行中到达。
