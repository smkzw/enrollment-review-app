任务已完成。以下是执行报告。

# 执行输出: r05-project-report-catalog-20260915 - worker_01

## 边界与上下文检查

- 回退声明: 主角色 `codebuddy/codebuddy-cli/deepseek-v4.1-flash` 在会话存在前不可用；本次执行按回退覆盖以 `zcode` / `GLM-5.3-Flash` 完成，保持同一有界角色、源清单、输出路径、质量门与会议回避协议。所配能力（文件读写、搜索、终端）足以完成本项工作，无能力缺口影响交付；未做本授权外的操作。
- 工作目录绑定 runner 授权的 worktree（`enrollment-review-app/.worktrees/phase5-clinical-facts-profile`）。未读取 `~/.codex/AGENTS.md`、`~/.hermes/SOUL.md`，未启动会议，未联网。
- 初始读取集两份文件均已读取（execution context、execution plan）。目标文件创建前核实不存在（`ls` 报 No such file）→ 按合同新建而非覆盖。
- 只读参考均已按需读取: `app/services/recent_project_reviews.py`（全）、`app/services/review_history_service.py`（全，含 `get_run`/`ReviewHistoryIncompleteError`）、`app/services/review_action_worklist.py:1-120`（`_workflow_stage_label`）、`app/storage/models.py`（`ReviewRunRecord:1019`、`ReviewEpisodeRecord:128`、`ReviewContextSnapshotRecord:1357`、mixin 与文件头约定）、`app/storage/review_context_repository.py`（全）、`.trellis/spec/backend/index.md`（全）；按引用扩读: `app/domain/contracts/review_context_v2.py`（冻结上下文合同）、`app/domain/contracts/review.py:1-115`（`Subject.center_code:82`、`ProtocolDocumentVersion.official_version:59`、`ReviewRun` UTC 约束:172-173）、`app/storage/codecs.py`（全，`to_utc_naive`/`parse_datetime_column`）、`app/storage/repositories.py`（`REVIEW_RUN_CONFIG:1235`、`ProjectRepository:1791`）、`app/storage/db.py`（PRAGMA 合同）。

## 已执行的工作

新增唯一源码文件 `app/services/project_report_catalog.py`（约 170 行），实现正式已保存项目报告的只读目录服务:

- **导出函数** `list_project_reports(session, *, project_id, center_code=None, before_completed_at=None, before_run_id=None, limit=20) -> ProjectReportPage`，与两个 frozen dataclass `ProjectReportEntry`（9 个合同字段逐一如规格）、`ProjectReportPage(items, next_cursor: tuple[datetime,str]|None)`。
- **参数校验**: `limit` 1..50；两游标必须同时提供（缺一抛 `ValueError`）；`before_completed_at` 必须携带 UTC 时区（naive 或非零 offset 拒绝）；SQL 绑定前用既有 `to_utc_naive()`（`app/storage/codecs.py:78`）归一化为 UTC naive，与时间列存储约定一致。
- **项目存在性**: 先 `ProjectRepository(session).get(project_id)`（缺失由存储层 `NotFoundError` 翻译为稳定 404，同 `recent_project_reviews` 先例）。
- **SQL 候选查询**: 按 `completed_at DESC, review_run_id DESC` keyset（游标谓词 `or_(completed_at < c, and_(completed_at == c, review_run_id < r))`），固定 `limit+1` 判 has_more。过滤: `ReviewEpisodeRecord.project_id == project_id`（同节点项目关系，与近期记录预览一致）+ `evidence_snapshot_v2_id IS NOT NULL`（V2 资料链；表级 CHECK `ck_review_runs_context_lineage` 保证 context_id 同非空）+ `completed_at IS NOT NULL`。全程 SQLAlchemy 表达式，无字符串拼 SQL，无全项目 load 后过滤。
- **中心过滤按冻结值**: inner join `ReviewContextSnapshotRecord`（经 `context_id` FK；`PRAGMA foreign_keys=ON` 由 `app/storage/db.py:46` 保证引用完整），用既有项目惯例 `func.json_extract(payload_json, "$.subject.center_code") == center_code`（先例: `prepared_review_workflow.py:81` 等 10 处同库同列用法），过滤的是冻结上下文里的中心，不读 `Subject` 登记现值。
- **逐条 get_run 核查**: 候选页内每条调用 `review_history_service.get_run`，逐项核对项目（`detail.context.authority.project_id`）、中心（`detail.context.subject.center_code`）、完成态（`detail.run.completed_at`）；任一不符显式抛现有错误 `ReviewHistoryIncompleteError`（带 `review_run_id`），不跳过当空。legacy/trial 记录不会到达核查（SQL 已排除；即便混入也由 `get_run` 的 `_require_v2_run` 抛 `ReviewHistoryUnsupportedError`）。
- **冻结值取数**: `subject_code`/`center_code`/`center_name` 取冻结 `context.subject`，`official_protocol_version` 取冻结 `context.protocol_document.official_version`，`workflow_stage_label` 复用 `_workflow_stage_label`（冻结 `context.workflow_stages`）；不读登记现值。
- **不去重**: 同一受试者不同日期/审核节点的正式报告全部列入，导出勾选留给 UI 所有者；无总完成率、无总体入排结论、无"每例最新"折叠。
- 未写 API/前端/测试，未启动 DB/模型/浏览器，未新增依赖，未改任何其他文件。

