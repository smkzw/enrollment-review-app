# Execution Output: phase5-sar31001-real-acceptance-20260901 - worker_01

## Boundary And Context Check

- 工作目录为 runner 绑定的 `.worktrees/phase5-clinical-facts-profile`，全部操作只读（Read/Grep/Bash 读取与一次 `import` 自检），未创建、未修改任何源文件或临床资料。git 状态中的既有改动（`M`/`D`/`??`）均为分支持续工作既有内容，与本次会话无关。
- 未读取生产路径、未启动 D001、未启动任何模型服务、未启动 V2 服务（启动服务会对数据根做迁移写入，违反本工作项“不修改文件”边界，故只做静态梳理 + import 自检）。
- 已读初始读集两份文件；额外阅读范围均在仓库内：`app/api/v2/*.py`、`app/services/` 相关模块、`app/storage/config.py`、`app/storage/migrate.py`、`app/config.py`、`app/services/omlx_gate.py`、`app/agents/deepseek_evidence_normalizer_transport.py`、`tools/phase5_acceptance/run_packet.py`、`scripts/`（slice7/mgk10sar/phase5 probe/启动脚本）、`tests/v2/api/`、`frontend/playwright.real.config.ts`。

## Work Performed

只读梳理出「SAR 方案 DOCX → III 期正式项目 → 单例资料导入 → 冻结修订 → 事实规范化 → 读取 Patient Profile」的真实 V2 API 全序列与服务启动顺序，并逐端点标注失败信号。关键结论：

**A. 服务启动顺序（真实验收所需）**

1. **后端 V2 API 是唯一必需服务**，无现成启动器，需手写命令（证据 `app/api/v2/app.py:12` 工厂说明 + `frontend/playwright.real.config.ts:29` 真实 e2e 的启动范式）：
   ```
   ENROLLMENT_V2_DATA_DIR=<隔离数据根> .venv/bin/uvicorn app.api.v2.app:create_app --factory --host 127.0.0.1 --port <port>
   ```
   就绪探测：`GET /docs` 返回 200（playwright.real.config.ts 用此 URL）。lifespan 内完成：迁移到 head + schema 校验（`upgrade_or_fail`，失败拒绝启动）→ 过期租约任务恢复 → 启动后台 JobRunner 线程（`run_runner=True` 默认开启，会自动领取并执行所有持久任务）。
2. **三个本地模型依赖**（真实推理验收必需；不启动则对应任务失败，均为可重试/显式失败，不会静默绕过）：
   - 方案解构：`DECONSTRUCT_BACKEND` 默认 `mtplx` → `MTPLX_BASE_URL` 默认 `http://127.0.0.1:8002`（`app/config.py:119,42`）；
   - 证据 OCR：oMLX，`OMLX_BASE_URL` 从 `~/Library/Application Support/oMLX/config.json` 的 port 发现，回退 `http://127.0.0.1:8000`（`app/config.py:20-38`），且硬依赖共享门禁脚本 `~/.codex/tools/omlx_workload_gate.py`（缺失即 `OmlxGateUnavailableError`，`app/services/omlx_gate.py:26`）；
   - 事实规范化：`EVIDENCE_NORMALIZER_PROVIDER` 默认 `mtplx`（同一 8002 服务）；prompt/model 配置在 V2 启动时幂等登记（append-only，合同漂移则拒绝启动，`fact_normalization_command_service.py:287-329`）。
3. **运行时门槛**：Python 3.12（pyproject）+ SQLite ≥ 3.51.3（`app/storage/config.py:35` 启动强校验）。本 worktree `.venv` 实测 uvicorn 0.39.0 / SQLite 3.53.4，`from app.api.v2.app import create_app` import 通过。
4. **数据根边界**：`ENROLLMENT_V2_DATA_DIR` 指向 worker_02 制作的隔离副本根（标准布局 `<root>/enrollment-review-v2.sqlite3` + `blobs/`）；与 legacy `projects/` 重叠抛 `DataDirError`（`app/storage/config.py:38,101-115`）。
5. **前端无关本项**：`scripts/start_v2_uat.sh` 只用系统 python 静态服务 `frontend/dist`（不代理后端）；`run.sh` 与 `scripts/run_enrollment_review_service.sh` 均为 legacy `app.main:app`（8900/8901），**不是** V2 后端启动器——这是主线程最容易踩的错。API 级验收只需第 1 条命令。
6. **导出时序约束**（来自 `tools/phase5_acceptance/run_packet.py` 模块 docstring）：导出验收包前必须先停 V2 服务让 SQLite WAL 落盘，只读打开否则大声失败。

