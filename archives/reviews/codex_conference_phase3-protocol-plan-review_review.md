# Codex 会商审评：Phase 3 方案解构规划

日期：2026-08-14

## Verdict / 结论

三位参与者均建议“修订后可开始”。共同成立的问题已写回 Trellis 规划；修订后未发现仍需用户作产品选择的阻断项。本任务仍保持 `planning`，等待用户确认后再执行 `task.py start`。

## Boundary Compliance / 边界合规

- CodeBuddy/kimi-k2.6、Pi/cms-router/minimax-m3、Grok Build/grok-4.6 均按用户指定模型实际运行；无 fallback。
- 三者仅阅读工作区内规划、设计和项目指令，未修改产品文件，也未读取工作区外原始临床资料。
- 本轮是规划审评，不宣称完成实际浏览器或医学验收。
- Hermes Workflow Guard 仅负责会商初始化、预检和运行记录；三位指定参与者通过各自原生 CLI/通道路由执行，不经 Hermes 模型替换。

## 参与者输出

- `runs/conference/phase3-protocol-plan-review/codebuddy_kimi26.md`
- `runs/conference/phase3-protocol-plan-review/pi_minimax_m3.md`
- `runs/conference/phase3-protocol-plan-review/grok46_explicit.md`

## 已采纳

1. Agent 前冻结两份独立目录：官方父规则目录、按研究期别和访视实例拆分的基线及以前必做项目录；Agent、用户反馈和修复回路不能删目录项。
2. 完整性检查从“非空”升级为逐项覆盖；占位流程项、只指向标题的来源或缺少逐字摘录均阻止发布。
3. 同一检查在筛选和基线重复执行时保留两个 requirement 实例；去重键包含研究期别和访视实例。
4. “操作无缝”、剂量选择衔接或新受试者继续入组不构成项目合并依据；只有同一受试者队列连续跨期才可提名，默认仍为独立项目。
5. 重新解构校验方案谱系和期别，首次解构检测同方案编号+同一期别正式项目碰撞，防止权威分叉。
6. 来源摘录必须能在文件哈希对应的提取快照中逐字定位；结构定位为主，本次渲染页为辅助。
7. 保存允许不完整草稿，只有发布要求全部阻止项清零；取消明确区分未保存修改和已保存草稿历史。
8. 把真实方案逐项对账、窄屏/缩放冒烟和反向错传用例前移，不把根因发现推迟到最终验收。
9. 增加用户反馈分类和自然中文术语审计。

## 未照搬

1. 未采用“新版本必须与旧版本五字段全部一致”。合法修订必然改变版本、日期或哈希；正确约束是同一方案谱系和研究期别一致，版本身份随新版本追加。
2. 未要求用户指出同一方案解构错误时创建新的 ProtocolDocumentVersion。来源忠实的纠错可保留同一方案版本；超出原文的解释只能进入说明层。
3. 未把 `RuleComponent.display_code` 固定为只允许 `IN-04a` 格式。该格式只是示例，不同方案可能使用其他官方子编号；实施时按父编号和来源层级校验，不写死一种格式。
4. 未新增 `paired_with_professional_judgment` 项目特异字段。现有 AtomicPredicate + ALL 表达式可以表示复合条件；通过冻结原文线索、Gate 和变异测试约束 AND，不复制同一语义。
5. 未在 RuleSet 重复存储方案五字段。RuleSet 继续通过 `protocol_version_id`、权威记录哈希和仓储引用完整性绑定 ProtocolDocumentVersion，避免两个事实源漂移。
6. 未物理删除“取消”的已保存草稿 revision；保留审计历史，仅允许丢弃未保存的前端局部修改。

## Independent Verification / Codex 独立核对

- 只读打开两份真实 DOCX：MG-K10-SAR 页眉包含方案编号和 V2.1/2025-09-19；D001 页眉同时含模板版本与正式方案 V1.0/2025-12-10，证明字段分类而非首个版本号匹配是必要的。
- 旧提取器对 MG-K10-SAR III 返回 IN 7/EX 16，对 D001 II 返回 IN 6/EX 30，但两份研究流程均返回空节点；这直接支持冻结流程目录和逐项覆盖门槛。
- 现有 V2 领域合同已支持 RuleExpression、WorkflowStage、EvidenceRequirement、ProtocolAuthorityRecord 和持久 Job；规划复用这些基座，没有另建平行真相。
- python-docx、LibreOffice、Docling 和 PDF 坐标候选已按官方资料核对能力与许可；主路线仍需在实施切片 1 用真实方案 spike 后最终锁定。

## 最终决定

规划已完成一轮独立挑战和根因修订，可提交用户作 Trellis 开工批准。用户批准后从切片 1 开始，不直接跳到 Agent 或前端工作台。
