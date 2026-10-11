# 1006V1整段时间要求与保存结果恢复

基础HEAD：1796417d5fbfed174b995e8f5f33dab0495f5dfd。工作树为唯一phase5-clinical-facts-profile；7份继承delivery改动未修改或纳入本提交。Goal active，claims_complete=false。

## 实际首错与范围

实际API79849a40…failed_final，第一组18原文点/4候选在来源和作者门禁之后，因第9点TEMPORAL_SCOPE_UNRESOLVED停止；第14点另有真实时期对应未决。11物理调用619.188226s，85发现复用0调用；不能把正常stop或官方草稿publishable当作共同发布。

来源连续期和局部标题已存在，不需要再生成。whole-unit-restricted/v2仅将两个受影响单元的10个原文点保留待核，0可执行候选；全量源、原作者、核对、时间故障见证、整段覆盖及现行门禁仍必须通过。未报告来源、错义、跨单元候选和无据独立性拒绝。此机制无方案/药物/数值特例。

实际只读预检：90组，第一组preserve_unresolved、review=reused、无source-only降级；原失败诊断摘要eb6ce31da4d72df6bd32bfc5b33e4f72205738cb6fe3df2c6e8ecfdeb64eb328，当前受限摘要59d22c4bc1e0e6e6cbd8dec85599ffb7978c57d3d5d8b920af72ea2c40551c78。其余89组仍refresh_required，不以历史13组通过强行复用不同身份。0模型/0写入，仅证明该恢复可入队。

## 接线与边界

生产：restricted_batch_from_review严格验证实际源/作者/逐项覆盖/核对和时间故障范围。

保存：沿原JobStore检查点和私有attempt_raw_outputs，原Job/原答/hash不覆盖。

恢复：实际来源/分包/草稿/提示/Schema/路线/恢复材料不变且无pending纠正，当前重验零候选、无独立性证明的受限结果，才允许编译变化下保留失败诊断。入队与执行分别核原诊断及派生产物摘要，不白名单版本、不恢复可执行语义。

消费：新旧路径共用_complete_restricted_deep_source；缺定义消费者时实际登记，沿原共享预算，既存登记必须精确恢复私有原答并重验。全局范围未知不抹掉，不因为登记成功就scope_complete。

界面/API：既有受限投影保留具体条目、原因和源，没有新增展示壳。本包尚未完成完整新规则共同发布、当前节点工作稿及相关更正；共享首屏适配184bdb60的成果不重做。

## 集中验证

命令：.venv/bin/python -m pytest tests/v2/services/test_protocol_control_execution.py tests/v2/domain/test_control_catalog_restricted_contract.py tests/v2/services/test_eligibility_review_projection.py -q --tb=short --junitxml=artifacts/rv1006-whole-temporal-source-connected-20261008-reviewed-final.xml

最终419passed/95.54s/exit0/5既有SWIG。此前392pass4fail/97.98s为新夹具误把已表达条目加入核对范围及旧断言不区分整体待核；v2 410pass2fail/96.21s，一项夹具漏计新定义消费者，一项恢复证明异常未类型化；修夹具与明确错误，不关闭来源保护。412pass94.72s是最终独审硬化前快照，不累加、不冒称同版最终419。

正反家族：连续期+time_validity、明确局部标题、同段真实未决；整段待核不能保留可执行兄弟；坏数值/不完整原文/错源/错范围/boolean索引/多重故障拒绝；变更source/prompt/schema/repair或仍保留候选不能跨编译复用；JobRunner保存/读回/旧hash；定义新登记、私有原答缺失/重复/损坏；实际投影无事实真值。git diff --check exit0。

## 独立审阅处置

C03实际CodeBuddy/codebuddy-cli/deepseek-v4.1-flash/max，同会话01a118e4…，无fallback。初轮exit0但仅启动/读取，拒为未完成；同会话补交完整报告；随后对恢复接线作8次有界读取。初轮两处读取略超声明窗口，保留限制，不包装成严格全范围审计。末轮之后的typed-witness/私有原答小修由所有者验证，未追认顾问看过。

采纳：先保留原失败材料再重验，不在降级后伪造证明；时间标签必须精确见证；恢复源错误类型化；定义真实读取不能跳过。

未采纳或限制：不扩大版本白名单、不新建失败状态/框架、不加猜测跨单元依赖。顾问未核调用预算实现与全局范围；所有者确认两gate异常均ValueError、take_call_receipts清空当轮队列。顾问F1缺失wire反例未满足实际源未决前提，作为防损坏边界而非自然真实失败定论。诊断SHA只证明身份，不证明医学含义。顾问意见不是专业批准。

## 本机受控实跑与未证

新API作业1f79e0e7b20442f3b66edde7a2ed6fa1第一步已实际完成并保存。受控目录rv1006-temporal-restriction-resume-20261008-v1，前置证明与只读核验一致；原文与整包作者读道被显式禁止，只新增必要定义登记1物理调用。Ollama cloud/deepseek-v4.1-flash/high，105.0591115s/stop，input14876/output含思考25309/total40185/cache512；整步130.7780577s。保存18来源点、10受限点/0候选、2定义项及1个实际登记原答，整体仍需要核对，不宣称全局定义关系已核清。首步受控检查点后Job queued/无失败，随后同一个Job由唯一自有Runner继续余89组，不新建或消费继承队列。续跑记录在rv1006-temporal-restriction-remaining-20261008-v1，当前尚未终态。

第一步旧Job状态和payload、保护材料、来源库hash均保持；0共同发布/激活/签发。临床原答、DB、环境、原件和私有驱动不提交；上述本机路径外部审阅不可读，哈希只证明身份。新读取结束后继续原窗口，而不是以本功能包代替交付。

代码快照SHA256：
- execution.py dd7a6231c922b9750e072044de912d0f771a2c913bbaae691d22391ef6c83c07
- restricted_source.py e54e460db175a54cffe7526fe7ce0936129a7a82b3f3175c5745a9583af11434
- test_protocol_control_execution.py cee1e77f2eafd06d8d0ca80a89fbf77096b8b416804a5ae6a3e0e1b520306da5

以上源码/测试摘要对应最终419验证；后续变化需重新绑定证据。只读诊断首次误用_prompt_from_payload签名，TypeError/0调用/0写入，按现行冻结prompt_templates修正，不伪报产品故障。