**B. API 调用序列（17 步，均有代码/脚本证据）** — 详见 Artifacts 节命令表；方案侧序列与 `scripts/run_phase3_slice7_full_acceptance.py`（MG-K10 SAR III 真实案例 `mg-iii`）一致，证据/冻结/规范化侧与 `tests/v2/api/test_slice44_api.py`、`test_evidence_api.py`、`test_fact_normalization.py`、`test_patient_profiles.py` 的合同一致。

**C. SAR III 特有阻塞点**：slice7 记录 MG-K10 SAR 方案解构完整性检查必有 `TIME_ANCHOR_UNRESOLVED` 阻止发布项（`scripts/run_phase3_slice7_full_acceptance.py:74`），需先 `PUT .../draft`（手工编辑）或 `POST .../draft/feedback` 解决时间锚点问题使 `publishable=true` 才能发布——真实验收不能直接 publish。

## Artifacts And Evidence

无新建产物（本项为只读梳理）。核心证据文件：

| 结论 | 证据位置 |
|---|---|
| V2 启动命令与 lifespan 序列 | `app/api/v2/app.py:12,134-304` |
| 数据根解析/迁移门禁/SQLite 版本门禁 | `app/storage/config.py:20-38,101-115`；`app/storage/migrate.py:513-532` |
| 方案侧 API（上传→身份→确认→草稿→完整性→发布） | `app/api/v2/protocols.py:346-588` |
| 受试者创建自动实例化审核节点 | `app/services/evidence_api_command_service.py:734-774` |
| 上传预览/确认/快照 API | `app/api/v2/evidence.py:307-467` |
| 构建/激活(冻结)修订 API | `app/api/v2/evidence_processing.py:660-703,821-859` |
| 事实规范化任务 API + 权威派生前置 | `app/api/v2/fact_normalization.py:41-73`；`fact_normalization_command_service.py:445-480,502-548` |
| Patient Profile 读取 API | `app/api/v2/patient_profiles.py:87-155` |
| Profile 由规范化执行器生成 | `app/services/fact_normalization_executor.py:77-81,644-690` |
| OCR 门禁/oMLX/MTPLX 依赖 | `app/services/omlx_gate.py:26-31,281-340`；`app/config.py:37-47,119,137-141` |
| 真实调用顺序范本 | `scripts/run_phase3_slice7_full_acceptance.py:243-381`；`frontend/playwright.real.config.ts:29` |
| 导出前必须停服（WAL） | `tools/phase5_acceptance/run_packet.py:31-35` |

## Commands And Observations

以下为交付主线程的精确命令序列（`$BASE` = `http://127.0.0.1:<port>`；`$EP` = review_episode_id；`jq` 可选）。失败信号统一为中文错误信封 `{"error":{"code","title","detail","recovery_action","correlation_id","context"}}`（`app/api/v2/errors.py:240-268`）。

**阶段 A：从 SAR DOCX 创建 III 期正式项目**

1. 启动（见 Work Performed A-1；先起 MTPLX:8002，OCR 阶段前起 oMLX）。
2. 上传方案并启动解构任务：
   ```
   curl -s -X POST $BASE/api/v2/protocol/deconstructions \
     -F idempotency_key=sar31001-deconstruct-20260901 \
     -F actor=医学监查员验收 \
     -F file=@"<SAR方案DOCX隔离副本路径>"   # → 201 {job_id}
   ```
   失败信号：MTPLX 未起 → 任务 `failed_retryable`（GET `/api/v2/jobs/{job_id}` 看 `error_code`）；同幂等键回放返回 200。
3. 轮询 `GET $BASE/api/v2/protocol/deconstructions/{job_id}` 直至 `awaiting_user=="identity"`。失败信号：`state ∈ {failed,failed_final,cancelled}` → 查 `/api/v2/jobs/{job_id}` 的 `error_code/error_classification`。
4. `GET .../identity` → 核对 `identity.protocol_code=="MG-K10-SAR-001"`，且 `phase_candidates` 含 `phase_iii`。
5. 确认 III 期身份（枚举值 `phase_iii`，来自 `enums.py:10`；slice7:293-306 为字段范本）：
   ```
   curl -s -X POST $BASE/api/v2/protocol/deconstructions/{job_id}/identity/confirm -H 'content-type: application/json' -d '{
     "protocol_code":"MG-K10-SAR-001","project_code":"MG-K10-SAR","project_name":"…",
     "official_version":"V2.1","official_date_value":"2025-09-19","official_date_precision":"day",
     "study_phase":"phase_iii","selected_candidate_ids":[…],"actor":"医学监查员验收"}'
   ```
