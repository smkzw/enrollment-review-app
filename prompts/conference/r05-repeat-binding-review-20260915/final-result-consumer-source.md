# 复查结果实际消费：只读源码审阅

沿用本批准会话的 evidence_single_object 角色；禁止递归分派、文件修改、运行测试、导入应用、构造对象、调用模型或服务、访问数据库和浏览器。只读取工作树源码，以最终回复报告，由 runner 保存。前轮是设计意见，本轮必须重新读取实际实现，不能把前轮意见当验证。禁止读取工作树外临床资料。

用户已确认允许按本次已提供并核对资料判断，报告明确范围、已知缺失单列；不要求全部复查记录声明。完整构建后集中测试，本轮只能源码审阅，非临床验收。产品模型不由工程顾问代调。

请审阅实际新增复查单原子求值与持久化，重点发现会误判、丢来源、绕过书面判断、历史读取破坏或实际无法工作的缺陷。读完整受影响定义和相邻调用，给出文件行号及最小修复，不重新设计独立框架：

- app/services/repeat_condition_selection.py 与 qualified_binding_selection.py（消费v22，清空前保留result_sources）
- app/services/repeat_result_resolution.py
- app/services/repeat_atom_calculation.py（两族实际计算）
- app/domain/contracts/evaluation_result.py 与 app/domain/expression.py
- app/domain/repeat_numeric_result.py、repeat_result_selection.py
- app/services/predicate_proposition_calculation.py、component_review.py
- app/services/frozen_review_calculation.py（v26接入原子与原最终组合）
- app/projections/control_calculation_experiment.py（v11）、control_review_outcome.py
- app/domain/contracts/review.py、control_review_outcome.py（v4）
- app/services/frozen_review_publication.py（v8）
- app/services/review_history_service.py、app/storage/review_control_repository.py

关键标准：精确原方案/当前节点/原件/方法身份；只对已核实来源计算；确定性比较及Fraction合并不制造ClinicalFact；语义复用两路已核实命题；初查、复查疑问、采用结果分离；无依据不回退初查、不剔除坏复查挑有利结果；原条款AND/OR/例外不改；旧版本JSON可读且不获新方法授权。

已明确未完成：报告API/UI尚未呈现本轮新增记录；研究者自主许可仍保守未知；观察排序与复查组合未接；无复查时未自行推断回退。不要把这些已知边界冒充意外发现，但指出本轮实现是否错误地绕过或扩大它们。检查是否存在实际运行必然报错的类型/循环导入/参数/版本不一致；仅编译通过不是运行证据。

输出发现优先，区分确定缺陷/待核风险/建议，明确PASS或FAIL仅针对源码范围，不得声称运行或临床通过。
