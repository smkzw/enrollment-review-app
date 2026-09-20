# 本次节点复查计数：有界只读源码审阅

继续批准evidence_single_object角色，仅源码读取；禁止修改、应用导入、对象构造、测试、服务、数据库、浏览器、产品模型或再派发。runner保存回复。静态审阅不是运行或临床验收。

完整读取app/domain/contracts/observation_relation.py、app/llm/observation_relation.py、app/services/observation_relation_input.py、observation_relation_receipts.py、qualified_observation_relation.py、app/domain/repeat_series_constraints.py、repeat_observation_count.py、app/services/repeat_result_resolution.py；必要时相邻版本/冻结来源定义。最新观察合同/任务/提示/摘要v4，观察消费v7、资格消费v27、计算v31、发布v13。

变更：已有双路观察核对仅在方案count_scope=per_current_episode时逐fact列episode_memberships（current_episode/other_episode/unresolved+本条原文引用），否则空数组。不是新模型阶段。输入带冻结ReviewContext正式workflow_stage，保留display_name/visit_instance，不让模型仅猜opaque ID；准备重建仍绑定原context哈希。两路明确一致后还核原文来源资格；同次组全成员一致才有节点归属。只计本次节点的已核实repeat组，未知成员使覆盖不完整，不能证明未超限；确定已超限仍可证明FALSE。按初查组次数及所有原期限/结果采用路径保持，不按上传归属/日期窗口自动分组。结果保存全部observed组与counted组及节点归属，但不声称多初查/聚合排序/多次许可已完成。

检查实质错误：辅助原文混成结果、漏计/重复计数、未知当其他节点、原文引用不匹配、节点说明未绑定、同组冲突被吞、旧哈希/版本许可偷渡、新方法无批准就自动采用、相邻调用不兼容。给文件行及最小修正，不凑缺陷、不扩展范围。

上一轮O-a建议属性解析失败返回空集不采纳：空集会通过子集检查，反而可能放行；现维持错误向上失败，不把坏依据变空。O-b维持上游冻结校验，未新增猜测补全。前轮回执实际720.128秒/exit0/GLM-5.3-Flash:max/verified，源审无确定缺陷；本轮不能把上述判断当你已复核，应按代码检查。
