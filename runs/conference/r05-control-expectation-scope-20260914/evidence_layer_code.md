源审完成。本轮完整读取了组合器、四个新合同/投影/服务文件、候选读取器与 expression.py 的时间算术抽取，并对照父级 DNF 合同与水合逻辑逐条核验。以下为报告。

---

# Conference Output: r05-control-expectation-scope-20260914 - evidence_single_object（续审：控制层求值边界源审）

## Output

**先更正前轮错误结论**：控制来源政策未断言（None）**现在可以持久化**——两个政策字段已改为 `bool | None`（app/domain/contracts/rules.py:287-288；evidence.py:160-161），仓储校验是与发布派生政策的**精确等值**比较，`None == None` 通过（app/storage/repositories.py:1671-1681）；模板侧仅要求非控制来源不得携带 None/控制字段（evidence.py:185-198）。我此前“unknown 政策无法入库”的说法基于旧源，不成立。

### 边界核验（源审通过，仅源审）
- **输入身份绑定**：`ControlBindingFrozenInput` 以内容哈希绑定完整发布+事实快照哈希，并核对 project/规则修订/期别一致（control_atom_binding.py:42-79）；服务侧复用 §17.1.1 冻结输入、无第二选择管线（control_binding_input.py:13-27）。
- **候选仅候选**：atom_identity 以 enum 锁定当前目录身份、结果集必须恰好完整、事实/定位/属性必须在冻结范围内、空候选必须说明 uncertainty（control_binding_candidates.py:31-53、92-111）；提示词明令禁止类别匹配、阈值计算与最终判定（:55-72）。未发现任何发布绑定的路径。
- **未知例外/适用性**：例外 UNKNOWN 经 `NOT ANY` 保持分支 UNKNOWN（挂起），不解除触发、也不误阻断（control_layer_evaluation.py:92-96）；无适用层→TRUE，UNKNOWN 逐层传播并进入 activation（:73-76、127）。与 §17.1 一致。
- **双向链接**：水合从例外侧单向派生 `activated_by`，结构上不可能出现单向悬挂（protocol_controls.py:2874-2880）；组合器再校验互逆（control_layer_evaluation.py:114-115）。替代义务前提正确使用**豁免前**触发真值（:109-110 注释明确）。
- **时间算术抽取**：公开 `evaluate_time_constraint` 只消费真实 DateValue 对，无事实/谓词构造（expression.py:298 起）；`_evaluate_time` 传入 `fact.effective_date` 真实日期（:280-295）。
- **混合强度不折叠成最终结论**：输出合同只有中间真值/激活，无 eligibility 字段（control_layer_evaluation.py:16-26），模块 docstring 明示不转排除。

### 真实缺陷（按优先级，附最小修复）
**D1（高）控制级时间约束被静默丢弃。** `ProtocolReviewControl.control_time_constraint`（protocol_controls.py:1573）与 DNF 层可并存（无校验禁止），而 `compose_control_layers` 既不消费也不拒绝它（control_layer_evaluation.py 全文无引用）——冻结的来源闭合时间语义被无声略过。最小修复：组合器对非空 `control_time_constraint` 直接 raise（沿用 :55-56 的 fail-closed 风格），待锚点语义定义后再接显式窗口真值入参。
**D2（中）替代义务的豁免∩作用域为空时静默失活。** 例外豁免 {T1}、替代组 scoped {T2} 时 `affected` 为空，`_any(())`=FALSE → route FALSE → 替代义务永不激活（control_layer_evaluation.py:116-121）。水合只查序位不查相交（protocol_controls.py:2875-2877），该状态可构造。其他链接不一致都 raise（:88-89、104-107、114-115），此处应同样 raise 而非静默 FALSE。最小修复：当激活例外 waives 非空且组 applies 非空而交集为空时，按合同不一致拒绝。
**D3（中）`obligation_group_truth` 跨 modality/kind 混合求 ALL。** 组内 RECOMMENDED 原子 FALSE 会拉低整组真值（:128），而 PROHIBIT/RECORD 类原子的"真值"语义各不相同——组级单一真值是潜在的折叠面。最小修复：输出增每原子 `(layer, modality, kind)` 回显（或强制/建议分开两列），并在字段注释明示消费者不得以组真值作阻断。
**D4（低·前向）None 政策在 `_coverage_verdict` 中将不对称坍缩。** `not None`=True（宽松）而 `None` 为假（转述判 none，严格）（app/projections/evidence_expectations.py:151-167）。受 :219-222 整体拒绝保护当前不可达；**撤销该守卫前必须先给 None 一个显式"未断言"分支**，否则 unknown 政策会静默变成一半宽松一半严格。
**D5（低）无触发时未限定例外的语义是组合器解释而非合同规定。** 有触发时水合强制每例外声明豁免范围（protocol_controls.py:2866-2869）；无触发时未限定例外“成立即挂起默认路径”（control_layer_evaluation.py:124）仅由组合器定义。最小修复：在该行注释或模块 docstring 钉死此语义，避免未来实现漂移。

### 目前不能视为最终结果的清单
1. `atom_truths` 的生产来源尚不存在——只有候选通道，没有“控制原子已验证绑定”的发布步骤与消费者；组合器在正式链路中尚不可驱动。
2. 组合器输出是中间真值：最终逐原子 modality 处置层（阻断/建议分离）未建；报告/前端不得以 `obligation_group_truth` 或 activation 作符合/不符合或排除。
3. `control_validity_constraint` 尚无消费方；接入时必须传事实**日期区间**（DateValue/PartialDateRange），不得把区间捏成点日期喂 `evaluate_time_constraint`。
4. 受试者期望对控制模板仍整体拒绝（evidence_expectations.py:219-222）；完整审核守卫仍在（frozen_review_calculation.py:37-38）——两者撤销分别以 D4 与最终集中验证为前置。

### 未执行的最终验证
本轮纯源审：未运行任何测试/求值真值表枚举、未验证 prompt v(control-binding-candidates/v1) 的模型实际输出、未核实发布仓储“每修订唯一目录”的查询实现、未做 §17.1.1 隔离评测、未做迁移/运行时校验。以上均留待构建完成后的集中验证，不因源审通过而视作已验收。
