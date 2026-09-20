预算边界已达到。针对目标的最终检查确认了正常进展：MTPLX 计数器从 8 变更为 9 —— step 1 长调用已返回，且下一个调用正在进行中。以下是完整报告。

# 执行输出：phase5-sar31001-nextflash-closeout-20260902 - worker_03

## 边界与上下文检查

- 已按初始读取集读取 `context/phase5-sar31001-nextflash-closeout-20260902_execution_context.md`、`plans/codex_execution_phase5-sar31001-nextflash-closeout-20260902.md`。工单为 3：在专用 8910 与显式 env 契约下审计已取消作业和新基线证据链，从合法新幂等入口运行 SAR 31001 事实规范化、事件/用药/Profile 投影并完成逐源临床 QC；不得复用取消作业、不得把未 QC 结果标完成。
- 补充读取（理由：恢复现场所必需）：暂停检查点 `CHECKPOINT_20260902_SAR31001_NORMALIZATION_MTPLX_PAUSED.md`、`CHECKPOINT_20260902_SAR_TARGETED_REPAIR_PAUSED.md`、`.trellis/workspace/codex/journal-2.md`、前序执行包报告 `runs/execution/phase5-sar31001-closeout-r3-20260902/worker_01.md`、`worker_02.md`、`runs/execution/phase5-sar31001-facts-profile-20260902/worker_03.md`、`runtime-identity.json`、`service-start.json`、`.env.example`、主检出目录 `.env` 的非敏感键（仅 grep 键名与模型/URL 值，未读取或输出任何密钥）。
- 边界遵守情况：全程只写 runner 管理的运行报告（由 runner 持久化），未修改任何代码、配置、SQLite 与历史证据；对运行库只做 `sqlite3 -readonly` 查询；对业务写入只通过 8910 的正式 API（创建规范化作业）；未触碰 8001/8002/8900；未复用取消作业；`claims_complete` 未变更（结构上不可能被 Phase 5 改动，见下）。

## 已执行的工作

**1. 现场审计（只读，完成）。** 运行库 `artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/enrollment-review-v2.sqlite3` 当前状态比暂停检查点更新：

- 两个旧规范化作业均已合法终态：`2e28e8673eee412abba3fc3f61cd476d`（06:21 创建，13:01 UTC 经 `cancel_request_expired_lease` 终态化）与 `b13c0607fa4e437d9b33cf680cf50066`（22:19 CST 创建、指向基线权威元组，23:44 由本任务专用服务启动恢复终态化）。两者 `progress 0/6`、`fact_normalization_calls` 均 0 行、四类业务表全零（facts/events/exposures/profile=0）——无任何部分数据，无需清理，均不可复用。
- **基线证据链已由 22:05–22:19 CST 的合法 closeout 会话（actor `worker03-closeout-r3`）修复并完成**：新上传作业 `c6372acc…`（evidence_processing，24 页真实 OCR）、selective-vision 后处理、两次 revision build（`e4bbc4b7…`、`8ca3e222…`）、两次激活事件，最终活动修订 `complete-16b51a2689a34ebc869aa59ae8397999`（快照 `350c8279390149bb81a6b6bb27e4c8d7`）。旧的三个失败快照（`79af5df6…`/`6f309de8…`/`fa464724…`）保持终态未激活。
- 两个活动修订均验证闭合：筛选 `complete-45b1c163…` 与基线 `complete-16b51a26…` 均 `ready / is_current / is_activatable`，8/8 门禁 passed，页 24/24 succeeded，pending 风险 0（筛选 1562 条风险全核、基线 1597 条阻断风险全核+1600 条复核），且两修订间共享 OCR 页数为 0（反借用不变量成立）。
- 幂等现场：两次取消 run 的幂等键均派生自旧模型配置 `evidence-normalizer/model/5c9814f8…`（`mtplx-qwen38-27b-optimized-quality`）。运行库在服务启动时（23:44:28 CST）注册了新配置 `evidence-normalizer/model/42ac01d6…`（`mtplx-flash-next-optimized-speed`）。键组合含 `model_config_id`（`app/domain/contracts/facts.py:699`），因此新入口产生全新幂等键——这就是"合法新幂等入口"，无需任何 supersede 机制。

**2. R3/用户裁决落实（验证，完成）。** 专用 8910 服务（PID 79405，23:44:26 启动，cwd=本 worktree，未由我重启）持有显式 env 契约：进程环境含 `ENROLLMENT_ENV_FILE=<主检出>/.env` 与 `ENROLLMENT_V2_DATA_DIR=…/sar31001-fresh`；env 文件未覆盖 MTPLX/EVIDENCE_NORMALIZER，应用默认值（`app/config.py:136,289`）生效为 `mtplx:mtplx-flash-next-optimized-speed:medium`。启动预检记录（23:44 写入 `runtime/protocol-semantic-route-preflight.json`）确认复杂/短两条路由的 MTPLX 身份均为 flash，无 blocking、未降级、端点可达。8002 实际服务 `Youssofal--Qwen3.8-Flash-Next-MTPLX-Optimized-Speed`（model id `mtplx-flash-next-optimized-speed`）——与 R3+用户裁决一致。按恢复协议执行了最小真实调用：32 token 仅够推理（content 空），2048 token 下 `choices[0].message.content` 返回合法 JSON `{"ok": true}`，传输契约验证通过。

**3. 规范化运行（已启动，进行中）。** 通过正式 API 为两个活动修订各创建一个全新幂等作业：

