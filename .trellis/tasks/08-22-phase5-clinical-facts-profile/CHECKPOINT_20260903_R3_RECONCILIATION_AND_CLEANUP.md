# Phase 5 / Phase 5.5 R3 对齐与清理记录（2026-09-03）

## 当前边界

- 当前仍为 Phase 5 收口；`claims_complete` 必须保持 `false`，直到 31001 事实、事件、用药暴露、Profile 和原始证据临床 QC 全部完成。
- Phase 5.5 只能先做 R3 设计对齐和不依赖模型的合同准备；不得以草稿读道模块冒充 Phase 5.5 已启动或已验收。
- 受试者逐页判读现行裁决为单阶段对称双主读：main-A GLM-5.3-Flash:high（zhipu-coding-plan）与 main-B MiniMax-M3:high（cms-smk）。
- Qwen3.8-Flash-Next（MTPLX.app，effort low）只允许作为 handwriting-C，且只写 `handwriting[]`。不得替代任一主读，不承担普通事实仲裁或离线主读。
- DeepSeek 不进入任何受试者读道；GLM-OCR 只作 OCR 侧车。

## 本轮发现的设计漂移

1. 设计书 §3.3、§7.4、§12 仍保留 Qwen3.8-Flash-Next 兼任“本地主读降级/单源事实仲裁”的旧表述。
2. 实施计划 Phase 5.5 工作项 2、4、4c 仍保留相同旧路由，并把云端并发写成 2–4，而最新裁决是每模型 2–3。
3. 上轮执行者新增 `app/agents/page_review_lanes.py`（15,338 bytes，400 行）和 `tests/v2/agents/test_page_review_lanes.py`（12,313 bytes），在 Phase 5 未收口、PageReviewRecord 合同尚未落地前提前实现读道；代码把 main-B 后端写成 `minimax`，没有落实 cms-smk 节点配置，并含静默修正配置与业务层模型身份硬编码。该实现不予采纳。
4. 上轮执行者还把共享 `app/llm/independent_vlm.py` 的 `temperature/top_p` 参数整体移除。R3 的“厂商默认采样”只约束未来页级判读请求，不应未经相邻调用审计就改变 Phase 5 已有共享传输合同；该越界改动回退，未来在 Page Reader 专用请求层落实。

## 清理清单与证据

### 删除

- `app/agents/page_review_lanes.py`：本轮越界草稿，未纳入正式合同。
- `tests/v2/agents/test_page_review_lanes.py`：仅验证上述被否决草稿。
- `artifacts/phase5-acceptance/20260903/normalizer-single-page-diag/db-snapshot/enrollment-review-v2.sqlite3`：53 MB 临时数据库副本，SHA-256 `fb132e87230204e6f7959437f95297649196b0e4595f0c43f2a3dac5954dd714`；不是运行主库。
- 同一诊断目录内的原始响应、重复输入副本、临时脚本和字节码：属于已终止的 Next-Flash 单页规范化试验，不作为产品验收结果。
- worktree 内 `.venv` 之外的 `__pycache__` 与 `.pyc`：纯可再生测试缓存。
- `.trellis/tasks/.DS_Store`（如存在）：Finder 缓存。

### 保留

- `artifacts/phase5-acceptance/20260903/normalizer-single-page-diag/DIAGNOSIS.md`，SHA-256 `45606bb06c1950c407925cb36cc10e40490e7fde3b08a7c3d45bb1417e2adbd3`：保留失败原因摘要；清理后迁入本检查点同目录的历史诊断记录，不再作为活动输入。
- `runs/execution/phase5-resume-next-flash-20260903/`、`runs/execution/phase5-nextflash-resume-20260903b/`：保留为历史执行证据，不作为现行路由依据。
- `runs/execution/phase5-r3-reading-lanes-20260903/`：保留并完成 guard 审计；执行者产物不等于 Codex 接受。
- 所有源研究方案、受试者原始资料、主运行数据库、已发布 RuleModelRevision、证据快照、既有 checkpoint、用户改动和未归因文件。

## 清理后的恢复入口

