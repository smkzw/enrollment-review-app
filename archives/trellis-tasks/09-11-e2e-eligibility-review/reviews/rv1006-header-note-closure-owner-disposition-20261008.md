# RV1006 表头脚注闭合：所有者取舍与证据

基础源码d51f5c9e，当前窗口继续执行，claims_complete=false；不新增Phase、模型、规则真相或临床采用权限。

## 第一因果错误

产品Job664a74a63376450a8688d8632e42a15b终态failed_final，12新物理调用/400.544216秒/exit3，16深审完成、17失败、73未执行。失败检查点6a3eb542c5704917aea476a2fb132cb7保存来源、草稿、实际核对与账本；旧Job/payload、来源库、保护库保持，0共同发布/激活/签发。

核对明确提出三个脚注未核清。只读完整冻结清单证明：项目行脚注已有真实关系，标题行引用的另两条脚注也存在于原结构映射，但深审分包仅加入owned的脚注，没有加入已选context标题的脚注。对应核对输入又没有携带已有编号映射，因此不能把该失败称为原方案缺资料或研究者裁量。

原文只在受控本机；外部审阅者不能仅凭这里的哈希核实医学含义。

## 最小修复

- 复用原生解析器table_footnote_context_links；已选owned/context标题的实际编号映射进入同一分包，引用目标按原文顺序补入context。原owned、发现处置及无关批次保持。脚注本身原先是owned时不重复放入context，不剥夺原深审所有权。
- 批次合同只允许本批owned/context来源作为映射键；每条引用仍要求编号、完整可用非表格原单元，未知/跨批身份拒绝。计划仍完整校验上下文及原发现分母。
- 来源解释的只读标题提供编号映射；原生alignment提供映射并将其计入实际输入hash，scope/v3。旧proof和终态不改，原始标记并不自动证明脚注适用或临床覆盖。
- 当前兼容预检实际为15reusable/75refresh_required：仅1–15复用；受影响表格的上下文改变须重新读，旧材料不凭同batch_id采信。

## 独立工程审阅及取舍

批准C03实际CodeBuddy/codebuddy-cli/deepseek-v4.1-flash/max，session01a11d1e-1a44-7abe-8839-b9dc2bfe5c9e，runner终态exit0/no fallback，父执行174.178秒；120min完成等待，主线程静默。9次只读，无测试、原件、环境或临床执行。顾问额外读取实际材料比较函数（五文件外），如实保留，不声称严格五文件独立或医学批准。

- F1全量输入映射未消费即拒绝：不采纳。产品prepare从完整冻结清单生成映射；发现可有non_control/其他期别，深审只处理candidate/uncertain。未进入深审批次的标题不是自动遗漏。将全部表的映射强制入深审会恢复全量无关读取；全清单覆盖仍由原发现处置对账负责。
- F2跨表脚注来源：上游procedure_catalog.py::_flow_footnote_refs/table_footnote_context_links用实际表root和表后同列表来源解析，遇下一表/标题停止；补同编号跨两表正反例，不按heading相似度猜归属。
- F3规划层再加编号异常分类：现输入由原生编号解析器生成，现批次合同已有非法编号/空来源硬拒。不是当前阻断，不另加恢复接口；未提供或解析不完整的脚注仍不自动算已读。
- F4/F8身份：_same_deep_batch_material比较完整批次材料（仅忽略batch_total）；实际预检15/75证明变化不复用。plan_id包含有源context ID，编号关系变化即使plan_id相同也不能绕过整批比较及alignment输入hash。不以plan_id单字段代替复用资格。
- F5/F7补批数、strict zip及多owned批夹具；F9同表标题涉及多个批次时每个相关批次各获同源只读脚注，只有真正无关批次不变。
- F6上游缺失脚注不新增猜测：现上游已有完整续行、缺片、科学计数反例；本补丁不宣称所有原件的脚注都可解析，不创建无源链接，不清模型真实未决。

## 已运行与未运行

四相连原模块1242passed/110.10秒/exit0/5既有SWIG，artifacts/rv1006-header-note-closure-connected-20261008-v1.xml。顾问后仅增强合成测试，7passed/0.53秒/58deselected/exit0，artifacts/rv1006-header-note-closure-final-focus-20261008-v1.xml；未重复整库，不累加窗口。原模块为generalization、control_deconstructor、agent_transport、execution；末窗为generalization/procedure_catalog的受影响家族。

只读实际预检源13191716ea054d0d9ed026c189b574e6，0模型/0写/DBhash保持/exit0；私有rv1006-header-note-closure-preflight-20261008-v1.json。旧诊断首次把unit_kind读作kind报AttributeError，修诊断后成功，0模型/0写，不归因产品或模型。

完整90组、共同发布、当前节点工作稿及更正后新旧审核报告仍未达到。新真实运行须经现有产品API、真实冻结预检和完整门；不能用本报告或测试直接激活规则。
