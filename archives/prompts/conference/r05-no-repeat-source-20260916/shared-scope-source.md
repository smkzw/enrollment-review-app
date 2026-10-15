# 多次共用原文范围：仅源码增量复核

继续原批准只读角色，不写文件、不测试/导入/构造对象、不启动服务/模型/数据库/浏览器、不派发；runner保存回复。不要声称临床或运行验收。

读取完整变化定义：app/domain/contracts/observation_relation.py、app/llm/observation_relation.py、app/services/qualified_observation_relation.py、repeat_condition_selection.py、repeat_permission_calculation.py，以及上轮后有报告接线变动的repeat_result_resolution.py与app/projections/repeat_review_presentation.py。按需要读相邻版本/回执。新观察合同/输入/任务/摘要/提示v5、消费v8、资格v28、计算v32/发布v14，历史None省略及旧版本保留。

新增每条AuxiliaryObservationAssociation可选shared_scope_excerpt，仅原文明确覆盖多次时逐次引用共同范围说明；模型仍只核观察来源关系，不判许可或入排。输出逐字原文校验；同辅助pair多组关联时，所有已一致关联均须两路提供范围原文且通过既有来源资格，否则仍作为归属歧义移出。单组不要求共用说明。条件取证仅对已明确覆盖的reference组使用同条原文；没有归属不等于其他组，多组中任何一项缺范围证明仍阻断。书面许可仍独立核内容、决定性分支、各次target范围，次数/期限不变。没有新harness阶段；方法未评测/批准前不能正式采用。

报告新增count_scope冻结材料及本次节点计数说明/每组归属，旧无字段不补写、不重算。上轮报告一处文字不准确：明确other_episode不令覆盖不完整；代码是未知或源范围未核清才不完整，不需照报告错误改代码。

重点找真实通路：任一模型未支持范围仍被共用、拼接不同pair事实造成越范围、普通一次许可被自动沿用、范围原文未校验/不同冻结资料串用、旧版本hash改写、代码报错或新调用未接。不要凭有两端引文即声称临床准确；这里只是经方法评测前的产品实现。没有确证缺陷直接说明；如需修正给最小方案及文件行，不扩充新架构。
