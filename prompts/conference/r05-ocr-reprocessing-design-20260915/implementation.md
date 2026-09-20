Delegated mode. You are a bounded read-only reviewer in the existing same-model conference session. Do not delegate, browse, run tests, product models, application or database commands, or write files. Return your report to the runner. Do not read raw clinical material or other worktrees. Codex retains final acceptance.

请对实际新增重识别后端做源码复核，而非重复方案。完整读 app/services/evidence_reprocessing.py、app/api/v2/evidence_reprocessing.py；核 app/evidence/ocr_adapter.py 的新attempt字段/for_attempt/prepare缓存路径、app/evidence/fingerprint.py、app/domain/contracts/ocr.py 的OCRProfile、app/storage/ocr_repositories.py 的OCRProfileRepository、app/services/evidence_processing_executor.py 的manage_snapshot_status及recover_evidence_ocr_runs、app/services/evidence_progress_service.py、app/api/v2/app.py注册。

相关下游必须核：evidence_sidecar_preparation.py 对重新识别同原件但新OCR的校对/风险继承是否错误；evidence_revision_workflow.py、evidence_activation_service.py 是否确实允许同快照不同base→complete而保持历史。不要仅基于函数名宣称成立。

所有者选择：attempt_namespace显式存OCRProfile payload且进入指纹，旧None序列化不加字段，不加不需检索的数据库列。命名空间以项目+用户幂等请求键哈希，不采“基础修订数+1”，因为失败尚未形成修订会重复计数。先从当前ACTIVE资料发起，执行不再写任何快照状态；同请求复用原Job，源/配置不一致拒绝；重试仍同namespace，取消任务不复用。重试前排除同资料另一活跃尝试。基础结果仍不可自动启用。只读新进度取本次events/runs，不把旧成功页当新完成；原上传进度排除新namespace。已接应用注册，未启动应用；前端接线、批量、新旧对照尚待所有者继续实现。

请指出P0/P1真实问题，准确给文件行、触发情形、最小修正。特别核：pydantic旧hash保持、get/checkpoint/result来源、取消/恢复独立、同参数真实新推理和本次成功页复用、进度不串历史。上一报告“崩溃不会重复付费”不被采纳，返回后但持久化前崩溃仍可能重复调用。ACTIVE限制可能挡住尚未能启用的坏识别，暂不假定全产品范围足够；建议是否可安全支持原处理已终态且有基础修订的候选，给精确已有状态依据。只给源码结论，不写测试不宣称运行/临床验收。
