# 2026-09-01 SAR 全新方案作业无损暂停检查点

## 暂停状态

- 用户要求立即无损暂停；执行任务 `phase5-sar-fresh-protocol-live-20260901` 已中断，工作者 01 已完成，工作者 02 在运行中被中断，工作者 03 未启动。
- 执行器会话 `26526` 已以 `SIGINT` 退出，退出码 `130`。专用 V2 服务及其子进程均已停止，`8910-8919` 无监听。
- 共享服务未触碰：`8000`、`8001`、`8900` 仍保持监听；`8002` 未启动。
- 不归档本次执行包，不运行执行清理，不改写作业状态，不删除 SQLite、WAL、模型批次、路由审计、渲染文件或执行记录。

## 已持久化业务进度

- 全新数据根：`artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh`。
- 作业：`da944f6e2a504694bbfbc888fa44d184`，类型 `protocol_deconstruction`。
- 已完成：文件登记、结构提取、221 页渲染对齐、方案身份与 III 期确认、身份确认等待、解构输入冻结，共 `6/10` 步。
- 当前暂停点：`generate_draft` 第 2 次尝试；数据库保留现场值 `running / SEMANTIC_DRAFT_MISSING`，租约已随专用服务停止而不再续期。该值是中断现场，不是完成结论。
- 已保存 6 个步骤检查点、17 条作业事件、8 个语义批次文件及完整路由审计。`integrity_check`、`await_review`、`publish` 均未开始。
- SQLite 只读 `PRAGMA quick_check` 返回 `ok`。

## 路由现场与未解决原因

- 本次服务入口声明的复杂路由仍是 `GLM-5.3-Flash high -> MTPLX medium -> DeepSeek V4 Flash high`，跨供应方按完整候选隔离。
- 实际路由审计显示：GLM 首选因专用 V2 进程未读取到 `DECONSTRUCT_GLM_API_KEY` 而跳过；MTPLX 因连接错误失败；DeepSeek 在第 9/10 批因来源闭包错误被门禁拒绝。
- 因此不能把本次运行称为“GLM 主路由已真实执行”，也不能继续 Patient Profile。恢复时应先定位 `.env` 到专用 V2 子进程的配置加载边界，再决定是否恢复现有第 2 次尝试或创建新的受控尝试；不得通过伪造环境、改写审计或拼接既有失败候选绕过。

## 文件完整性锚点

- 主库 SHA-256：`d86917f90d525ec5b1e0e0a2dbe68a2e30b8e3dd8a386e0b05e28d8afd4fcdfb`。
- WAL SHA-256：`bc61291249f2efd672ef68c4d0a31b1d7c70086210854407ce7b2c1d25c790dd`。
- SHM SHA-256：`99f7637cf425071062807e9557ad02473cfcce0e4bfa3efe1902559bed079d7f`。
- 方案副本 SHA-256：`075c93b45414dcb4bb33ef1cf623d295a9d8f029d7560ca484a0c0267c4fdabd`。

这些哈希记录的是 `2026-09-01T18:16:56+0800` 的静止现场；恢复 SQLite 后 WAL/SHM 正常变化不代表源方案变化。

## 恢复入口

1. 先读取本检查点、执行上下文、工作者 01 报告、`job-created.json`、`service-start.json` 和该作业的 `route-audit.json`。
2. 只读核对数据库作业、步骤、事件、租约和既有语义批次，不先清理 WAL，不迁移到旧 `sar31001` 数据根。
3. 修复并验证专用 V2 进程可见 GLM 凭据的配置加载链，验证时只报告“已配置/未配置”，不得打印密钥。
4. 在继续任何远端调用前重新运行全新运行门禁，并明确恢复策略；不得启动工作者 03，直至工作者 02 的业务结果达到可审计终态。
5. 方案规则目录通过完整性检查和人工可读抽查后，才进入 31001 事实规范化与 Patient Profile。

Phase 5 保持 `claims_complete=false`；D001 第 20 包、旧 SAR 失败作业和 31001 下游处理均未恢复。
