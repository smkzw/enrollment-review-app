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
- 迁移前使用SQLite backup API生成一致备份并校验文件大小、SHA-256和`PRAGMA integrity_check`；不得直接复制活跃WAL主文件。
- Alembic执行成功后仍须校验PRAGMA、实际schema与ORM metadata及基础读写；任何一步失败均自动恢复迁移前备份并阻止写服务启动。
- 首次建库失败没有旧备份时，必须清除主库及WAL/SHM半成品，恢复到“尚未初始化”，不得留给下次启动猜测。
- 迁移提供升级、验证和回滚说明；不可通过删除旧列来“清理”已经投入使用的历史。
- 尚未写入真实业务数据的绿地迁移允许在本阶段内修正，但必须重建独立V2数据库并记录决定；一旦进入真实使用，只能新增迁移，不能改写既有版本。
- SQLite 重建被其他表引用的父表时，必须保留子行、恢复外键开关并执行 `PRAGMA foreign_key_check`；任一步失败即恢复备份。含当前版本正式数据时，有损降级必须明确拒绝，不能静默丢表、丢列或丢历史。

## 运行约定

- V2数据根为`data_v2/`或`ENROLLMENT_V2_DATA_DIR`显式指定目录，与legacy `projects/`物理隔离。
- 每个连接实测`foreign_keys=ON`、`journal_mode=WAL`、`synchronous=FULL`、`busy_timeout=10000`。
- 当前SQLite运行时不得低于3.51.3；不满足时以中文说明阻止V2写服务启动。
- 规范化关键列与canonical JSON/hash同时保存；读取先验hash，再用Pydantic合同还原并交叉校验镜像列，不一致时拒绝发布。
- 不可变记录的直接读取、列表、计数和链头查询必须执行同一套列/正文镜像校验。不能先用可能漂移的规范化列过滤后把坏行静默隐藏；正文自带的创建时间也属于不可变镜像。
- 可重建投影仍须在物理表上强制其真实父关系和必要非空字段。应用层的来源闭包与语义校验不能替代 RuleSet、资料要求、审核节点等数据库外键。
- Agent 候选的 canonical payload 必须自带并镜像校验 `run_id / call_id / candidate_kind / created_at`；候选行使用复合外键证明调用确实属于该运行，不得只靠两个独立外键拼接出伪来源。
- 使用类型判别列的关联表仍须有真实父外键：每种类型使用独立可空父 ID，由 `CHECK` 约束类型、通用 ID 与唯一非空父 ID 一致；不得仅保存无外键的 `entity_kind + entity_id` 或 `target_kind + target_id`。

## 命名

- 表名复数 `snake_case`；主键采用稳定ID，不以显示编号承担关系主键。
- 外键 `<entity>_id`；合同中的时间保留带时区 UTC。SQLite 的 `DateTime` 物理列统一存储为 UTC 无时区值，仓储写入前归一化，API/领域边界恢复为带 `UTC` 的时间，界面再按本地时间显示；不得让浏览器自行猜测无时区时间。
- 枚举值为稳定英文机器值，中文标签由投影词汇表提供。

## 禁止

- mtime作为内容版本；
- 单一overall_verdict覆盖多个审核节点；
- 从Markdown重新解析业务真相；
- 后续阶段静默改写早期ReviewRun。
## 规范化作用域与过期原因

- `ReviewRun` 通过唯一的 `review_episode_id` 继承该审核节点绑定的 `rule_set_id`，并保存实际使用的 `rule_set_revision`。不要在运行记录中重复保存 `rule_set_id`，避免两个字段形成冲突的双重真相。
- stale 原因中的 `source_revision` 是内部不可变修订，不是方案封面上的展示版本号。同一来源实体、同一内部修订、同一原因在被 ReviewRun 覆盖后保持关闭；只有新的来源修订或不同原因才打开新的提醒。
- 若外部文件撤回后重新发布，即使封面版本号不变，也必须生成新的内部来源修订，保留两次发布的证据链。
