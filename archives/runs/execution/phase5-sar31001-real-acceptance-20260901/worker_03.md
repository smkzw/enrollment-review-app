# Execution Output: phase5-sar31001-real-acceptance-20260901 - worker_03

## Boundary And Context Check

- 只读审查已完成，未修改任何源文件、原始临床资料、D001 控制任务或生成路径；未读取 peer worker 报告（按“不评审 peer”边界）；未启动 V2/oMLX/MTPLX/D001；未访问生产路径。
- 读取范围：初始读集 2 个文件（execution context、Codex plan），加上为完成审查所必需的项目内代码/文档/测试（均记录于下）。运行的两条 pytest 命令只读验证，产物仅写入临时目录与 `__pycache__`。
- 本报告不作任何最终医学入排结论；工具链本身也声明 `clinical_acceptance.claimed=false`（`tools/phase5_acceptance/run_packet.py:1683-1688`）。

## Work Performed

围绕工作项 3 的五个审查对象逐一完成只读审查，并汇总主线程最小验证清单。

**1) 代表受试者真实验收所需的输出（证据）**
- 验收数据包导出器 `tools/phase5_acceptance/run_packet.py`（schema `phase5.run_packet/v1`），固定五个验收锚点：`isolation`、`source_fingerprints`、`run_authority`、`statistics`、`per_event_source_checks`；以 28 个阻断性 gap code 判定 `packet_disposition = blocked|verifiable`，CLI 退出码 0/2（`run_packet.py:1645-1676,1799`）。
- 输入清单工具 `tools/phase5_acceptance/input_manifest.py`（`phase5.input_manifest.v1`）：内容哈希清单、源不可变复验、互斥目的地隔离副本、副本计划+复制后校验。
- 验收台账 `tools/phase5_acceptance/ledger.py`（`phase5_acceptance_ledger/v1`）：P5-AC01..AC13，证据类 `deterministic/clinical_manual/browser_tester/conference_advisory`；`clinical_manual` 或 `browser_tester` 缺失时整体拒绝 pass，advisory 永不替代（`ledger.py:59-118`）；禁止伪造真实病例身份。
- V2 读取面：`GET /api/v2/subjects/{sid}/review-episodes/{eid}/patient-profile`（当前链头、读取时派生 `stale`、未生成时 404）、`.../history`、按冻结 revision 稳定 ID 读取（`app/api/v2/patient_profiles.py:87-155`）；DTO 补齐全部定位详情，定位解析不完整即大声失败（`app/api/v2/patient_profile_schemas.py:450-469`、`app/services/evidence_api_read_service.py:971-996`）。

**2) 发布权威链（证据）**
- 写入侧：不可变 `FactAuthority` 元组（project/subject/episode/episode_revision/protocol_version/rule_set+revision/snapshot/complete 修订，`app/domain/contracts/facts.py:91-108`）；`FactAuthorityValidator` 在发布前强制：v2 快照存在且作用域一致、活动指针对成对且等于权威、`episode_revision` 非陈旧、complete 修订必须 `revision_kind='complete'`+`ready`+可激活、定位引用闭包（同节点/同快照成员/同处理修订清单，`app/storage/fact_authority.py:75-263`）。
- 读取侧复核：数据包从最新 `succeeded` Profile 冻结权威，校验 `authority_matches_active_pointers`、快照/修订存在且 payload 哈希一致、每个规范化运行的身份（prompt node/template sha/schema 版本 + model provider/name/effort）与 `matches_frozen_authority`；不匹配即 `authority_pointer_mismatch`、`no_normalization_run_matching_authority` 等阻断（`run_packet.py:339-505`）。

**3) 逐事件来源定位（证据）**
- 写入侧门禁：`LOCATOR_AND_TEXT_HASH`（定位属于当前完整修订、页闭包、effective_text 修订绑定、assertion 哈希一致，虚构/跨修订/跨页定位 REJECTED）、`PAGE_COVERAGE_AND_REFERENCE_CLOSURE`（页集合精确覆盖）、BLOCKING 级 OCR 风险未解除且与定位重叠时仅阻断相关候选（`app/domain/gates/fact_evidence_closure.py:1-24,271-330,406+`）；发布时写 `fact_evidence_locator_links` 反向索引并先 `validate_locators`（`app/storage/fact_repositories.py:15,289`）。
- 数据包逐事件核对：每个 Profile 条目（fact/event/exposure/conflict/expectation）产出一条核对项，携带文件+页码+摘录+文本哈希+bbox；`raw_ocr/effective_text` 定位的摘录按字符区间在记录的 OCR 页文本内重放，effective text 由冻结修订的 corrections 确定性重建；Profile 定位集合必须等于发布链接行（`entity_link_locator_mismatch`/`entity_links_absent`）；被人工修正取代或低于 stable identity 链头的条目判 `stale_revision_in_profile`（`run_packet.py:1023-1260,1263-1477`）。

