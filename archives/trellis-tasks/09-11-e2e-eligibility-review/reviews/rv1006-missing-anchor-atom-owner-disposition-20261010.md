# 缺失时间锚点的局部修订：所有者取舍

## 实际问题与边界

- 实际运行代码81b3cd0e502ad7709acdb4f80da38aea0b52779b，Job0c8e961e4fc6456e9f2d9295fdf60116终态failed_final，6物理调用/286.66884104092605秒/exit3。85发现和44成功深审零新调用，45失败、45未执行；旧Job/保护库/来源库不变，无共同发布/启用/签发。
- 第6条账本的TIME_ANCHOR_MISSING已有具体候选、原子路径、来源span与摘录hash；第7条仍要求整候选输出，恢复时按span字典对齐，同一句支持两个独立原子导致正确拒绝重复定位。不是原件不可读或研究者判断缺失。
- 冻结回执经原有parse、candidate merge、hydrate、实际_validate_deep_batch_output重放，当前selector准确返回(1,0,1)。0模型、0写库、无proof签发；第一次只读诊断把消费者参数顺序写反而exit1，修调用顺序后exit0，不改产品来迎合诊断。

## 最小修改

沿用现有continue_atom与原子拼接：单一当前错误的完整身份核验后，仅补time_constraint及配套time_operand_attribute/time_purpose。临床命题、观察政策、来源和兄弟字段冻结。格式失败仍同路径/同限制重试，缺能力不退整候选；预算及无进展停止不变。旧span-only整体恢复门完全保留，未按药物、病种、方案名或固定数值放宽。

基础作者和编译器未变，新增validator身份missing-anchor-scoped-atom-recovery/v1。只读实际来源预检44reusable/1resume_partial/45refresh_required、0模型/0写库/DBhash保持。第45仅可接续已核来源解释，不能把失败草稿或缺失目标核查当成功。

## 批准独审与取舍

C03/evidence_single_object，CodeBuddy/codebuddy-cli/deepseek-v4.1-flash/max，session01a12256-4dba-729e-9330-250349f33417，196.579秒/exit0/no fallback，120分钟完成等待。报告在runs/conference/rv1006-missing-anchor-atom-review-20261010/evidence_single_object.md；原运行回执私有logs。同DeepSeek家族，只有新程序/上下文分离，不称独立模型意见或临床批准。

- F1–F3：实际身份、字段冻结、同错恢复与缺能力保护有代码依据，采纳。
- F4：顾问未读旧恢复正文；所有者完整读取，旧重复span拒绝保留，已拼接的单原子不再用span猜对象。现有输出恢复继续锁住其他候选和来源处置。不能将未读范围叫完整独审。
- F5：结构合法的命名时间并不自动证明原文含义。保留实际完整来源、语义对应及采用门，不新增访视词表/日期猜测或自动采用，也不把顾问的“人工审核会处理”当产品保证。新时间字段仍是模型提案，不是确定性临床证明。
- F6：范围不完全一致时拒绝窄修订属于保守边界。实际冻结原答已精确命中，无证据无需放宽。
- F7：冻结权限按错误轮次，不承诺未来不同有据错误永远只能改同一字段；每次新授权仍来源化且重验。
- F8：并行观察/时间模式未证可达。实际selector要求只有TIME_ANCHOR_MISSING，原观察选择器只接受自己的错误类，不能凭猜测新增恢复分支。

顾问未读测试、mapper完整正文及身份消费者；这些由所有者检查，不声称测试已被模型确认。顾问实际9次读/search中一次超平台输出上限无内容，超出8次请求预算如实保留。

## 验证与复盘

相连功能窗为control deconstructor、publication gate、execution service三个原模块；新用例使用合成同源双子项，包含正确定位、错path/hash/owner/entity/span、混合错误类、重排、越权命题、同限制恢复、重复停止、缺运输能力拒绝。来源及临床字段不变；水合ID随父候选版本改变，测试分别核精确wire保留与去系统ID后的业务字段，不以旧ID强行固定新版本。

v1为1610pass/11fail/121.38秒；新夹具误加不存在字段，另有validator版本预期未同步。v2为1621pass/2fail/124.61秒，新夹具complete_or_verify带时窗却给不兼容time_purpose，被旧构造器正确拒。v3为1621pass/2fail/131.89秒，实际只差水合obligation_id；冻结比对证业务字段和wire兄弟均不变，修测试期望，不松产品门。针对性4例中2pass/2fail用于快速定位此字段，0.84秒，不累计窗口。最终集中窗另记录实际终态，不提前宣称通过。

最终同三模块集中窗1623passed/119.39秒/exit0/5SWIG，JUnit artifacts/rv1006-missing-anchor-atom-connected-20261010-v4.xml；git diff --check通过。源码最后修改在独审前，末变化仅测试夹具/断言及身份预期，不冒称顾问读过末测试。窗口不相加，非临床验收。

这轮测试材料错误拖长验证；应先完整核夹具与已有构造器、对同因新失败做局部定位，稳定后才跑相连窗口，不能每次夹具小修机械重跑全窗。不会用检查总数替代正式用户流程。

## 尚未实现

完整共同要求发布、同包当前节点工作稿、正式UI有源更正后的相关重算及新旧结果仍未达。上述修复与只读重放不是整例验收。正式自动事实采用和临床签发仍不授权。下一从当前实际来源的合法入口续建，保留旧终态/账本及可复用44组；不覆盖既有输出目录、不复制大库。
