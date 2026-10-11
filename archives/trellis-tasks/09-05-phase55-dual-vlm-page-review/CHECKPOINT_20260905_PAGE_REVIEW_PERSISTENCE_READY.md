# Phase 5.5 页级判读持久化检查点

- 时间：2026-09-05
- 工作树：`.worktrees/phase5-clinical-facts-profile`
- 分支：`codex/phase5-clinical-facts-profile`
- Trellis 任务：`09-05-phase55-dual-vlm-page-review`

## 本轮完成

1. 新增 `0020` 迁移，以五张窄表追加保存页级判读、页级对账、读道引用、受试者页覆盖与覆盖条目。
2. 新增不可变仓储，写入和回读均校验完整合同哈希、规范列、真实外键和临床作用域闭包。
3. 两个主读道缺一时不得形成持久化对账；手写专项读只作为可选第三读，不能替代主读。
4. 覆盖预期页清单必须逐项等于处理修订冻结页清单；失败和舍弃页面继续保留各自原因。
5. 新增批次落盘入口，事务由调用方持有；任一记录失败时不得留下可误认作完整结果的半批数据。
6. 产品判读链继续仅使用内置 HTTP 客户端和显式环境变量，未引入 Hermes、OMP、ZCode 或外部 harness。

## 验证

- 聚焦迁移、仓储、合同与执行：`40 passed`。
- 存储层全量：`505 passed`。
- 完整 `tests/v2`：`3710 passed, 3 skipped, 2 subtests passed`。
- `python -m compileall -q app` 通过。
- 定向 `git diff --check` 通过。
- 项目虚拟环境未安装 Ruff/Black，因此未运行这两个工具，也未临时引入依赖。

## 仍未完成

- main-B 显式凭据仍缺，三端点真实身份预检和最小合成页调用尚未执行。
- 金标集产品 harness 复跑、31001 端到端逐页覆盖、事实/Profile 回源临床质检及浏览器验收尚未完成。
- Phase 5 继续保持 `claims_complete=false`，不得进入 Phase 6。

## 下一安全动作

1. main-B 凭据具备后，只从显式 env 做三路身份预检与最小合成页调用；不读取任何外部 harness 配置。
2. 预检通过后，在既有金标集复跑产品 harness，先报告召回率、静默漏判、手写采信与冲突数字，再决定是否进入 31001 真实试运行。