6. 轮询 session 至 `awaiting_user=="review"`（解构多批次走 MTPLX，slice7 用 limit=80）。
7. `GET .../draft`（校验 IN/EX 官方编号）与 `GET .../integrity`。**预期失败信号（SAR 特有）**：`issues` 含 `issue_code=="TIME_ANCHOR_UNRESOLVED"`、`publishable==false` → 必须先 `PUT .../draft`（`ManualEditRequest`，带 `expected_revision_id`）或 `POST .../draft/feedback` 修复，重查 integrity 直至 `publishable==true`。
8. 发布：`POST .../publish -d '{"idempotency_key":"sar31001-publish-20260901","actor":"…"}'` → `{project_id, protocol_version_id, rule_set_id, rule_set_revision, replay}`。重放同键必须 `replay==true`（幂等校验点）。

**阶段 B：单例 31001 资料导入**

9. 建受试者（自动按已发布 RuleSet 的 `review_required` 流程节点实例化审核节点）：`POST $BASE/api/v2/projects/{project_id}/subjects -d '{"subject_code":"31001","center_code":"31","center_name":"河北省中医院"}'` → 201 `{subject_id}`。失败信号：项目未发布/不存在 → 4xx `AppInvalidReferenceError`。
10. `GET $BASE/api/v2/subjects/{subject_id}/review-episodes` → 选筛期节点（`stage=="screening"`），记 `review_episode_id`、`revision`、`active_evidence_snapshot_id`（此刻应为 null）。
11. 上传预览（`upload_mode ∈ {full,incremental}`，`base_revision` = 节点当前 `revision`，≥1）：
    ```
    curl -s -X POST $BASE/api/v2/subjects/{subject_id}/evidence-upload-previews \
      -F review_episode_id=$EP -F upload_mode=full -F base_revision=<ep.revision> \
      -F actor=医学监查员验收 -F files=@"<文件1>" -F files=@"<文件2>"…
    ```
    → 201 `{preview_id, preview_sha256, items[]}`。失败信号：空文件列表 422 `EMPTY_UPLOAD`；节点/受试者不匹配 404。
12. 确认（触发快照+base 修订+OCR 持久任务）：`POST $BASE/api/v2/evidence-upload-previews/{preview_id}/commit -d '{"preview_sha256":"<64hex>","upload_mode":"full","base_revision":<同上>,"idempotency_key":"sar31001-commit-1","resolutions":{}}'` → 201 `{evidence_snapshot_id, job_id}`。失败信号：`base_revision` 落后 → 409 `AppStaleRevisionError`（信封保留服务端当前值与差异）。
13. 轮询 `GET $BASE/api/v2/jobs/{job_id}` 至 `succeeded`；进度 `GET $BASE/api/v2/jobs/{job_id}/evidence-progress`。失败信号：oMLX/门禁缺失 → `failed_retryable` + `error_code`（门禁脚本缺失类）；个别页失败会以页状态显式呈现（`failed_pages`），不会伪装完成。

**阶段 C：冻结修订（complete 修订构建 + 激活）**

14. `GET $BASE/api/v2/evidence-snapshots/{snapshot_id}` 取 `base_processing_revision_id`，然后构建完整修订：
    ```
    POST $BASE/api/v2/evidence-processing-revisions/build -d '{
      "evidence_snapshot_id":"<sid>","base_processing_revision_id":"<base_rid>",
      "expected_revision":<ep.revision>,"idempotency_key":"sar31001-build-1","actor":"…"}'
    ```
    → 201 `{candidate_id, job_id, candidate_status, complete_revision_id}`。失败信号：`expected_revision` 过期 → 409；风险待核对时候选停在 `waiting_review`（按 gate 提示走 risk-review API 后同候选续建）。
