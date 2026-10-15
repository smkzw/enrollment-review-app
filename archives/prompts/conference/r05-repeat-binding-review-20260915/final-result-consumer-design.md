# 最终复查结果消费：独立只读设计核查

沿用批准的 evidence_single_object 会话与实际模型/档位，不更换路由、不递归分派。只读源文件，禁止修改任何文件、运行测试、导入应用、构造对象、启动服务、调用产品模型、读取数据库、访问浏览器或工作树外临床资料。仅以最终回复给出报告，由既有 runner 保存。

用户最新确认：允许依据本次已提供且核对的资料判断，报告说明范围，已知缺失单列；不要求另有“全部复查记录已提供”声明。用户要求完整构建后集中测试，因此本轮只作源码设计审阅，不作运行或临床验收。

请先读取当前实现，而不是依赖上轮结论：
- app/domain/contracts/repeat_scheme.py
- app/domain/repeat_result_selection.py
- app/domain/repeat_series_constraints.py
- app/domain/repeat_numeric_result.py
- app/services/repeat_condition_selection.py
- app/services/repeat_trigger_calculation.py
- app/projections/control_repeat_trigger_calculation.py
- app/services/qualified_observation_relation.py
- app/services/qualified_binding_selection.py 的观察关系、全局选择和命题关系筛选段
- app/services/frozen_review_calculation.py
- app/domain/expression.py 的 _evaluate_bound_predicates、evaluate_component
- app/projections/control_calculation_experiment.py 的 _evaluate_control_selection
- app/services/frozen_review_publication.py
- docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md 最后复查来源增量

目前实际状态：逐配对核实后，已在全局选择前保存逐目标复查的完整触发/许可条件选择；正式冻结计算已调用两族条件计算器并返回条件结果。次数、日期和方案结果选择已有消费者材料。最终复查 owner 仍被 repeat_relation_unverified 阻止，不能以已有辅助计算声称完成。

请挑战以下拟实施方案，并给出最小完整的源码接线建议（不是再设计另一套模型任务）：
1. 由现有封存选择及计算结果派生复查采用依据，按具体目标分别核实触发、许可、次数与期限。不能把辅助条件的 TRUE 直接当入排 TRUE，不能让其进入最终条款的 AND。所有结果绑定方案/本次资料/观察图/条件范围及方法身份。
2. 方案明确 retain_initial 时，初查判定与复查执行疑问分别保留；不因为某次复查触发或日期不明就抹去已经核实的初查事实。初查本身的来源、归属、书面判断及有效期仍必须通过。其他结果政策不能因为复查不合要求就无依据回退初查或选有利值。无复查、可选复查、条件不触发的回退语义尚未明确：请指出哪些可由现有合同合理确定，哪些必须保留未知/需要补原文合同，不能擅自编造临床政策。
3. 官方与控制要求都接同一通用采用依据，但各自复用原数值/语义求值器。数值合并只产有理数计算结果，不构造假的 ClinicalFact；布尔 all/any 走逐检查命题。语义关系须在全局清空前保存与具体检查关联的已核实原文。缺研究者判断直接报告，不能要求用户再次确认缺失本身。
4. 不通过修改冻结方案或普通 caller 传入任意真值来绕过来源。建议一个仅由封存结果重建的计算入口，分别给官方/控制表达式提供有依据的单原子结果；原最终组合保持不变。报告区分初查发现、复查是否可采用、实际采用结果及资料范围，保留未采用原件。

输出：高/中风险优先，每项给源文件/行依据及最小修订。请明确推荐的消费边界、无复查/不合规复查策略、如何不破坏历史封存/原文引用。若认为建议过度工程化或还有更短的完整实现，请具体指出。不要推荐以“等做测试”替代实际构建，也不要宣称本轮运行验证通过。
