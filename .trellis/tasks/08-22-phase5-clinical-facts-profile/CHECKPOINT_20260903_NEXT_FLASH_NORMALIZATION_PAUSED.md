# Phase 5 Qwen3.8-Next-Flash 规范化无损暂停

暂停时间：2026-09-03 06:24 CST  
任务：`08-22-phase5-clinical-facts-profile`  
分支：`codex/phase5-clinical-facts-profile`  
状态：`in_progress`，Phase 5 未完成，`claims_complete=false`

## 本轮已确认

- 现行 MTPLX 产品路由已统一为 `mtplx-flash-next-optimized-speed`，`/health` 实际模型为 `Youssofal--Qwen3.8-Flash-Next-MTPLX-Optimized-Speed`，视觉能力开启。Qwen3.8-27B 不在现行产品路由；测试和历史记录中的旧身份仅作反例、回归或防回退证据，不改写历史。
- 通用 Evidence Normalizer 合同的两个问题已修复：不兼容的资料要求绑定只丢弃绑定而保留事实；肯定/否定候选缺少规范值时，只允许无损复用已有原始标量，不做语义推断。
- 聚焦回归：`100 passed, 5 warnings`。
- 筛选期受控作业 `67478824bad845c6bd91494fa91f09bf`（运行 `72787b3ec2dd4c1bb274c3cee1260316`）的首个页组在第 2 次尝试中成功，已生成检查点 `8082e16d7bc748b0b6ab3523d7a80680`。该页组持久化 30 条候选和 5 条未解决项；原始血常规报告目视抽查证实主要数值与单位可追溯，但手写 `NCS` 便签尚未进入 Phase 5.5 三源手写审读。

## 暂停现场

- 用户指令后已请求取消作业；数据库状态保留为 `cancel_requested`，进度 `1/15`，不宣称为已取消终态。
- 第二页组 `normalize_001_8ee5ee...` 在收到取消时处于 `running`；已关闭专用 `8910` 服务并中断客户端请求，该页组未产生新的 `fact_normalization_calls` 持久记录。
- MTPLX `8002` 保持运行且当前 `active_requests=0`；未停止或切换共享 MTPLX、OCR `8001` 或主应用 `8900`。
- `8910` 已无监听进程；页工作活动租约为 0。下次启动时必须先让任务运行器对 `cancel_requested` 与残留 `running` 步骤做合法终态对账，不得直接重试或复用此作业。
- SQLite `PRAGMA quick_check=ok`；主库 SHA-256 为 `2d19774519ec67c8f9ad75eda4e25c7dc886eaf9677b2d617a51a52aff7c876c`，暂停时无 WAL 文件。

## 仍未完成

- 筛选期剩余 13 个页组与汇总步骤未完成；基线期尚未从合法新入口重建。
- 31001 正式事实、事件、用药暴露和 Patient Profile 未完整生成，未做全量原始证据临床 QC。
- Phase 5 不得收口，`claims_complete` 必须继续为 `false`；Phase 5.5 合同层不得提前替代 Phase 5 业务验收。
- Qwen3.8-Next-Flash 的当前速度仍不满足真实产品要求：首页组本轮耗时约 16 分 40 秒，且经历了同会话修复。不得因为首步成功就认定速度-质量已达标。

## 下一安全动作

1. 只读核对 `8001`/`8002`/`8900`、数据库哈希与作业租约；用显式 env 合同启动专用 `8910`。
2. 先触发任务运行器恢复对账，确认旧作业进入真实 `cancelled`终态；不对 `67478824...` 调用 retry。
3. 使用当前活动完整修订从法定 API 新建一次受控筛选期尝试。首先验证首页组的幂等复用与耗时，若仍出现长时间同会话修复，先缩减模型面向的 Schema/提示词而非盲目跑完。
4. 筛选期完成后先审计候选和未解决项质量，再串行启动基线期。之后生成 Profile 并逐事件回源 QC。
5. Phase 5 验收后更新实施计划状态，再新建 Phase 5.5 Trellis 任务并从 ClausePack/Schema 无模型合同层开始。