## 产物与证据

- **产物**: `app/services/project_report_catalog.py`（新建，7738 字节，git 状态 `??` 未跟踪新文件）。
- **冻结中心查询路径存在性证据**（合同要求若不存在须证据返回——已存在，不触发返回）: `Subject.center_code: str|None` 定义于 `app/domain/contracts/review.py:82`；`ReviewContextSnapshotV2.subject: Subject`（`review_context_v2.py:79`）经 `model_dump(mode="json")` 落入 `payload_json`，路径 `$.subject.center_code` 可查。
- **cursor 回传一致性**: `next_cursor` 里的 `completed_at` 是合同值（UTC-aware，`ReviewRun` 合同 `_require_utc` 强制），用户原样回传后经 `to_utc_naive` 再绑定，往返语义一致。
- **已知权衡（供 Codex 审核）**: inner join 意味着若某 V2 run 的 context 行物理缺失会被 SQL 阶段静默排除——该情形被 `PRAGMA foreign_keys=ON`（FK 违例无法插入）+ 同事务写入路径排除；这与 `recent_project_reviews.py` inner join episode 的既有惯例一致。若 Codex 要求目录对"引用行缺失"也大声失败，需要改为 LEFT JOIN + 显式检测，属规格变更，未擅动。

## 命令与观察

- `ls app/services/project_report_catalog.py` → 不存在（创建前核验）。
- `rg "_workflow_stage_label|json_extract|to_utc_naive|foreign_keys"` 等多次定点检索 → 确认 `func.json_extract` 为既有生产惯例（10 处），`to_utc_naive` 为时间归一惯例，`PRAGMA foreign_keys = ON` 为存储层合同，`list_project_reports`/`ProjectReportEntry` 等命名无冲突。
- `.venv/bin/python -m py_compile app/services/project_report_catalog.py` → **PY_COMPILE_OK_VENV**（合同允许的唯一检查）。
- 过程中自纠一处缺陷: 首稿游标谓词误用 Python `and` 连接两个 SQLAlchemy 表达式（运行时会抛 `TypeError`），已改为 `and_(...)` 后再编译。
- `git status --porcelain` → 本会话仅新增上述一个源码文件；worktree 中大量 `??`/`M` 均为先前阶段遗留，未触碰。副作用说明: py_compile 在已存在的 `app/services/__pycache__/` 下生成对应 `.pyc`（该目录已 gitignore，不构成仓库改动）。

## 阻碍或缺失环境

- 无阻碍。合同限定"仅 py_compile"为唯一验收检查，因此**以下未经我验证**: 对真实项目 DB 的运行时行为（`json_extract` 命中、分页正确性、错误路径）。依据: 同库同列 `func.json_extract` 已在 `prepared_review_workflow.py`、`batch_review_workflow.py` 等生产路径承担同等查询，JSON1 可用性是项目既定事实；逻辑核对均以源码证据为准。DB/模型/测试/浏览器按合同未启动。

## 重跑请求或下一步

- 无重跑请求。建议 Codex 验收要点: (1) 审阅 `next_cursor` 语义（取自页末 Entry 的 `(completed_at, review_run_id)`）与合同一致；(2) 裁定上文"inner join 权衡"是否接受；(3) 后续如需 API/测试接线，另行派发（本合同禁止，未做）。
