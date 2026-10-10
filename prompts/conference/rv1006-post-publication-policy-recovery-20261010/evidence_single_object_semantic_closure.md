# 定向只读复核：有源负核对能否安全进入既有单元修订

沿已批准C03本会话执行，只读、不递归派发、不读病例/私有数据库/环境文件/临床原答、不修改源码。只评工程边界，不作临床批准。

本轮待挑战的冻结差异（基础bfc0f68b，尚未提交）：
- app/agents/protocol_control_deconstructor.py::_reviewed_semantic_closure_repair；run的cited_unexpressed分支；已有_merge_scoped_unit_repair及后续完整门。
- app/services/protocol_control_execution.py仅新增validator身份。
- tests/v2/protocols/test_slice58c_control_deconstructor.py的reviewed_semantic_closure家族及既有scoped_unit_repair家族。

问题：可信绑定的incomplete核对是否只授权一个来源明确、无真实疑问、无跨单元共同候选的完整单元进入原局部接口？缺proof、来源变动、正核对、真正歧义、多单元、传输失败是否仍拒？修订后是否保留范围外兄弟、重新消费和核对；一次无改善是否停止；原负核对不能当采用。

请特别挑战：授权依据是否充分、同单元未受影响含义是否受原门保护、错误scope是否会隐式扩大、旧partial恢复是否存在再次消耗而无新证据的风险。若已有足够确定性反证，不要求更多模型投票或大重构。预算与恢复限制必须如实，不能用本轮小窗证明跨运行账本完整。

最多12次针对性只读；完整读相关定义及决定性消费者，不扫全部历史。可读git diff只限上述文件；不运行真实模型/库写/服务/网络，不重跑全库。报告必修项按严重度+位置+具体反例，区分已证明/推测/未执行，并给最小方案。未发现必修也明确残余。返回一个完整报告，不把摘要当报告，不宣称产品交付。
