# 无损暂停：研究者书面判断的正式消费链

2026-09-14。用户要求完成手头修复后暂停。此记录不是自动恢复指令。

## 当前状态

- 唯一工作树：/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile
- HEAD：4caf392c376ce7a9392fa2e8facc7d8a7f4e4a34；大量既有未提交工作保留，不 reset、不清理。
- Goal 未完成；未把运行时 goal 标 complete/blocked。收到暂停后未再派发工作或调用产品模型。
- 本轮 E03 r05-judgment-content-job-20260914 已终态 exit 0，一轮、无 fallback；exec 69767/functions cell 1039 已结束，pgrep task-specific runner 无结果。未启动产品服务，不停止他人平台/会话。
- 当前产品仍 GLM-5.3-Flash high + MTPLX FlashNext OptimizedSpeed xhigh，两独立主读；未改模型或额度。
- 用户要求整个产品构建完成后统一测试；本轮 owner 仅源码、py_compile、diff 检查，无产品模型/数据库/浏览器测试。claims_complete=false。

## 所在位置与实质进展

位于恢复 Plan T5 的正式审核、行动与冻结报告衔接。T0–T3 有多项源码实现，T4 当前组合原件临床与大屏统一验收尚未完成；T5–T7 部分已构建，不等于阶段验收通过。精确状态以恢复 Plan 和 PROJECT_CONTEXT 当前摘要为准。

现有关键缺口：系统会保留“缺判断”“尚未核实”等未决项，但真正找到研究者判断后，正面内容尚未完整进入正式审核；多次观察及控制族也不能被永久缩成单观察/未知。

本次已写：
1. judgment_content 合同：明确书面判断、研究者归属、对象、节点、编码忠实性五维；不产入排真值，不改事实。
2. 通用提示与产品直接读取：去重输入，不传对方意见，逐配对原文引用；复用65536..131072与一次截断重试，拒绝重复 JSON 键。
3. 判断检索摘录与既有事实的严格来源关联，零/多匹配保留；从同次准备及已核候选回执产生内容核实输入。
4. 双路内容比较：同输入/批次/提示，只比较五维；支持、否定、分歧、未清楚分别保留，未签发采信。
5. E03 新增可恢复 JobRunner producer/executor/receipt verifier，保存原始请求/回答/失败及完整摘录覆盖。尚未注册。
6. Owner 修复持久化 list/tuple 不一致及只核最后回答的缺陷；新回执逐次核429等待、length翻倍一次、同attempt、完整请求/路由/额度和最终stop。编译/diff通过。

## 边界与未完成

- 新工作尚未接正式消费者或 API 注册；不得仅凭双路 content_supported、JSON 或报告存在启用采信。
- 当前内容输入仅官方谓词；控制族显式拒绝，后续须完成控制族，不当作永久产品范围缩减。
- 严格逐字摘录匹配召回未知；source matching 不证明作者/适用性。仍要有效评测与用户批准方法采用。
- 独立会商 r05-core-consumption-review-20260914 已完成方向审阅；本轮新代码尚无独立会商验收。
- E03 实际为 pi/cursor/default，底层模型未知；报告承认违规尝试递归 pi-worker 且失败，也超出 compile-only 做 import/空函数检查。详细见 owner review，不采信全面合规声明。
- 没有进行数据库迁移、正式发布、clinical QC、ego UI 或全链验证。

## 恢复后顺序

1. 先读 goal-objective、最新全局指令、本记录、当前源码和恢复 Plan。确认用户已解除暂停，不根据旧进程号重跑。
2. 完整审阅新任务及回执实现，核失败/取消、资源准入、持久来源、空/歧义覆盖；未使用的 require_route_receipts 参数及重复资格/内容读取需一并评估，不以新增大量重复框架替代接通产品。
3. 完成独立源码会商，修明确问题；按用户要求不提前开启阶段测试。
4. 把经核内容接入版本化的正式判定消费者及独立方法评测/批准范围。保留缺失、未核实、真实冲突区别；不可直接撤销所有 professional 拒绝。
5. 完成控制族与来源支持的多观察策略，再接正式入口/界面。评估来源资格与判断内容能否一次读取、分别留结果，避免相同原文重复调用；不能未经新身份与验证改旧任务语义。
6. 产品构建完成后集中做当前双模型、原件QC、金标、ego大屏和完整交付验证。临床有效性未证明前不声明任何阶段通过。

## 证据地址

- docs/PROJECT_CONTEXT.md
- plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md
- docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md
- reviews/codex_execution_r05-judgment-content-job-20260914_review.md
- runs/execution/r05-judgment-content-job-20260914/worker_01.md
- logs/execution/r05-judgment-content-job-20260914/worker_01_stdout.txt
- reviews/codex_conference_r05-core-consumption-review-20260914_review.md

## 本次暂停源文件 SHA256

```text
abb9bb73146662ab4336a25bd530f13e72371ba22c53701273ecbd5486bfb30e app/domain/contracts/judgment_content.py
e2bb08bd5abc7f773f03414e59f6fe9880262c3213a837bb2e7a43c5a16a6db2 app/llm/judgment_content.py
af54bef6abb69a6acbb728bd0bb05e4fa143a38b2ddc9d18a18379459eadad37 app/services/judgment_fact_linkage.py
e94a58e9dc64c7c8cbc6a7ee5fed324a8e8e22fe0fd61db3c3169af0e435a521 app/services/judgment_content_input.py
29779a3f84c825ad3d9a6e5206ed3284cea08ab42bb10059a5e14e3218f51045 app/services/judgment_content_comparison.py
a7846fe38e983eb93540c3d4fdf4f07995e21d383b82c92ca5bdd9c996557e90 app/services/judgment_content_job.py
b949aa658a61eef98b45a0f5edf54da46164034bc9e5926faafe55e20772bfe4 app/services/judgment_content_receipts.py
```
