继续同会话C03只读审阅，模型/档位保持原路由。不得运行Python、模型构造、测试、应用、浏览器，不写文件，不读原件/密钥/个人历史。仅读源码及必要直接导入，报告由runner写入。

前轮F1两处prompt Literal已加v5；所有者额外修了两处consumer Literal加v16。F2提示字段限定官方族；F3不新增限制（v3空条件不破坏正确性）。可最小确认，不重复前轮全库审阅。

新增范围：
1. app/domain/expression.py：从evaluate_component提取共同的选择核验与原子计算到_evaluate_bound_predicates；evaluate_component仍只两树。evaluate_bound_expression明确必需资料清单，供旁置树求值，不创建伪RuleComponent。检查旧行为保留及旁置是否能越权。
2. app/services/predicate_proposition_calculation.py的repeat_triggers_only默认False；新app/services/repeat_trigger_calculation.py按已封存资格结果计算官方旁置树，检查scope/事实值日期/原文位置，返回replacement_authorized=False。尚未接正式采用/未证明作用于初查，不能视为复查许可。本次检查实际错误并指出完整消费需有的证明，不要求暂未实现消费者冒充完成。
3. observation_relation合同/llm/input/receipts/graph五文件：v2要求逐事实origins(initial/repeat/unresolved及本条摘录)与repeat_of.reference_kind(initial_observation/preceding_observation/unspecified)，不得因最早或无关系推断初查。Context旧v1缺version保持历史序列化，新输入显式v2；旧回应不当新方法证据。对账保留各路完整原文、同意/不同意次序；图保留回指种类，同一次检查次序冲突、初查反为复查、初查回指目标实为复查等留结构疑问。图不证明范围完整或采用许可。
4. graph允许同一复查同时明确指向初查及紧邻上次，两种角色不误作两个前次；同角色多个目标仍冲突，所有有向边仍查环。核对v1 hash兼容与新版种类不会被当fact_id。origins只同意的已知角色进入图，保留未确定清单；同次组继承明确角色只属关系候选，临床/采用标志恒false。

源：上述文件，app/domain/contracts/repeat_scheme.py、app/domain/contracts/qualified_binding_selection.py、app/domain/contracts/binding_qualification.py、app/services/qualified_binding_selection.py必要相关定义。不要读全项目长日志。
输出缺陷优先（源码位置、后果、最小修订），然后已确认边界/未验证部分。特别审视初查、前次、未明确关系不能互换；方案/疾病/模型均不得硬编码。没有产品调用，不对速度/质量作数字结论。最终结果采用、期限和次数消费者仍待实现，临床声明保持false。