**4) 时间轴风险标记（证据+推断）**
- 合同层：事件时间（`start_range/end_range` 部分日期 + `duration_status`）与记录时间 `record_time` 分离；暴露不变量（ended 必须有 end_range、ongoing 不得有）；13 条泳道、条目类型化身份与定位必带（`app/domain/contracts/patient_profile_v2.py:203-503`）。
- 风险标记（首屏突出）为确定性推导，仅由已发布合同状态触发：未解决冲突、当前到期资料缺口（absent/referenced_missing）、`observed_weak+ocr_or_parse_risk`、`observed_weak+provenance/historical gap+provenance_followup`；`pending_review_count == len(highlights)` 由合同强制（`app/projections/patient_profile.py:278-318`、合同 `_validate_complete`）。
- 推断/缺口：数据包导出逐事件时间字段与 `pending_review_count`，但**不导出逐条目的突出原因、也不独立重放突出推导**；`native_text` 定位不摘录重放（依赖应用内原生坐标门禁，`run_packet.py:1030-1037`）。这两项必须由主线程在 UI/人工核对覆盖（见清单第 10-12 条）。

**5) 旧运行污染门禁（证据）**
- 清单层：文件名+内容双重旧产物识别（`.sqlite*/.db/.pyc/.pyo/.jsonl/__pycache__`、携带 `phase4./phase5.` schema_version 的 JSON 导出）；工具绝不写源树、目的地必须与源根互斥、源根不得嵌套、源不可变复验（`input_manifest.py:80-142,318-487`）。
- 数据包层：`manifest_contains_run_artifacts`（含 legacy 清单回退的名称扫描）、`source_not_fingerprinted`（消费 blob 必须能对上清单指纹，堵跨病例/陈旧输入污染）、`profile_item_authority_mismatch`（条目仅在其它权威下存在→跨快照污染）、隔离副本必须在隔离根内且哈希一致、清单必须 `source_immutability.verified=true` 且有 copy plan、数据库只读打开（WAL 未 checkpoint 会大声失败）（`run_packet.py:708-918,160-171`）。
- 数据库含多 episode 时必须显式 `--review-episode-id`（`run_packet.py:243-269`）；真正的“全新隔离运行目录”由外部保证：`ENROLLMENT_V2_DATA_DIR`（`app/storage/config.py:27-29`）。

**测试佐证（观察）**：`tests/tools/` 50 passed；`tests/v2/projections+tests/v2/api -k "patient_profile or profile or run_packet"` 38 passed。覆盖篡改 payload、外权威发布行、删除链接、篡改摘录、manifest 模式缺副本、副本出根、无匹配规范化运行、旧产物混入、effective_text 投影重建等（`tests/tools/test_phase5_acceptance_run_packet.py:159-672`）。

## Artifacts And Evidence