15. 轮询 `GET $BASE/api/v2/evidence-processing-candidates/{candidate_id}` 至 READY；`GET $BASE/api/v2/evidence-processing-revisions/{complete_revision_id}` 核对 `is_activatable==true` 与逐门禁 `gates[]` 全过。
16. 激活（切换节点成对活动指针，即“冻结/启用"）：
    ```
    POST $BASE/api/v2/evidence-processing-revisions/{complete_revision_id}/activate -d '{
      "expected_revision":<ep.revision>,"idempotency_key":"sar31001-activate-1",
      "reason":"SAR 31001 筛期资料完整性确认","actor":"…","candidate_id":"<cid>","job_id":"<jid>"}'
    ```
    → 201 激活事件（`from/to` 指针对 + `resulting_episode_revision`）。失败信号：base 修订 → 409 `NonCompleteRevision409Error`；`expected_revision` 过期 → 409；重复激活同键回放 200。

**阶段 D：事实规范化（自动生成 Patient Profile）**

17. `POST $BASE/api/v2/subjects/{subject_id}/review-episodes/$EP/fact-normalization-jobs -d '{"idempotency_intent":"sar31001-run1"}'` → 201 `{job_id, run_id}`（`idempotency_intent` 仅标记，不参与权威）。**前置失败信号（最常见）**：未先激活 → 错误信封“该审核节点还没有启用完整资料版本…"；活动指针在建任务前变化 → “活动证据…已变化”（409 `AppStaleAuthorityError`）。随后轮询 `/api/v2/jobs/{job_id}` 至 `succeeded`（执行器发布 facts/events/exposures/conflicts 并生成 Profile revision）。

**阶段 E：读取 Patient Profile**

18. `GET $BASE/api/v2/subjects/{subject_id}/review-episodes/$EP/patient-profile` → 链头 Profile（含逐条 locator 定位详情）。失败信号：未生成 → 404 信封“该审核节点还没有生成病历档案”；历史 `GET .../patient-profile/history`（未生成返回空列表不报错）；冻结回放 `GET /api/v2/subjects/{subject_id}/patient-profile-revisions/{id}`。

**观测补充**：(a) 本 worktree `.venv` import 自检通过、SQLite 3.53.4 ≥ 3.51.3 门禁；(b) `scripts/mgk10sar_phase3_rerun.py`（8900 legacy API）与 V2 无关，不可作为 V2 验收路径；(c) SSE 备选 `GET /api/v2/jobs/{job_id}/events`（`Last-Event-ID` 续订，终态发 `done` 事件），长任务可替代轮询。

## Blockers Or Missing Environment

- **无阻断**（本项为只读梳理，未执行需写权限的步骤）。以下为真实验收执行期（主线程阶段）的环境前置，非本 worker 阻断：
  1. 仓库无 V2 后端启动脚本/launcher（run.sh 系列均 legacy）——主线程需直接用 Work Performed A-1 命令；建议后续由 Codex 决定是否补一个 `scripts/start_v2_api.sh`（本次未创建，避免越界）。
  2. 需确认 MTPLX(8002)、oMLX(发现端口)、`~/.codex/tools/omlx_workload_gate.py` 三者在验收时段可用（按边界本次未探测、未启动）。
  3. `TIME_ANCHOR_UNRESOLVED` 为 MG-K10 SAR III 方案解构的预期阻止发布项，主线程必须计划一次人工修订步骤（slice7 仅记录未演示修复路径）。
- 不确定性标注：identity confirm 的 `project_name` 等 SAR 元数据期望值取自 slice7 CASES（推断适用，因为同方案文件）；`resolutions` 冲突处置仅在同名异内容文件出现时需要（SAR 31001 单例全量首次上传预期为空 `{}`，推断）。

## Rerun Requests Or Next Step

- 交 Codex：以 Work Performed A/B 为执行蓝图，将 `ENROLLMENT_V2_DATA_DIR` 指向 worker_02 的 20260901 隔离副本后按 17 步顺序跑真实验收；每步以信封 `error.code` 对照失败信号表判定。
- 建议主线程在阶段 A 第 7 步前先准备 TIME_ANCHOR 修复方案（PUT draft 手工锚点修订），并预留 MTPLX 多批次解构时长（slice7 每案例推进上限 80 次）。
- 验收运行结束后、调用 `tools/phase5_acceptance/run_packet.py` 导出前，先停 V2 服务（WAL checkpoint），这是 run_packet 只读打开的硬前置。
- 若主线程需要 UI 级验收：按 `frontend/playwright.real.config.ts` 的双 webServer 范式（Vite preview + `VITE_V2_API_PROXY_TARGET` 指向 V2 后端），不要用 `start_v2_uat.sh`（无后端代理）。
