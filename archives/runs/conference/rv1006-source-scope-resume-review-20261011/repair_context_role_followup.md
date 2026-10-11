收到 C03 有界增量复审（修复提示材料与捕获重开分支）。只读、不委派、不落盘（Explore/Plan 子代理与"不委派"边界冲突；计划文件不写）。先定位新符号并读取恢复分支。

定位完成：常量 `deconstructor:268`、哈希函数 `:2982`（`:3008` 纳入）、使用点 `:12045`、种子证明 `execution:2449`、回执可追踪 `:3694`。读取四处（预算 6，已用 2＋本轮 4）。

# Conference Output: rv1006-source-scope-resume-review-20261011 - evidence_single_object

## Output

同会话增量复审（6 次目标读取用满：1 次符号定位＋5 次定义读取；`_completed_repair_receipt_traceable`、`_execute_deep` 预算绑定与三支测试未读，见末节）。未改文件、未运行测试、未委派（Explore/Plan 子代理与"不委派"冲突；计划文件未写）、未读临床/DB/env/tmp。**同产品模型家族、同恢复上下文，独立性折减；以下为源/提案校验级结论，非临床批准；实际来源与集成归 Owner。**

---

### 一、修复提示材料（变更 1）：只收紧、不授权

**[代码事实]**
- 常量文本（`protocol_control_deconstructor.py:268-275`）是**通用修复指导**，无疾病/评分/分期专属；其内容是**限制**："applicable_population、条件、时间和例外只能由本动作原文、直接上位范围或经核实的结构关系支持；context_units、已有官方/流程目标及其访视标签仅供核对关系，不能自动借作当前动作的限制"；"review_stage 及 workflow_stage_id 说明在哪里核查，不证明原文只适用于该阶段"；"未能找到限定时不为匹配目录而新增时期或缩窄人群；明确未限定与原文歧义分别保留"。
- 仅当 `not base_only` 时进入完整修复合同哈希（`:2982-3010`，`:3008` 追加），`base_only` 路径不含它 → 与"基础作者/来源提示不变"一致。
- 唯一使用点是既有来源闭包局部修复提示（`:12042-12056`：`build_protocol_control_agent_prompt(local_batch, …) + _SCOPED_SOURCE_CONTEXT_REPAIR_GUIDANCE + (…既有反绕过文字…)`，随后 `transport.continue_scoped_unit_repair`）。拼接位置与上下文表明它**补充**既有"不得因无正确关联就称已覆盖/独立要求应保留有源候选"的约束，而非给予新权力。
**边界**：该 guidance 只影响该修复提示文本与完整修复合同哈希（旧合同哈希因此失配）；不改变 splice、兄弟保护、完整来源/发布门。**[推断]** 它是"修复材料"而非"生成材料"，与 `base_only` 排除相印证。

### 二、接受矩阵（变更 2）：放宽只作用于唯一绑定记录

**[代码事实]** `_validated_deep_partial_source` 的收口（`protocol_control_execution.py:2954-2959`）：

```
if completion_resume is not None:
    if (changed_components
            or (repair_identity != protocol_control_agent_repair_contract_sha256()
                and completion_resume.reason != "source_capture_revalidated_requires_fresh_author")):
        raise ...
    return checkpoint_id, saved, completion_resume
```

- `changed_components`（非 validator 的材料变化）**仍然阻断**；只有"修复合同变化"且 reason 为 `source_capture_revalidated_requires_fresh_author` 时放行。传输型补读恢复（reason `source_unit_quote_completion_transport_resume`）不满足该条件 → **仍拒绝变化合同**。
- 该 reason 只有一个生产点：`_resumable_unit_completion_failure` 的 rejected_capture 分支（前轮已核 `:2833-2848`），且进入该分支必须同时满足：validator 变化、错误类**恰为** `SOURCE_UNIT_QUOTE_COMPLETION_INVALID`＋`schema_invalid`、`detail.called is True`、种子证明 v1＋`adopted is False`、**四项语义字段全空**、计划单元合法、单元/detail/前置/source_refs 绑定、历史账存在且末条一致、`remaining` 为空、**原来源 sha 相等**、**被拒答复非空且哈希吻合**。输出 `source-capture-revalidated-proof/v1`、`source_unit_completion_ids: []`。
- 空计划经执行层 `resume_source_unit_completion_ids`（`:4752-4757`）进入 runner，`if resume_source_unit_completion_ids:` 为假即跳过补读块（前轮已核 `deconstructor:7806`），无 `partial_wire/review/coverage/alignment` 可恢复 → 走全新作者＋核对＋完整门。

**[代码事实] 其他失败提案的既有恢复**（`execution.py:2449-2549`）：`_revalidated_source_seed_proof` 文档明示"只重放实际来源读取，绝不复用其下游作者结果"；入口要求组件身份相等（除 compiler/validator，`:2458-2465`）、实际原答哈希必须吻合（不吻合即抛"不能作为缓存未命中处理"，`:2531-2533`）、pending 路径要求下游全空并按阶段回显证明与 `repairs_used` 上界（`:2477-2521`），随后从 actual 文本重建来源（`:2542-2549`）。**未在本轮读到其提问/修正历史与额度结算的余下部分**（见末节）。

**边界结论**：
- **不绕过负语义证明**：负核对保留证明（`_preserved_negative_alignment_proof`）与本 delta 不相交；这里从不把被拒补读当"歧义"或候选采用。
- **不绕过作用域/权威**：新 guidance 只收窄；接受放宽仅对上述全绑定记录。
- **不绕过累计预算**：新证明 `**proof` 透传（含 `source_repair_limit`）、历史账必须匹配、无清零路径；runner 对历史尝试计费（前轮 `deconstructor:7803-7805`）。
- **不把来源-only 恢复变成采用旧候选**：四项语义字段必须为空；种子不携带任何候选/复核；空计划直达新作者。

### 三、缺陷与建议

**必修**：已读面内**未发现可达绕过/采用缺陷**。
**建议（低）**：`2957` 用 **reason 字符串**作为授权键（唯一生产点当前安全）；可另并检 `source_seed_proof["schema_version"] == "phase5/source-capture-revalidated-proof/v1"` 作为类型化收紧，避免未来新增 reason 时误放行——一行级，不新框架。
**证据不足/未读（如实声明）**：① `_completed_repair_receipt_traceable`（`:3694`）实现未读，仅见使用点 `:1266、:3544、:3975`；② `_execute_deep` 旧来源历史/请求预算绑定（`seed_limit`/`_bind_control_request_budget` 一带）本轮未重读；③ `protocol_control_agent_repair_contract_sha256(base_only=True/legacy…)` 的调用方未读；④ `_revalidated_source_seed_proof` 在 `:2549` 之后的提问/修正回放与额度结算未读；⑤ 三支点名测试未读。以上不改变 §一/§二 的边界结论，但"回执可追踪"与"预算绑定"属未经本轮实证项。

**独立性**：同族模型、同恢复上下文；本报告只核对源码合同（源/提案校验），不构成医学批准或真实采用依据。
