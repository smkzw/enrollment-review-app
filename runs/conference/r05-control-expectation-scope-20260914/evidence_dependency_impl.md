源审完成。核验链路：新依赖合同 → 证据/草稿合同与序列化 → 水合 → 线 v3/提示 1.9/草稿转换 → 门禁候选与发布两侧校验 → 执行 v3 与状态门 → 投影 → 前端解码与渲染。以下为报告。

---

# Conference Output: r05-control-expectation-scope-20260914 - evidence_single_object（源审：证据依赖接线）

## Output

### 一、边界核验（源审通过项）
- **合同与历史字节**：`ControlEvidenceAtomReference` 为 `(layer, group_index, atom_index)`、strict 非负整数（control_evidence_dependency.py:9-18）；Draft/Evidence/投影三处序列化在空时剔除字段，历史载荷不变（protocol_controls.py:1417-1422、1449-1454；control_evidence_requirements.py:43-44）。校验只查存在性/唯一性，明确不做语义证明（control_evidence_dependency.py:21-38）。
- **次序保持**：水合按 `enumerate` 保序复制证据与 atom_refs（protocol_controls.py:2934-2949），表达式组同样按序构建；引用序位以发布哈希绑定，不可跨目录漂移。门禁候选侧（草稿位）与发布侧（已水合控制）双端校验（protocol_control_gate.py:3967-3972、4257-4263），两端序位一致。
- **线 v3/提示 1.9**：wire 证据字段 `atom_refs` min_length=1（protocol_control_deconstructor.py:632）；提示词规定零基序位、一项资料可对多原子、禁止仅按类型关联，并要求**适用/触发/例外的判定资料也必须关联、不得等条件成立后才收集**（:1393-1396）；草稿转换原样保序传递（:2475-2486）。JSON schema 经 `model_json_schema()` 生成，嵌套引用类型可正常转换（:1148）。
- **执行 v3**：作业载荷盖版本章（protocol_control_execution.py:717），状态 API 拒绝版本不符的旧作业作为发布依据（protocol_control_status.py:169-174）——v2 在途作业失效属 fail-closed，历史已发布目录不受影响。
- **投影**：`require_explicit=False` 容忍历史空引用、不发明链接（control_evidence_requirements.py:58）；`source_span_ids` 已改为取 `source_policy.source_span_ids`（:91，修正了此前控制级并集过粗的问题）；`requirement_id` 不含 refs——同一不可变发布内内容恒定，无碰撞风险（:70-76）。
- **前端**：引用解码强制安全整数、组/原子越界即 invalid、重复引用拒绝（protocolControlView.ts:225-238，`object(undefined)`→invalid :49-51）；展示仅人读标签+逐字 statement，无 layer 枚举/索引/ID 工程标识；空引用诚实显示“尚未整理”（ProtocolControlPanel.tsx:73-77）；政策三态文本与约束配对校验（protocolControlView.ts:245-259）。政策与引用身份分别渲染，未混淆。
- 两处守卫仍在（frozen_review_calculation.py:37-38；evidence_expectations.py:219-222）；本变更未实现任何受试者适用性判定。

### 二、关键语义评估：先决证据 vs 激活义务证据
**结论：现有关联对下一个消费者已足够，不缺必须新增的语义关系，不需要新框架或冗余状态表。** 分类完全可由三方连接推导：atom_refs（layer+组位）× 发布控制（`obligation_expression.groups[g].obligation_group_id` 按位取用）× `ControlLayerEvaluation`（组激活态，control_layer_evaluation.py:23）× 组内原子 modality。共享期望通道（shared_control_requirements → EvidenceRequirement/模板）确实**不携带** atom_refs（control_evidence_requirements.py:102-123），但 `ControlEvidenceOrigin` 保留 (publication_id, protocol_control_id, evidence_key) 完整连接键（control_evidence_origin.py:9-14），且冻结上下文含完整 control_publication——任何消费者都能回连，数据无损。不应把 refs 复制进共享行（会造平行表）。

**修正后的缺口判定式**（替代我此前“applicability=TRUE 即放开 absent”的过度简化）：证据项 E 的缺失要成为 absent 判定，须同时满足：① 组合器 applicability=TRUE；② E 的 obligation 层引用所指每个组 g 的 `obligation_group_activation[g]`=TRUE（触发分支生效且未被豁免；替代组按例外激活）；③ 所引义务原子逐个 modality=MANDATORY（RECOMMENDED/BEST_EFFORT 永远只作建议项）；④ E 不再承担先决职能——若 E 还引用 applicability/trigger/exception 原子且其中仍有 UNKNOWN，则 E 缺失只能呈现“条件判定资料未收、适用性未确认”，不得记 absent（反循环：判定条件的资料收集不依赖条件已证明，作者侧提示 :1395 已令关联，消费侧按此式执行）。观察到 E（正向覆盖）永不证明义务适用。条件原子无 refs 也不是缺陷：它们可由控制原子绑定通道（既有事实）解决，强制每原子配引用会逼造链接。

### 三、发现（仅源审级别，无紧急缺陷）
**F1（低·一致性说明）**：投影对 refs 历史宽容但对 `source_policy is None` 直接拒绝（control_evidence_requirements.py:63-64）——政策前旧目录完全不可投影。这是有意的 fail-closed（禁止默认值顶替），但与 refs 的宽容策略不对称，建议在模块 docstring 一句话钉死“政策强制、引用宽容”的差异理由，防未来误改。
**F2（低）**：`validate_control_evidence_dependencies` 允许多个证据项引用同一原子、也允许一项证据多原子（仅项内去重，:30-32）——与提示词一致，属正确设计；消费侧需按“任一已决条件原子可解除其先决挂起”处理多对多。
**F3（记录）**：反循环约束目前只存在于提示词（:1393-1396）与上述消费式，代码尚无任何执行点（适用性未实现）——这是下一个消费者的实现义务，不是本变更缺陷。

### 未验证部分
纯源审：未运行测试/模型/前端；提示 v1.9 的模型实际行为未测；发布→投影→仓储全链未在真实数据上走通；两守卫存在性仅由源码确认。不构成临床或最终验收结论。
