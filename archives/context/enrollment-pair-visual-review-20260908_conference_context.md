# 冻结双模型视觉审阅
## 范围
仅评审已有产品输出与原件，不运行产品模型、不替产品生成事实。主线程尚未选择赢家。读上下文独立，但候选包含同模型家族，报告独立性限制。
所有路径相对当前worktree。根目录 artifacts/phase55-model-comparison/20260907/。
可读：product-input-v2/input.json、manifest.json、pages/；product-runs-complete24/；product-runs-resume-20260908/minimax-m3-high-page-*/ 与 minimax-m3-high-connect-retry-page-22/；product-pair-gemini-main-a-20260908/；pair-complete24/；pair-complete24-minimax-high/；gold-sar-lab-page9.json、gold-sar-biochemistry-page17.json；app/domain/page_reconciliation.py、app/domain/page_source_association.py、app/domain/targeted_page_review.py与其直接合同。
禁止读取 .env、个人配置、其他任务、harness-findings、MODEL_COMPARISON、其他review及主线程结论；禁止网络/新API/数据库写入/任何文件修改。
## 工作
用视觉工具实际查看冻结pages图像。可先从input.json按索引找到文件；扩展名为空不妨碍读取，不要仅看OCR替代原图。重点覆盖病历、检验、手写各类（索引1、9、17、18及自主选择2页）；临床范围仅原件和冻结ClausePack，不能凭常识补诊断。
比较三种搭配：GLM low+Gemini high、GLM low+MiniMax high、Gemini high+MiniMax high。保留首轮失败，恢复记录分开。Gemini main-A为新真实调用，不能改旧main-B标签。第23页两个GLM+MiniMax机械回放来源相同，统计按页去重。
检查模型是否准确完整保留否定、时间、结果、单位、主体和手写；共同读对、共同读错、一方漏读的区别；已采信键是否真正临床正确，是否主要人口学信息。键数不等于事实数，不直接作召回率。仅金标覆盖切片可报该切片数值表现，不能称全任务召回。
给出高影响发现、具体页/观察ID/原文依据、通用修订建议和需要主线程进一步核对的事项。无需局限于预列问题，可自主发现，但只在可读集合内。遇图像工具不可用如实记录，不能宣称视觉审阅完成。
## 交付
返回中文报告，由runner保存；不自行写报告文件。分开实见、推断、建议与不确定性。AI审阅不是临床签批。
