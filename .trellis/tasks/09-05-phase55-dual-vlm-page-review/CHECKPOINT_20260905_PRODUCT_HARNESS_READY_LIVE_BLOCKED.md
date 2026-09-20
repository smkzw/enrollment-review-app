# Phase 5.5 产品自有逐页 harness 检查点

- 时间：2026-09-05
- 工作树：`.worktrees/phase5-clinical-facts-profile`
- 分支：`codex/phase5-clinical-facts-profile`
- Trellis 任务：`09-05-phase55-dual-vlm-page-review`

## 已完成

1. 完成 ClausePack 内容寻址投影、`determination_mode` 和 SAR III / D001 发布规则对照。
2. 完成严格页级合同、NFKC/数值/日期/单位归一化、双主读事实对账、确定性信号丢弃及手写三源二取一。
3. 完成产品自有逐页 harness：仅通过显式 env 直连 GLM / MiniMax / MTPLX GUI，不读取 Hermes、OMP、ZCode 或其他 harness 的模型库、会话和凭据。
4. 完成模型身份固定、三路 `/models` 联合预检、页图字节哈希校验、ClausePack 哈希校验、JSON 修复、截断翻倍一次、429 等待不计次、同模型备用端点和明确失败。
5. 完成双主读互盲并发、不代笔、条件手写三读、手写缺席计数、多读道失败记录与 SubjectPageCoverage 生成。

## 验证

- 聚焦合同与调度：`41 passed`。
- 完整 `tests/v2`：`3700 passed, 3 skipped, 2 subtests passed`。
- `python3 -m compileall -q app tests/v2` 通过，只保留既有 `app/models.py` 转义警告。
- 定向 `git diff --check` 通过。

## 当前边界

- 主检出目录 `.env` 存在且权限为 `600`；已声明 GLM 凭据，未声明 `CMS_SMK_API_KEY` 或 `PAGE_REVIEW_MAIN_B_API_KEY`。
- 因 main-B 凭据不完整，三路产品预检必须失败关闭；本轮没有发送任何真实受试者页面。
- Phase 5 仍未完成临床收口，`claims_complete=false`。Phase 5.5 仍缺持久化、金标复跑、31001 端到端及浏览器验收。

## 下一安全动作

1. 为 PageReviewRecord / PageReconciliation / SubjectPageCoverage 新建独立追加写持久化模块和 Alembic 迁移，不改写 Phase 4 冻结产物。
2. 在显式 env 中配置 main-B 凭据后，先做三路模型身份和最小合成页直连测试，不直接上真实临床资料。
3. 三路预检与合成页通过后，再在隔离的金标集和 31001 处理修订上复跑。