1. 修订设计书和实施计划，删除 Qwen 的主读降级/普通事实仲裁职责，保留 handwriting-C 专项第三读。
2. 对当前执行包完成独立验收与 guard 审计；明确拒收越界实现。
3. 只读核对 8001/8002/8900/8910 的实际进程、模型标识、响应格式和日志；端口存活不等于路由正确。
4. 审计旧规范化作业租约与终态，不复用 `cancel_requested` 作业；查明基线期 `EXECUTOR_ERROR` 与 `SNAPSHOT_STATE_INVALID` 的共同根因。
5. 从合法入口新建受控 Phase 5 作业；完成 31001 临床 QC 后才允许把 `claims_complete` 改为 `true`。
6. Phase 5 收口后，新建 Phase 5.5 Trellis 任务，先实现 ClausePack 投影、`determination_mode`、页级 Schema 与 Gate，再接入读道 harness。

## 只读恢复审计补记

- `8001`：oMLX 正常监听；`/v1/models` 返回 8 个模型条目及 MarkItDown。GLM-OCR-bf16 在目录中，OCR 侧车准入条件存在。
- `8002`：实际模型仅为 `mtplx-flash-next-optimized-speed`；启动命令对应 Qwen3.8-Flash-Next，但 GUI 当前 reasoning effort 为 `xhigh`，不等于未来 handwriting-C 要求的 `low`。本轮未切换共享 MTPLX。
- `8900`：实际进程工作目录为 `/Users/smkzw/Vibe-Research/backend`，不是入排审核系统。旧记录把它称作“主应用”已经失真，本轮不停止、不修改。
- `8910`：当前为本 worktree 的 V2 FastAPI 服务；API 路由可读。是否使用了显式 env 文件不能仅凭进程命令证明，后续重启必须走 `ENROLLMENT_ENV_FILE` 启动合同并保留预检审计。
- 旧事实规范化作业 `2e28e867…` 与 `67478824…` 均已进入 `cancelled`，租约 owner 为空；禁止复用条件已经满足，后续只能新建作业。
- 三次 502 的共同原因不是 Schema：旧作业冻结模型为 `mtplx-qwen38-27b-optimized-quality`，而 8002 实际模型目录不含该身份。数据库事件完整记录三次 `TRANSPORT_FAILED / Error code: 502`；现行 Flash-Next 身份已消除此错配。
- 早期基线失败链已查清：首次作业完成 24/24 页后在收尾阶段发生 `EXECUTOR_ERROR`；对同一已改变状态的快照重试后触发 `SNAPSHOT_STATE_INVALID`。随后已从合法新快照 `350c8279…` 构建并激活 `complete-5f514e…`，因此当前不存在“激活失败快照”的遗留状态。
- 当前主库 `PRAGMA quick_check=ok`，SHA-256 `2d19774519ec67c8f9ad75eda4e25c7dc886eaf9677b2d617a51a52aff7c876c`；31001 的 facts/events/exposures/profiles 计数仍全部为 0。
- Flash-Next 旧诊断显示单页曾耗时约 46 分钟，首个受控页组也耗时约 16 分 40 秒。按当前 14 个页组全量续跑预计为小时级，不能为了“跑通”直接续跑；下一步应先缩短面向模型的输入合同或切换经批准的独立语义路由，并做单页速度/质量闸门。

## 本轮验收

- 执行包 `phase5-r3-reading-lanes-20260903` 已通过 guard 审计；Codex 仅接受只读审计结论，拒收提前实现的读道模块。
- 设计书和实施计划已删除 Qwen 主读降级与普通事实仲裁职责，云端并发统一为每模型 2–3。
- 设计书修订日期已补至 2026-09-03；`.env.example` 明确区分现有 Phase 5 证据规范化与 Phase 5.5 handwriting-C，避免把 MTPLX 误解为双主读之一。
- `tests/v2/llm/test_independent_vlm.py` 与 `tests/v2/agents/test_mtplx_semantic_route_regressions.py`：39 passed，1 skipped（仅真实联网门禁未启用）。
- 大量既有 checkpoint、研究记录和执行包虽仍未提交，但属于阶段历史与审计证据，不按“缓存”删除；当前恢复入口、哈希和失败归因需要依赖这些记录。仅删除可明确归因、可再生或已被 R3 否决的文件。
