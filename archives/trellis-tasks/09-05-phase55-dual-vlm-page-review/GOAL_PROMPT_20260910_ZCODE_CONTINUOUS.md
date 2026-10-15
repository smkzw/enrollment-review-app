# Goal Prompt：ZCode 接管连续实施（2026-09-10）

> 本文件是产品线程的当前 goal 文本载体（平台 goal 若支持编辑，以本文件替换旧 objective；旧 goal 的 MTPLX/MiniMax/手写第三读文字均已失效）。依据：HANDOFF_20260910 §14 建议 + 接管审查 ENGINEERING_REVIEW_20260910_ZCODE_TAKEOVER.md。

在唯一 worktree phase5-clinical-facts-profile 中，按 R3 设计与 09-05 恢复计划接管入排审核系统连续实施。保留共享未提交工作、原始研究方案/病例/数据库和全部失败证据。Phase5/5.5 未临床收口，claims_complete=false。产品仅 GLM-5.3-Flash low 与 Gemini-3.7-Flash high 独立直连（显式 env/OAuth），不使用个人 OMP/Hermes 作为产品 harness，不启动其他线程本地模型。

当前执行单元（审查§5 五切片，全部复用既有 JobRunner/ArtifactStore/EvidenceExpectation 模式，不新增叶子合同框架）：
1. 判断检索持久作业（job type + payload 冻结 + executor + 取消/租约/恢复）；
2. 正式 API（POST/GET，服务端派生权威，幂等）；
3. professional_judgment 缺口消费（双读完整、当前适用、确需书面判断且未见 → 限定"本次提交资料"的无法判定原因；缺文件/未读清/未到期互不覆盖）；
4. Profile 待办汇总卡 + 全中文文案 + 术语统一（快照→完整资料集、读法→识别结果）；
5. runtime05 后继或新受控实例的真实全链验证。

之后按交接§8 第四/五步：31001 原件 QC 与 Phase5 收口判断 → 当前组合必要产品金标/大屏验收 → Phase6–9。用药分项匹配保持隔离，先新留出评测、后向用户申请正式采信。暂缓广泛横评、新 harness 迁移。

医学边界不变：无判断不等于阴性，未核实不等于缺失，条件适用不明不猜测，后期资料不静默改写早期结论。按全局执行/会商机制：执行单元 inline 完成，冻结结果后按 manifest 路线做一次独立审阅；长任务最多 120 分钟等待、收到终态接续，不反复自行暂停。测试计数只作证据附录，验收以"正式入口可用、临床来源核对、界面可见中文原因"为准。任何未完成不得用完成标记或漂亮页面代替。
