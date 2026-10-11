# 会议输出：qwen-bounded-completion-review-20260910 - evidence_single_object

## 输出

续审第九遍（正式表达批次控制）。已读失败工件（第 7/17 批应 `['EX-10','EX-11','EX-12']` 实得 `['EX-10']`，一轮结构修复后 `failed_final`）与全部指定代码/测试。

**P0｜阻塞：门禁修复在形式模式下清空同批上下文。** `protocol_deconstructor.py:1446` 的 `candidate_context`（当前目标规则+冻结批次原文）仅在 `compact` 为真时构建；而 `:4697-4707` 修复前压缩会话历史，经解耦后（`protocol_semantic_transport.py:363-364` `supports_bounded_batch_context`=本地即真，与表示无关）**形式本地 transport 同样被压缩**，且锚文本自称“仅依据后续修订提示和其中提供的目标规则/原文返回”——但形式 `_repair_prompt`（:1469-1477）只有问题清单与 schema 文本，无原文无目标规则，模型只能编造。最小修复：1446 行去掉 `compact` 门（`_batch_prompt_payload` 表示中立），或 4697 行压缩仅限 compact；并补回归断言形式修复提示含目标规则与批次来源。

**P1｜编译风险未解，新数量/枚举约束可能整体失效。** 形式 schema 递归（`LogicalExpression`/`SemanticRule` 自 `$ref`）；oMLX xgrammar 编译失败即静默降级 prompt 注入，`minItems/maxItems/enum`（:1010-1015）全部落空，第 7 批式失败将原样重演（仅回执 Warning 可察）。真实试验前须 CPU 编译探针（pass-8 P1 仍开放）。

**P2｜相邻隐患。** `_batch_schema_repair_prompt`（:1341-1377）不含原文/目标规则，靠会话历史；当前批内修复（:4224-4234）前无压缩故安全——建议测试钉住“批内结构修复前不压缩”，防未来重演 P0。

**已核实无问题**：批次间压缩（:4322-4331）后下一批提示经 `build_protocol_deconstruction_prompt` 自含系统契约+本批来源（:1277-1282,1299-1317）✓；scope 于下一批调用前重配（:4260）且修复沿用本批 scope ✓；形式分支逐次新生成 schema 后再改，无共享突变 ✓；远端默认不变（property 仅本地；远端仍走 json_object）✓；slice3:149/160/173/183 覆盖数量/枚举、历史压缩、omlx 投影、修复不混 wire 文本 ✓。

**残余风险**：1418 项回归不含 P0 场景（其一半——压缩行为——已被 :160 钉住，修复上下文侧无测试）；无在线验证；形式 schema 的 grammar 编译行为未实测；实验预算为环境覆盖（记录 effective 131072，代码默认 cap 8192），非代码缺陷。不扩展为项目重构。
