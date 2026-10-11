收到同会话定向续审（捕获簿记修正 + 拒绝补读重开）。只读、不委派、不落盘（Explore/Plan 子代理与"不委派"边界冲突；计划文件不写）。先定位 delta 新符号。

读取恢复绑定与 runner 空列表路径、以及序列位置门（对齐核验）。

# Conference Output: rv1006-source-scope-resume-review-20261011 - evidence_single_object

## Output

同会话定向续审（本轮机读：6 次定义读取＋5 次符号定位）。未改文件、未运行测试、未委派（Explore/Plan 子代理与"不委派"边界冲突；计划文件未写）、未读临床/DB/env/tmp/私有回执；未复读历史或旧叙述。HEAD 06b4037b 与四文件清单未做 git 校验（无写/无 git 权限），按冻结工作树实际内容直读。**同产品模型家族、同恢复上下文，独立性折减；非医学批准；临床与集成由 Owner 负责。**

---

### 一、捕获簿记修正：是否把缺失/重叠/外来来源新判为完整

**[代码事实] 新块仅计同单元、物理在前的字面先决条件**（`protocol_control_source_interpretation.py:329-343`）：
- 仅遍历本单元 `indexes`；`eligibility_sequence != "after_eligibility_decision"` 或 `eligibility_sequence_context is not None` → 跳过（`:331-333`，跨单元见证不走此块）。
- `bounds = locate(unit.excerpt, eligibility_sequence_quote or "")`、`action = locate(unit.excerpt, quoted_text)`；`bounds is None or action is None or bounds[1] > action[0]` → 直接 False（`:334-337`）。与解释门 `:3444-3457` 的 `boundary in source[:action_start]` **同义**（先决条件必须整体位于动作之前；空/未定位即拒）。
- 计入方式：已被既有区间/加入项包含→跳过；**部分重叠→False**（`:340-342`）；否则追加进 `extra`（仅覆盖簿记）。循环内包含检查基于增长中的 `[*ranges,*extra]`，同一先决被两条陈述引用不会重复追加。
- 最终仲裁仍是原函数 `source_statement_ranges_cover_unit`（`protocol_control_gate.py:5074-5095`：区间外只允许空白/分隔符；`end <= start`、`start < cursor` 重叠/逆序、越界一律 False）。
**反例与结论**：先决缺失→`:336` False；先决在动作之后→`:336` False；跨单元条件→不在此计数且须过 `_validate_sequence_context`（`:3448-3453`）；部分重叠→`:341-342` False；未引用的真实词→仲裁 False。**没有把缺失/重叠/外来来源新判为完整的路径**；该函数只读，不改任何陈述/语义字段（注释 `:338-339` 明示"计数不等于把先决指派给其他陈述"）。

### 二、拒绝补读重开：采纳/重读/预算边界

**[代码事实] 默认停止仍在**（`protocol_control_execution.py:2794-2801`）：仅 `transport_failed`（精确错误类＋outcome）或 **`capture_validation_changed=True` 时的 rejected_capture**（精确 `SOURCE_UNIT_QUOTE_COMPLETION_INVALID`＋schema_invalid）可继续，否则 `SOURCE_UNIT_QUOTE_COMPLETION_STOPPED`。`capture_validation_changed` 来自 `saved_components.validator_version != current_components["validator_version"]`（`:2951-2953`）——**同 validator 的拒绝补读保持停止**。
新重开分支（`:2833-2848`）四个绑定齐备才放行：① `remaining` 必须为空（新校验下所有计划单元已完整，否则 `:2834-2835` 再抛停止）；② `proof.source_sha256 == sha(当前解释)`（**原来源未变**）；③ `raw = last.raw_output_text` 非空且其 sha 等于该尝试保存的 `raw_output_sha256`（**实际被拒回执绑定**）；④ 输出新证明 `phase5/source-capture-revalidated-proof/v1`、`source_unit_completion_ids: []`、`rejected_completion_sha256`、`adopted: False`，并 `**proof` 透传（含 `source_repair_limit`）。被拒答复**只做哈希，从不解析/应用**。
**[代码事实] 旧语义无法回归**：上游强制保存记录中 `partial_wire/source_target_review/source_statement_coverage/source_candidate_alignment` 全为空（`:2804-2809`），历史账必须存在且末条与尝试一致（`:2827-2829`）；`_validated_deep_partial_source` 另验冻结组件/线路/提示/修复合同，且要求 `not changed_components` 与当前 repair contract（`:2936-2957`，组件相等语义由 `_same_deep_components_with_current_gate` 判定）。
**答案**：拒绝语义输出不能成为采用或被解析；仅哈希与空计划可见。原来源一经改变即 `:2837-2838` 抛错；重开**不发生重读**（空计划＋历史 `seen_unit_completions` 记录，见下），额度由原 `source_repair_limit`＋历史计数保持，无重置路径。

### 三、空补读列表是否真的到达"全新作者"

**[代码事实]**：种子经执行层 `resume_source_unit_completion_ids=(seed_proof or {}).get("source_unit_completion_ids", ())`（`:4752-4757`）传入 runner；runner `if resume_source_unit_completion_ids:`（`protocol_control_deconstructor.py:7806`）为**空则整块跳过**——不发补读，不恢复 `partial_wire/review/coverage/alignment`（它们已被清空并受 `:2804-2809` 约束），随后走正常作者+核对+完整门路径。历史回放（`:7744-7805`）只做见证收集：被拒补读记入 `seen_unit_completions`（`:7780-7785`，防止同单元/同前置重复补读）；`source_repairs` 计入该历史尝试（`:7803-7805`，额度不重置）。非空路径（`:7806-7842`）另有严格边界：仅允许"有源草稿、无线稿/核对/对齐/覆盖"、单元唯一且确缺、缺额用尽即拒（`:7812-7816、7821-7822、7835-7837`）——该路径与本次重开互斥。
**答案**：是。空列表通过构造与 runner 分支确定性地跳过补读，且无旧结论可恢复；被拒输出不进入解析面。**[推断]** 其后的作者+完整门为既有正常流（`:7843` 之后本轮未读，见限制）。

---

### 可达缺陷（按严重度）与建议

**必修**：在已读边界内**未发现决定性缺陷**；三条防线（定位/先后对齐、四重绑定、空计划到新作者）在当前源码上闭合。**不主张临床正确性。**
**建议**：
1. **重开绑定的是粗粒度 validator 串**（`:2951-2953` 取拼接后的 `validator_version`）：任一无关校验器升版都会使"旧拒绝补读"具备重开资格（仍需源未变＋全部单元已完整）。若要收窄，可改绑"捕获校验子版本"（即你提到的 table display coverage identity v2 / 捕获组件位），代价是引入子版本比较——不改框架的一行级选择。
2. 历史回放把 rejected 尝试记入 `seen_unit_completions`（`:7780-7785`），语义正确但当前空计划下不可达；保留即可。
**证据不足**：① `locate_source_quote_offsets` 的"唯一性"语义本轮未读（"unique located"由 `bounds is None`→False 模式与既有用法支撑，未读实现）；② table display coverage identity v2 常量与记录位置未读；③ 新测试（`test_protocol_control_execution.py:1124、1148`）与作者路径 `:7843+` 未读；④ frozen 四文件清单与 HEAD 06b4037b 未 git 校验。以上均不影响 §一–§三 的结论方向，但"唯一性/测试覆盖"属未经本轮实证项。

**同模型家族折减**：本审阅与产品同族、同恢复上下文；结论为源码合同级工程判断，不构成医学批准或发布依据；实际来源与最终集成由 Owner 核实。
