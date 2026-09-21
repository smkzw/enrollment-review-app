# HANDOFF 2026-09-22：muse-spark 守望期交接

## 一句话状态

31001 补证重放已完成 95%，最后一步（新模型组合下的页判读→事实重整→投影对齐）
因 opencode 供应商 muse-spark 上游持续不可用（已中断 6 小时以上）而等待中；
守望脚本在后台自动探测（14 天窗口），恢复后无需人工介入即自动跑完全链。

## 恢复后的自动链（守望脚本自动执行，无需人工）

1. 探测 muse-spark 可用 → 自动提交页判读（muse-spark + cms-model 双路，25 页）
2. 页判读完成 → 自动提交事实重整 → 记录终态到 /tmp/muse_spark_watch.log
3. **人工/下次会话仅剩一步**：按 REPLAY_LOG.md 末节步骤，读取投影、记录
   新哈希与决策分布、追加闭包总表、提交推送。

## 关键文件与位置

- 守望日志：/tmp/muse_spark_watch.log
- 重放日志（闭包总表/接手步骤）：runs/execution/wp08-singleton-replay-20260921/REPLAY_LOG.md
- 状态快照基线：runs/execution/wp08-singleton-replay-20260921/wp08_*.json
- 采集脚本：scripts/wp08_capture_state.py
- 恢复守望：scripts/wp08_muse_spark_watch.sh

## 当前模型路由（用户裁定，已生效）

| 节点 | 路由 | 密钥来源 |
|---|---|---|
| OCR 主读 | 本地 oMLX:8001 / GLM-OCR-bf16 | oMLX 应用 |
| 页判读 main-A | opencode-go / muse-spark-1.3-contributor(high) | .env 的 OPENCODE_API_KEY（用户填写） |
| 页判读 main-B | cms-router:20128 / cms-model(xhigh) | .env 的 CMS_SMK_API_KEY |
| 事实规范化 | ollama-cloud / deepseek-v4.1-flash(max) | OMP 凭据库 ollama-cloud 行 |
| 绑定/资格/检索/判断等双路 | main-A 同上 + main-B 同上 | 同上 |

## 踩坑与修复（本轮全部已修）

1. payload-only 合同字段 + ORM 镜像比对 → 历史覆盖记录误判不一致（已修）。
2. native_text 定位核验缺工件库 → 首个带文字层的补证页暴露（已修）。
3. 模型目录 401 导致预检拒绝启动（已修：显式模型名不强依赖目录）。
4. 同值事实多发布通道（demographics vs demographic_age）→ 单点更正不影响判定，
   需按提示逐一更正（产品改进建议，已记录未实现）。
5. cms 网关对最长页的流式判读间歇截断 → 重试是当前唯一对策（网关侧待配置）。
6. 元数据确认晚于页判读 → 完整修订重建导致页判读返工（操作顺序：先确认后判读）。
7. 遗留 .env 与最新决策漂移引发两次返工（模型分配已写入长期记忆）。
8. 旧失败任务重试会沿用旧模型配置 → 换模型后应创建新任务而非 retry 旧任务。

## 下一步（按优先级）

1. muse-spark 恢复后：守望自动完成页判读+事实重整 → 读取投影、追加闭包总表、
   提交推送（REPLAY_LOG.md 末节有逐步说明）。
2. 配额 2026-09-25 20:14 重置（定时核查 automation-6fba2572 已就位）。
3. 30 页级规模验证：等用户提供真实脱敏受试者文件文件夹 →
   build_scale_validation_set.py → run_scale_validation.py。
4. 用户接手：gold 标注 → 方法采用签字 → 官方报告发布（工具链已备）。
5. 跨方案验证（另一研究方案文档走 A 链）。
