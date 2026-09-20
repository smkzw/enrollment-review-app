# Phase 5 SAR 31001 事实规范化 MTPLX 测试期无损暂停

暂停时间：2026-09-02 15:58 CST  
任务：`08-22-phase5-clinical-facts-profile`  
分支：`codex/phase5-clinical-facts-profile`  
恢复状态：`in_progress`，不得视为 Phase 5 完成

## 暂停原因与运行边界

- 用户正在单独测试 MTPLX，要求整个入排审核构建任务先无损暂停。
- 已停止本任务专用的 V2 服务 `127.0.0.1:8910`，未继续发送模型请求。
- MTPLX `127.0.0.1:8002`、OCR `127.0.0.1:8001`、主应用 `127.0.0.1:8900` 均保持运行且未修改。
- 治理执行包 `phase5-sar31001-facts-profile-20260902` 的工作者均已终止；执行报告和运行记录原样保留，未归档、未清理。

## 已确认的业务现场

- SAR 方案作业 `09b593a721e7430fa72bddf8883f233f` 已完成；正式规则目录已发布到修订 16。
- 未命名回溯窗口已按通用“审核节点相对锚点”合同处理：筛选与基线分别评判，前一节点结果不得覆盖后一节点。
- 受试者 `31001` 的内部标识为 `0675cabcc979452dbdd5f5c1570c36d8`。
- 筛选期审核实例 `59b98368e962465ca5d62ff55b4da07d` 的 5 份 PDF 已完成 24 页证据处理；快照 `2685d8e0c0a948ff83a13cb7952eb915` 已有可激活完整修订 `complete-45b1c163d1ba44059847af7fa9557ffc`。
- OCR 风险项已逐页完成流程性复核，但未做逐字临床金标准校对；这只表示处理门禁闭合，不代表原始证据识别质量已获临床接受。

## 明确未完成的部分

- 事实规范化作业 `2e28e8673eee412abba3fc3f61cd476d` 停留在 `cancel_requested`，进度 `0/6`；规范化运行标识为 `4ecda29906164a35ad7cbe0b021d9275`。
- 暂停前 MTPLX 连续出现 3 次 HTTP 502；第 4 次调用仍在等待时已先请求取消，随后按用户指令停止专用 V2 客户端。不得把该作业恢复或标记为成功，恢复前必须先核对租约与终态。
- 当前 31001 的 `clinical_facts_v2=0`、`clinical_events_v2=0`、`medication_exposures_v2=0`、`patient_profile_revisions_v2=0`。
- 基线期审核实例 `746385aba80c421ab83aaf439e084b7f` 的处理未成功：作业 `49bda9d56bb14d47a4641c35b2aade33` 为 `failed_final / SNAPSHOT_STATE_INVALID`，作业 `ce47ea92dfd94b5390b8059685b29d6c` 为 `failed_final / EXECUTOR_ERROR`，作业 `604bd7887f99458b90dc29e58cbb8631` 已取消。没有可用的基线期活动快照。
- Patient Profile、逐事件回源、临床 QC 和 `claims_complete=true` 均未完成；当前必须保持 `claims_complete=false`。

## 数据完整性锚点

- 数据库：`artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/enrollment-review-v2.sqlite3`
- `PRAGMA quick_check=ok`
- SQLite SHA-256：`79d93f382d93acf06ba0d45cfa1d8384b13146e70e96f574b5bd0666d28350ef`
- WAL SHA-256：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（空 WAL）
- SHM SHA-256：`fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb`
- 原始方案、受试者资料、隔离副本、运行日志、执行报告和数据库均未清理或改写。

## MTPLX 恢复前风险

- 本次入排应用冻结配置指向 `mtplx-qwen38-27b-optimized-quality`，而暂停前 `8002` 健康信息曾显示 `mtplx-flash-next-optimized-speed`。这可能是模型绑定不一致，当前因用户正在测试 MTPLX 而不做任何切换或重启。
- 不得仅根据端口可用判定模型质量或调用链恢复；必须核对实际模型标识、响应格式、HTTP 502 原因和一次最小真实调用。

## 下一安全动作

1. 用户明确恢复后，先确认 MTPLX 测试已经结束，再只读核对 `8002` 的健康状态、实际模型标识和近期错误。
2. 用显式 env 契约重启专用 `8910`，不得影响 `8001`、`8002`、`8900`。
3. 只读审计规范化作业的租约、调用记录和取消终态；不得直接复用一个仍为 `cancel_requested` 的旧作业。
4. 查明基线期 `EXECUTOR_ERROR` 与快照状态错误的共同根因；只可从合法新快照或受控重试入口继续，禁止激活失败快照。
5. 事实、事件、用药暴露和 Profile 均生成并完成原始证据临床 QC 后，才可讨论 `claims_complete=true`。

