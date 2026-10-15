# 1006V1 后置资料政策核对：所有者取舍

## 实际首错与边界

真实产品运行源码5bb2d4e6、Job d5898e74c0f54c3ea6bc85ddb60324c6：failed_final/PROTOCOL_CONTROL_EVIDENCE_POLICY_UNJUSTIFIED，5物理调用287.742400167秒，44深审完成、45排队。85发现及44已成功组实际零新增读取；预检50可复用不是本次实际完成50。0共同发布/激活/签发，claims_complete=false。原件、旧Job、来源库和保护库保持。

一项许可性要求的候选增加了原文没有的取证豁免，并把许可写为必需核对；来源审阅正确拒绝。宿主却把这项有效负核对归为普通政策失败，并撤回另一项已经完整门及新鲜语义核对的条件句修订。首因是既有后置核对和局部恢复的衔接，不证明模型普遍不足，也不是临床缺资料。

## 最小修复

只改既有Runner：本次回应完成结构、范围和来源绑定后，require_evidence_policy_alignment 的有效负结论才可进入原 scoped-unit repair。损坏、重复、范围、字段和传输失败不能借历史负结论进入此路。只有单一完整、无未核范围的来源单元可修一次；共用修订次数和已修单元账，不增加路线或刷新额度。

前项修订保留需要不变兄弟/处置、所有受影响动作与政策的正向绑定，且没有该来源的未核陈述；同一保护也约束抛出局部修订异常的路径。未满足时仍回退原未核草稿。保存不等于采用；新提案仍全门、重新来源核对，坏局部答不升级。

## 独立审阅和决定

C03任务 rv1006-late-policy-recovery-review-20261011，Grok/grok-build/grok-4.7/high，只读源码与合成用例，实际exit0。运行器记录首次同路线exit1后同路线exit0，session ce928534-2cb5-4059-aac3-b364dcb15fe0；不是无fallback的顺畅运行，不称不同模型意见。报告 runs/conference/rv1006-late-policy-recovery-review-20261011/evidence_single_object.md。未读原件/数据库/病例原答，未执行测试，不是医学批准。

采纳：新回应完成标记防旧负结论误用；回退保护同时约束raise；所有受影响动作对齐及未核陈述保护。证据维度未写全或取值相同的 incomplete 不强制改成完整或技术错误：它也可能指出义务/许可、范围等其他语义差额。现行合同允许负结论保留这些差额，只用于单次有界修订，绝不作采用证明；新增空维度/同值反例验证这种既有语义，不让模型投票。

## 验证

- 首窗口15例：11通过、4失败，均为新测试给冻结expected evaluation直接赋值，已保留JUnit v1并改model_copy；不松产品门。
- 扩展最终相连窗口：56 passed、1655 deselected、5第三方SWIG警告、8.25秒、exit0。命令为 `.venv/bin/python -m pytest tests/v2/protocols/test_slice58c_control_deconstructor.py tests/v2/services/test_protocol_control_execution.py -k 'late_policy_negative or source_condition_repair or proposition_field_repair or reviewed_semantic_closure or independent_reads or preserved_negative_alignment or evidence_policy or negative_alignment or definition_failure_keeps_alignment' -q --junitxml=artifacts/rv1006-late-policy-connected-20261011-v1.xml`。
- 覆盖正确修订、不可用、坏JSON、越界、核对断流/坏JSON/重复/错来源、修订账已用、空维度/同值负结论；旧绑定、消费者、独立读错误资格和保存反例沿相连原模块核验。没有单独构造“旧负结论+本次坏回应”的实际保存夹具；新回应完成标记和错误类型由源码直接核，不夸大测试覆盖。
- 源码diff检查exit0。没有全库重跑；没有正式UI、新完整规则工作稿或临床验收。

## 配置与方法判断

固定已批准官方GLM与跨章Ollama DeepSeek；不新加模型/图平台。此次有证错误属于状态与依赖边界；其代价来自后置失败回滚、反复宽上下文恢复，不能用增加输出预算解决。下一让原子局部修订与现有单元恢复实际保存、逐项消费；无新证据相同失败停止分支，其他独立读取按现有两次止损策略。完整要求、同包病例、正式UI更正和旧历史保持仍是交付终点。