- 筛选：`POST /api/v2/subjects/0675cabcc979452dbdd5f5c1570c36d8/review-episodes/59b98368…/fact-normalization-jobs` → **job `b5dcede7917b4adca951683fadc946da`，run `28b2f43467ce44d588adb459968b5164`，`created=true`**（HTTP 201，未撞旧键）。
- 基线：同接口 746385ab… 节点 → **job `9d4c399aec234ce08c99ae3e8afa49a5`，run `423367ef633746c1b9be00b2ff517578`，`created=true`**（HTTP 201）。
- 进度（最后一次观察 01:53 CST）：筛选 `running 1/6`（normalize_000 九页病历批已于 00:48 完成，耗时约 46 分钟含 runner 内修复调用；normalize_001 首次调用约 57 分钟后返回，后续调用在途），基线 `queued 0/6`（runner 串行执行）。MTPLX 服务器 `requests_completed` 从 4 持续递增至 9、`active_requests=1`，证明调用链健康推进。

## 工件与证据

- 运行库（只读审计+业务写入均经正式路径）：`artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/enrollment-review-v2.sqlite3`
- 服务与预检证据：`runtime/protocol-semantic-route-preflight.json`（23:44，flash 身份）、`model_configs` 表两行（旧 quality / 新 flash `42ac01d6…`）
- 新作业事件：`job_events` seq1–4（created → normalize_000 started/completed → normalize_001 started），checkpoint 合同与既有实现一致
- 完整性证据：两修订 API 响应 `gates` 全 passed；`evidence_processing_revision_pages` 24/24×6 修订；`evidence_activation_events` 4 条激活历史；`idempotency_records` id≤92 全链
- 轮询日志（进程证据）：`/Users/smkzw/.zcode/cli/exec/sess_452d4e5e-6de3-4cec-8a72-1039d4d60179/call_66b64650f8f04919a243708b-stdout.log`（后台轮询仍在运行）

## 命令与观察记录

- `lsof/ps -wwE`：确认 8910 进程身份、cwd、显式 env 键（未输出密钥）；`curl 8002 /health、/v1/models`：flash 实例确认；两次最小真实 chat 调用验证 content JSON 路径。
- `sqlite3 -readonly`：jobs/episodes/revisions/snapshots/activation/idempotency/model_configs/fact counts/calls/revisions pages/OCR 反借用核对。
- 正式 API：`GET /evidence-processing-revisions/{id}`（两修订闭合状态）、`POST …/fact-normalization-jobs`（两次，均 201 created=true）、`GET /jobs/{id}`（持续监控）。
- 观察到的性能特征（推断）：flash 路由在大批次上约 5 分钟/页（9 页步 46 分钟；8 页步首调用约 57 分钟）；`max_tokens=60000`、effort=medium；传输未设显式超时（前次 24 分钟在途调用证明无 600s 上限），runner 内预算为 2 次传输重试 + 2 次 schema 修复，工作流层每步 3 次尝试。

## 阻碍或缺失环境

1. **规范化未在本预算窗口内完成**（唯一实质未竟项）。筛选 1/6、基线 0/6，均为合法运行中状态，非失败。按观察速度，两作业全部完成约需 2.5–4 小时。
2. QC 阶段未开始：事实/事件/暴露/Profile 投影尚未产出，逐源临床 QC 无对象。按边界，绝不预标完成。
3. 风险提示（证据→推断）：若某步在途调用无限期不返回，runner 无超时兜底，作业将滞留 running。本次未观察到该情形（所有调用均返回）；若复现，需 Codex 决策（如为该路由加传输超时），代码修改不在本工单授权内。
4. 已知缺口（沿用前序 worker_03 报告，未变化）：run-in 节点无活动快照；邮件引用的入组审核表、基线 RQLQ、run-in 日记等不在 5 份清单内；元数据来源方"待确认"标记已被链头修订确认（基线 5/5 门禁 passed）但权威属性仍以 Codex 验收为准。

## 重跑请求或下一步

1. **恢复点**：继续监控 `GET /api/v2/jobs/b5dcede7917b4adca951683fadc946da`（筛选）与 `9d4c399aec234ce08c99ae3e8afa49a5`（基线）直至终态；或查 `job_events` 最新事件。后台轮询日志仍在上文路径追加。
2. 两作业完成后执行逐源临床 QC（查询集已备好）：四表计数与权威元组核对；`fact_gate_results` 门禁分布；`fact_normalization_unresolved_items` 必须保留为显式缺口；每条 fact/event/exposure 的 locator 链回 `evidence_locator_artifacts`（`source_layer=raw_ocr`、页号、excerpt 与 `ocr_pages` 原文切片及 SHA 比对）；`event_fact_links`/`exposure_fact_links` 闭合；Profile revision `status=succeeded`。QC 结果对照前序 worker_03 已核实的源事实清单（时间线、用药、异常检验值）逐源抽验。
3. 仅当逐源 QC 通过且 Codex 验收后才可讨论完成状态；`claims_complete` 仍为 false（该旗标属 Phase 6 协议控制矩阵契约 `app/domain/contracts/protocol_control_matrix.py:1804`，默认 False 且有守卫，Phase 5 运行不触碰）。
4. 若作业失败（`failed_final`/`failed_retryable`），按 `job_events` 的 step/attempt/retryable 定位失败步，再以同一幂等入口重新提交（同键同哈希将安全复用运行记录，不产生重复事实）。
