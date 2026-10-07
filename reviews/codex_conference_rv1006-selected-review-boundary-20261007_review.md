# 1006V1 来源风险范围：所有者综合记录

状态：代码修订与相连软件检查完成；真实病例采用和完整窗口未完成。基础提交 c018cfb2940d5953cb048b8f4b87f4aa4ad013dc。

## 首个因果错误及最小修订

`validate_blocking_ocr_for_candidate` 在候选定位循环前，把整份资料任何页的未决风险当作本候选数值缺少核实。现改为 scoped_text_v1 的数值/单位/日期依赖候选，其自身每个来源页必须无剩余阻断风险；不依靠字符区间不重叠来绕过同页风险。页清单和识别页匹配先于视觉来源跳过；完整修订闭包错误仍全局拒绝，视觉来源另受独立资格检查。

这只修 OCR 风险范围，绝不是逐字段数值、日期、单位已被证明，更不是发布或医学批准。无定位、引文不含数值等问题仍由相邻资格承担，不用空风险清单证明正式采用。当前隔离病例24页均有自身风险，355个数值/日期候选的来源页均有风险；没有只因其他页而受阻的候选。本改动自身没有释放这些病例候选。

## 执行与独立审阅

E03 `rv1006-p2-manual-source-consumer-map-20261007` 实际 pi/cursor/default，session 01a114b5-cd6d-7000-902e-043e2b616bcb，exit0，无fallback。底层具体模型身份未报告，不把default称为已核模型。只读映射已有事实核对、采用与消费者；其“缺人工入口”的结论来自搜索 MANUAL_CONFIRMED，所有者用已有 OCRRiskReview、RiskScanService、EvidenceApiCommandService 与完整修订冻结路径反证，不新建人工框架。此执行未跑测试、未读临床材料、未验收产品。

C03 `rv1006-p2-selected-review-boundary-20261007` 实际 grok/grok-build/grok-4.7/high，session 9f51c779-770f-46b6-8d61-1e80aae1dcc5，终态exit0，无fallback。120分钟完成等待，实际等待215.6236秒，报告10次材料读取。独审针对修前代码/修复假设，条件接受候选自身页范围，反对仅删除提前拒绝；指出空风险并不证明字段来源、人工判断类型需核。所有者进一步核现有创建端：CORRECTED必须走真实校对，页级核对仅CONFIRMED_AS_READ，单风险允许NOT_APPLICABLE；未改变这些规则。最终补丁及测试由所有者核验，不声称顾问读过最终补丁或作医学批准。

原输出位于 runs/execution/rv1006-p2-manual-source-consumer-map-20261007/worker_01.md 和 runs/conference/rv1006-p2-selected-review-boundary-20261007/evidence_single_object.md；运行原答不作为临床来源或交付批准。

## 集中验证与边界

六相连原模块：test_scoped_source_risk_boundaries、test_fact_evidence_closure、test_slice44_revision_workflow、test_slice44_build_matrix、test_fact_publication_service、test_receipt_verified_work_draft_consumer。命令使用本工作树 .venv/bin/python -m pytest，最终164passed、5个第三方SWIG警告、68.09秒、exit0。JUnit /Users/smkzw/tmp/rv1006-selected-review-boundary-20261007-v3.xml，仅本机可读。

正例覆盖实际仓储保存人工核对、完整修订消费、无关页仍有风险而自身来源页已清；反例覆盖自身页非重叠风险、缺页/错误OCR/陈旧闭包。同页风险不放宽，正式发布消费者测试保持。

前两个集中窗口均162pass/2fail：新合成核对夹具缺base，随后base只有一页关系行。所有者修完整两页关系及真实序列化，不放宽生产端来源验证，不称旧夹具或模型失败。窗口重叠不累计。

## 下一消费边界

复用已有风险核对/校对与所选完整修订，不复制批准、不设置verified=true。当前候选仍须全部资格及实际保存读回；正式自动采用的隔离试验授权不能扩成正式批准。尚无完整同源要求包、当前节点工作稿和更正后新审核报告，claims_complete=false。