未创建/修改任何工件（本角色为只读审查；报告由 runner 持久化）。审查依据的关键文件：
- `tools/phase5_acceptance/run_packet.py`（1804 行，全文审查）
- `tools/phase5_acceptance/input_manifest.py`（关键 600 行审查）
- `tools/phase5_acceptance/ledger.py`（证据类与 P5-AC 定义段）
- `app/domain/contracts/patient_profile_v2.py`、`app/projections/patient_profile.py`、`app/api/v2/patient_profiles.py`、`app/api/v2/patient_profile_schemas.py`
- `app/storage/fact_authority.py`、`app/domain/contracts/facts.py`（FactAuthority）、`app/storage/fact_repositories.py`（定位链接发布）、`app/domain/gates/fact_evidence_closure.py`、`app/services/patient_profile_service.py`（stale 派生）、`app/services/evidence_api_read_service.py`（locators_by_ids）、`app/storage/config.py`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_REPRESENTATIVE_SUBJECT_ACCEPTANCE_PREPARED_PAUSED.md`
- 测试：`tests/tools/test_phase5_acceptance_run_packet.py`（结构性抽查）

## Commands And Observations

- `Read` context/plan/checkpoint + 上述源码（工具：Read/Grep 类）。
- `.venv/bin/python -m pytest tests/tools/ -q` → `50 passed, 5 warnings in 9.99s`。
- `.venv/bin/python -m pytest tests/v2/projections tests/v2/api -q -k "patient_profile or profile or run_packet"` → `38 passed, 279 deselected`。
- `.venv/bin/python -m tools.phase5_acceptance.run_packet --help` → 正常输出（注意：`tools/` 无 `__init__.py`，以命名空间包方式 `-m` 调用可行；直接 `python tools/phase5_acceptance/run_packet.py` 也有 import 回退，两路均可用）。
- `ls runs/execution/phase5-sar31001-real-acceptance-20260901/` → 仅三个 99 字节占位 worker 报告（未读取内容）。

**主线程必须验证的最小清单（建议，SAR 31001 单例真实验收）**

前置失败信号：数据包 CLI 退出码 2 即 blocked，逐条追查 `blocking_gaps`，不得降级为流程通过；只读打开失败=V2 服务未停（WAL 未 checkpoint）。

1. 输入隔离：20260901 新清单 `mode=copy`、`source_immutability.verified=true`、`copy_verification.verified=true`、`run_artifact_files=0`、仅含 SAR 31001 原始资料；数据包 `source_fingerprints.run_artifact_entries=[]`、`isolated_copy_recheck.verified_ok==checked`、`unused_manifest_files` 为空或可解释。
2. 运行隔离：V2 使用全新 `ENROLLMENT_V2_DATA_DIR`；数据库仅含 31001 一个审核 episode（自动选中或显式 `--review-episode-id`）；D001 任务 `3259ab5f070447c3938ff2de5f45c9cd` 保持第 19 包暂停未动；未复用 2026-08-23 旧验收产物。
3. 权威链：`run_authority.authority_source=="patient_profile_revision"`、`authority_matches_active_pointers==true`、complete 修订 `kind=complete/status=ready/is_activatable`；≥1 个规范化运行 `matches_frozen_authority==true`，并记录其 prompt template sha 与 model provider/name/effort（不得混入 D001 时代模型配置）；`protocol_version_id` 指向本次从 SAR V2.1 DOCX 冻结的新协议版本。
4. 逐事件定位：`packet_disposition=="verifiable"` 且 `blocking_gaps==[]`；每个 fact/event/exposure/conflict 至少 1 个定位、`entity_links_match==true`；抽样（含全部突出条目）对照隔离副本原文核对页码/摘录/极性/规范值/单位（P5-AC02 的 browser_tester + clinical_manual）。
5. 时间轴：抽样核对事件时间与记录时间分离是否与原件一致；暴露 ended/ongoing 不变量；native_text 定位依赖应用内门禁通过（数据包不重放），确认 `gate_results` 无未解释的原生坐标拒绝。
6. 风险标记：UI 待核对数 == 数据包 `pending_review_count`；突出原因仅出现四种合同原因且与数据包事实一致（未解决冲突双方并列可见且 resolution_revision=0；到期缺口带具体 gap_type；not_due 不得按当前到期突出）；数据包不导出逐条突出原因——以 UI+DB 人工比对为准。
7. 阶段不可回写：history 各 revision 不可变；仅当权威前进时读取派生 `stale`，后阶段证据未改写早阶段结果。
8. 台账收口：deterministic 证据取自数据包；`clinical_manual`（P5-AC12 逐事件人工核对）与 `browser_tester`（1080P/2K/4K 来源回放）两类齐备后才可评估 pass；尊重 `clinical_acceptance.claimed=false`，最终医学入排结论不由工具或本报告宣称。

## Blockers Or Missing Environment

- 无阻塞性缺失（审查与聚焦测试均在现有 `.venv` 下完成）。
- 未验证（超出本工作项边界，非阻塞）：oMLX 8001 / MTPLX 8002 / V2 服务实际可用性（checkpoint 亦标记未确认）；SAR 31001 新隔离副本与清单是否已由 worker_02 创建（按不评审 peer 边界未查看）；真实单例运行尚未发生——本清单是运行后验收用的最小验证集。
- 不确定性：`_authority_where` 发布行匹配未含 `protocol_version_id/rule_set`（由 `review_episode_id` 作用域间接覆盖）；若主线程要求协议维度显式对账，需在读清单第 3 条人工核对，工具当前不单独阻断。

## Rerun Requests Or Next Step

1. 主线程在 worker_02 产出新隔离副本+清单并完成单例 V2 运行、停止 V2 服务后执行：
   `.venv/bin/python -m tools.phase5_acceptance.run_packet --isolation-root <新数据根> --manifest <20260901清单.json> --output <packet.json> --case-label project=SAR --case-label subject=31001`
   预期退出码 0、`disposition=="verifiable"`；随后按上方 8 条最小清单逐项收口并登记 ledger（deterministic/clinical_manual/browser_tester）。
2. 若需要把“逐条目突出原因”纳入机器核对（当前缺口，见工作项 4 推断），建议后续最小增强：在 `per_event_source_checks` 中导出 `highlight_reasons`（纯结构化复制，不新增语义）；此为建议，非本次授权改动。
3. 恢复点：本报告 + `CHECKPOINT_20260901_REPRESENTATIVE_SUBJECT_ACCEPTANCE_PREPARED_PAUSED.md`“下一安全动作”1-5。
