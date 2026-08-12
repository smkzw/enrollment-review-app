# 数据库规范

## 基线

V2使用 SQLite/WAL、SQLAlchemy 2和Alembic。文件系统只保存原文件、页图和大对象；业务状态、版本、任务、转移和审计关系进入数据库。旧 `projects/` 目录保持只读，不直接迁移为V2事实。

## 事务与写入

- 一次用户动作或一个JobStep的可见状态变化在一个事务内完成。
- 原文件、OCR原文、EvidenceSnapshot、ReviewRun、ActionTransition和AgentCall不可原地覆盖。
- 人工可编辑实体含 `revision`；更新必须携带基础revision，冲突时返回差异。
- 所有可重试写操作使用幂等键；重复请求不得生成重复文档、Job、Action或转移。
- 投影可重建，不反向作为领域真相。

## 查询

- 仓储返回领域对象或明确DTO，不让API组件直接拼SQL。
- 列表查询必须批量加载计数/状态，禁止按受试者逐行N+1查询。
- 临床判断查询必须带方案版本、RuleModelRevision、ReviewEpisode、EvidenceSnapshot和ReviewRun范围。

## 迁移

- Alembic每次只做可解释的小迁移；迁移前自动备份数据库。
- 迁移提供升级、验证和回滚说明；不可通过删除旧列来“清理”历史。
- Phase 2前只定义合同，不创建生产业务表。

## 命名

- 表名复数 `snake_case`；主键采用稳定ID，不以显示编号承担关系主键。
- 外键 `<entity>_id`；时间统一带时区的UTC存储，界面按本地时间显示。
- 枚举值为稳定英文机器值，中文标签由投影词汇表提供。

## 禁止

- mtime作为内容版本；
- 单一overall_verdict覆盖多个审核节点；
- 从Markdown重新解析业务真相；
- 后续阶段静默改写早期ReviewRun。
