# Phase 2 SQLite领域层与持久任务

## Goal

为本机单用户 V2 建立可恢复、可追溯、不会静默覆盖的持久化基座，使后续方案解构、资料上传、OCR、事实抽取、分阶段入排审核和报告都能共享同一版本化事实源；浏览器关闭、服务重启、重复提交或并发编辑均不得破坏任务或临床记录。

## Background

- Phase 0.5 已冻结 V2 领域、Agent、Gate、证据、审核节点和 UAT 合同；Phase 1/1.5 已验证合成交互原型并允许进入 Phase 2。
- 当前 legacy 仍以 `projects/` 文件、Markdown 和请求内 SSE 流程为主，只作为只读反面锚点，不迁移成 V2 业务真相。
- 依赖已固定为 Python 3.12、SQLAlchemy 2.0.52、Alembic 1.19.1；项目 `.venv` 的 SQLite 为 3.53.1。

## Requirements

### 数据边界

- V2 数据进入独立 `data_v2/` 根目录；SQLite、备份和大对象目录不得与 legacy `projects/` 重叠。
- 数据库保存业务状态、关系、版本、任务、状态转换和审计；文件系统只保存原文件、页图、OCR大对象及可再生导出。
- 旧项目不自动导入、不写回；本阶段不创建真实临床项目或运行真实审核。

### 领域持久化

- 建立 Project、ProtocolDocumentVersion、RuleSet/RuleExpression、EvidenceRequirement、Subject、ReviewEpisode、EvidenceSnapshot、SourceDocumentVersion、EvidenceSpan、ClinicalFact、EvidenceExpectation、ReviewRun、FinalAssessment、ActionRequest/Transition、ReviewRunDiff、PromptVersion、ModelConfig、AgentCall、GateResult、Job/Step/Checkpoint/Event 等核心表。
- 复杂且已由 Pydantic 契约验证的不可变内容使用规范化检索字段加 canonical JSON payload/hash；关键关系必须有真实外键，不能只靠 JSON 中的 ID。
- 原文件版本、EvidenceSnapshot、EvidenceSpan、ClinicalFact、ReviewRun、FinalAssessment、ActionTransition、AgentCall、GateResult 和 JobEvent 追加写，不原地覆盖历史。
- 所有读取必须保留 project、protocol version、rule revision、episode、snapshot 和 review run 范围，不得重新引入单一 overall verdict。

### SQLite 与迁移

- 所有连接启用外键、WAL、忙等待和明确同步级别；写事务短小，一次用户动作或一个 JobStep 的可见变化在同一事务提交。
- 启动时验证实际 SQLite 运行时满足 WAL 正确性基线；不合格时以中文说明阻止 V2 写服务启动。
- Alembic 初始迁移可升级、校验和降级；每次迁移前用 SQLite backup API 创建一致备份并校验完整性，不能直接复制活跃 WAL 数据库主文件。
- 迁移失败不得继续启动业务写服务；保留原库和备份，提供明确恢复命令。

### Job 与恢复

- 用户动作先创建持久 Job，再由后台执行；SSE 只订阅按序 JobEvent，浏览器断开不取消 Job。
- JobStep 有依赖、尝试次数、可重试标记、进度和错误分类；每个成功步骤写持久 Checkpoint。
- 数据库租约包含 owner、到期时间和 generation；只有当前租约持有者可提交步骤结果或续租。
- 服务重启后识别过期租约并从最后成功 Checkpoint 恢复；不得保留永久 `processing`。
- 取消为持久请求，在安全步骤边界转为 cancelled；已提交检查点和历史事件保留。

### 幂等、并发与 stale

- 可重试创建使用作用域化 idempotency key 和请求 hash；同键同内容返回同一结果，同键不同内容明确冲突。
- 人工可编辑记录使用 `revision` 乐观并发；更新必须携带打开时 revision，旧 revision 返回当前值与字段差异，不静默覆盖。
- 文档、事实、规则或锚点变化后，受影响且尚未完成新 ReviewRun 的实体进入结构化 stale 记录；完成覆盖范围内的新 ReviewRun 后才可关闭。

### 用户体验与接口

- V2 API 错误使用自然中文问题、影响和恢复动作；不向页面暴露 SQL、堆栈、枚举或日志词。
- Job 查询返回当前状态、总体进度、步骤、可重试范围、最近事件和恢复动作；事件序号支持断线续订。
- 当前 Phase 1 前端仍可用 stub；本阶段只增加持久 API/服务和必要的最小任务订阅适配，不提前实现 Phase 3 方案解析或 Phase 4 OCR。

## Acceptance Criteria

- [ ] 初始迁移在空库升级成功，schema 与 ORM metadata 一致，可降级回空基线并再次升级。
- [ ] 每次迁移前生成经过 `PRAGMA integrity_check` 验证的一致备份；模拟迁移失败时原库仍可读且不会继续启动写服务。
- [ ] 所有连接实测 `foreign_keys=ON`、`journal_mode=wal`、配置的同步级别和 busy timeout；运行时 SQLite 版本门禁通过。
- [ ] 核心领域 fixture 可持久化后完整往返，关键 ID/版本/日期精度/枚举/payload hash 不丢失；非法跨项目、跨方案版本或跨审核节点关系被外键或服务校验拒绝。
- [ ] 重复同内容请求只产生一个 Job、文档或 Action；同幂等键不同请求返回冲突。
- [ ] 强制终止服务后，过期租约 Job 从最后成功 Checkpoint 恢复；已完成步骤不重复执行，不存在永久 processing。
- [ ] 关闭 SSE 客户端不影响 Job 继续；以 `after_seq` 重连能补齐事件且不重复、不乱序。
- [ ] 取消只在安全边界生效并保留历史；可重试失败只重跑失败范围。
- [ ] 两个会话以相同 revision 编辑时，后提交者收到最新 revision 和字段差异；数据库内容不被静默覆盖。
- [ ] 上游版本变化产生准确 stale 影响范围，新 ReviewRun 完成后只关闭其覆盖的 stale 项。
- [ ] legacy `projects/` 树在完整测试前后哈希一致，V2 只写声明的数据根目录。
- [ ] 后端单元、迁移、故障注入、仓储集成、API/SSE 和启动恢复测试全部通过；独立 checker 复核后才关闭 Phase 2。

## Out Of Scope

- 真实方案上传/解构、II/III 期识别、规则发布属于 Phase 3。
- 原始资料上传、OCR、页图与 EvidenceSpan 实际生成属于 Phase 4。
- 真实 Patient Journey 抽取、Agent 审核、报告生成和真实项目回归属于 Phase 5-8。
- 多用户、登录、权限、安全或生产部署不在本任务范围。

## Deferred Items

- 复杂查询性能、前端分页和大规模批处理吞吐在真实数据进入后量化；本阶段先保证正确性、恢复性和无 N+1 的仓储接口。
- WAL 手动 checkpoint 策略先使用 SQLite 默认自动 checkpoint，并提供观测/维护入口；只有压力测试证明需要时才改为独立调度。
