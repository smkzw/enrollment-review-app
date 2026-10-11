# 定向来源约束复核

继续既有只读角色，不改文件、不启动模型、不访问工作区外临床源。先更正上一回复：原 response-3 EX-04 已有现病史第二组件，不是本轮新增。

请独立审阅当前 app/agents/protocol_deconstructor.py 的 protocol_output_response_format / _repair_prompt，以及 app/protocols/deconstruction_gate.py 的 _frequency_repair_action 和脚本 qwen_semantic_repair_diagnostic.py。涉及恢复原有_SYSTEM_CONTRACT，正式生成格式中每谓词至少一个原文片段，完整anyOf分支，不改持久域合同、不填医学答案。

新证据根 artifacts/qwen-three-platform-20260909-v3：
- formal-targeted-repair-live-02：仅反馈细化，150.763s/4074，仍缺来源且开放范围退化。
- live-03：恢复原有完整说明，384.322s/10487，仍缺来源。
- live-04：anyOf与properties/required并列，317.641s/10063；语法自然结束但只输出source而无其他谓词必填字段。标准JSON Schema检查严格拒绝；实际平台生成约束未执行并列基础字段要求。
- live-05：把基础属性/必填条件完整复制入两个anyOf分支，359.968s/11963；形式解析、frequency_issues、scope_issues通过，clinical_acceptance仍false。所有运行相同oMLX模型medium、max_tokens131072、无模型缓存、默认采样、单条独立源，不是标准排名。
- prepare-05/prepared-request.json是当前完整生成schema。平台内置xgrammar CPU编译通过，03无来源/04仅来源两个反例都拒绝，schema字段顺序的完整原子可接收（任意字段顺序可能不接收）。不得把编译成功等同完整兼容。152聚焦检查通过；1421全protocols检查在最后“完整分支展开”之前通过，最后修改需分开表述。

请回答：源码修订是否有共享回归/临床边界问题？live-05是否仍有语义或表达风险，尤其现病史 comparator=in、source_term使用、开放列举与频次窗口锚点？下一步应优先完整门禁离线重放还是新模型调用？只基于源证据给建议，不宣布整条或全系统验收。
