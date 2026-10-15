# 无损暂停记录：2026-09-11 深夜（第二轮，Phase 5 收口推进中断点）

更新时间：2026-09-11 23:4x CST。用户指令：无损暂停，做好任务记录。本文是恢复本轮收口推进的首要入口。

## 0. 暂停时点状态

- 分支 `codex/phase5-clinical-facts-profile`，HEAD = `f466bc2`，工作区干净（全部已提交）。
- 本会话累计提交 6 个：`24a8c77`（冲突组链头）→ `eaa428d`（判断检索 P0）→ `09bfe2b`（三项 UI 修复）→ `3df9b09`（文档）→ `e72bce6`（会商 findings 闭环+截图归档）→ `f466bc2`（收口建议报告）。
- 独立会商审阅已完成并闭环：APPROVE-WITH-CONCERNS，4 项 findings 全部修复（见 e72bce6 提交说明）。
- Phase 5 收口建议已落盘：`.trellis/tasks/09-11-e2e-eligibility-review/PHASE5_CLOSEOUT_RECOMMENDATION_20260911.md`。
- 无在途模型调用；验收服务已停；无未提交改动。

## 1. 中断的进行中工作：第 19 页读道补跑（runtime06c）

- 目的：消除 06b 唯一页级失败（read:18:main-A，EX-16:01 的 coverage_incomplete 根因），验证 SchemaFailDiag 的"原样重试可消失"判断。
- 已做：拷贝 06b 全量到 `artifacts/phase55-takeover/20260911/glm-gemini-runtime-06c-page19-retry/`；SQL 重置 read:18:main-A 与 summary 步为 queued、清失败检查点、作业回 queued；修复了拷贝产生的外键孤儿事件（job_events 2898 引用已删检查点，删除该 1 条孤儿后 foreign_key_check 归零——**注意：runner 正常路径不会产生这种孤儿，这是手工 SQL 重置的副产品**）。
- **真实结果（本次暂停前最后状态）**：重跑触发真实 GLM 调用 → **RateLimitError（429，0.32 秒即拒，回执 sha 99925a25…）**→ 步骤 2 次尝试预算耗尽 → 再次落 page_failure{transport}，作业 completed，EX-16:01 仍 coverage_incomplete，其余 6 条 candidates_present 不变。06b 原库未被触碰。
- **新工程观察（恢复后处理）**：
  1. 429 限流在判断检索读步上没有等待重试语义——`judgment_search_reader` 把一切完成调用异常（含 429）包装成 `failure_kind="transport"`，执行器只按 2 次尝试预算重试，没有页判读 harness 那样的 `rate_limit` 等待分类（对照 `app/llm/page_review_harness.py:519` 的 429→"rate_limit" 与 `max_rate_limit_waits`）。恢复者优先给判断检索读器补 429 识别与有限等待（复用既有语义，不新造框架）。
  2. 深夜时段 GLM coding-plan 429 可能是并发/配额窗口问题；重试时机建议放在白天额度窗口，先单次直连探测（参考本会话 direct_completion 探针方式）确认可用再入队。

## 2. 恢复步骤（按收口建议优先级，均已获用户此前批准的真实额度授权）

1. 先读本文 + `PHASE5_CLOSEOUT_RECOMMENDATION_20260911.md`。
2. 白天窗口先直连探测 GLM；可用则重置 06c 的 read:18:main-A + summary 再跑（沿用本文 §1 的 SQL 步骤，记得处理孤儿事件）；若 429 复现则先实现 §1 观察 1 的限流等待再重试。
3. 通过后继续：31001 原件 QC（37 事实/5 事件/0 暴露/54 保留逐类对照页图，档案页定位详情跳转链路可用）→ 基线节点验收 → 更新收口建议 → 用户确认后才动 claims_complete。

## 3. 边界（不变）

- runtime06/06b/06c 均为隔离受控实例；06b 为已验收成功证据，06c 为重试现场，均保留不删。
- claims_complete=false；用药分项维持隔离；双模型路线固定；不做安全性测试。
- 手工 SQL 重置仅限隔离副本，永不对 06b/原库执行。

## 4. 证据索引

- 06c 重试现场：`artifacts/phase55-takeover/20260911/glm-gemini-runtime-06c-page19-retry/`（429 回执在 artifacts/raw_response/99925a25…）
- 06b 成功证据 + 三档截图：见 `PHASE5_CLOSEOUT_RECOMMENDATION_20260911.md` §一
- 独立审阅全文：`agent://AcceptReview`（transcript: history://AcceptReview）
- 本轮全部决策沿革：`docs/PROJECT_CONTEXT.md` 顶部 09-11 摘要
