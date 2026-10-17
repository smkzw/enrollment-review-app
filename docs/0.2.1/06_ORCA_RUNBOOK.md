# 0.2.1 ORCA RUNBOOK：用 Orca 编排多 Agent

Codex 作为统筹者在 Orca 终端中运行，通过 `orca orchestration` 把任务派给 OMP（多模型）与 CodeBuddy 执行节点，收回结果、审查、合并。本文件给出前置条件、权限、冒烟测试、分工、规则和命令示例。

**命令以构建机上安装的 Orca 版本为准。** Orca 编排层仍标为实验功能，命令变动频繁。统筹者开工时先运行 `orca skills get orchestration` 读取与本机版本一致的指南，并对用到的命令先看 `--help`；本文命令只作示例，与本机指南不一致时以本机为准，并在状态表记一行。

资料来源（2026-10-17 查阅）：github.com/stablyai/orca 的 `README.md`、`docs/site/content/docs/cli/{orchestration,reference}.mdx`、`docs/site/content/docs/agents/supported.mdx`、`skill-guides/orchestration.md` 及 `skill-guides/orchestration/references/coordinator-loop.md`、issue #22947、#24431、#17557。

---

## 1. 前置条件（构建机）

| 项 | 做法 | 检查 |
|---|---|---|
| Orca 桌面版 | `brew install --cask stablyai/orca/orca`，或从 GitHub Releases 下载 DMG | 打开 Orca |
| `orca` 命令 | Settings → General → Orca CLI 注册；Orca 自己的终端里默认可用 | `orca status --json` |
| 编排层 | Settings → Experimental → 开启 orchestration | `orca skills get orchestration` 能输出指南 |
| Codex CLI | 安装并登录（Orca 从 `~/.codex` 启动 `codex`） | Orca 终端里 `codex --version` |
| OMP | 已安装并登录各模型（agent ID `omp`） | `omp --version` |
| CodeBuddy CLI | `npm install -g @tencent-ai/codebuddy-code` 并登录（agent ID `codebuddy`） | `codebuddy --version` |
| Agent 技能 | `orca skills install --skill orca-cli --skill orchestration` | 统筹者会话中可调用 |
| 仓库 | 在 Orca 中打开构建工作树；`orca repo set-base-ref --repo id:<repoId> --ref origin/dev/0.2.1 --json`，让新工作树都从 `dev/0.2.1` 分出 | `orca repo show` 或等价命令查看 base ref |

## 2. 权限与数据边界（D40）

- 已知问题 #22947：macOS 默认沙箱中的 Codex 无法连接 Orca 本地运行时，`worker_done` 发不出去；Manual 模式下无人值守的节点会卡在确认提示上。
- 因此：
  - **执行节点**（OMP、CodeBuddy、Codex 类）用 Orca 默认的免确认启动参数（Yolo）。
  - **统筹者**同样以免确认参数启动（否则每条 `orca` 命令都要人工批准）；它是用户直接看着的节点。
- 免确认模式下，数据边界靠三层保证：
  1. **数据与密钥在仓库外**：验证副本和 `.env` 放在仓库目录之外（第 0 波完成），执行节点的工作树里没有这些文件；
  2. **任务说明明令禁止**读写数据目录、`.env`、服务与浏览器；
  3. **合并前核对**：统筹者对每个节点分支运行 `git diff --name-only dev/0.2.1...<分支>`，任何不在任务说明文件列表内的改动都拒绝合并并打回。
- #24431：Orca 启动的 Codex 可能不读 `~/.codex/rules`，不要依赖规则文件做权限控制。
- #17557：编排消息的发送方认证较弱，只在本机可信环境中使用，不开远程配对端口。

## 3. OMP 如何指定模型

`worker-start --model` 只对 Claude、Codex、Cursor、Antigravity、Muse 生效；OMP 用它自己的配置选模型（OMP 命令行支持 `--model`、`--provider`、`--profile`）。文档支持的做法是先开一个指定模型的终端，再把任务派到这个终端：

```bash
# 1) 为任务建工作树（不启动 agent，或按本机 --help 的等价方式）
orca worktree create --name c1a --json
# 2) 在该工作树中开一个指定模型的 OMP 终端
orca terminal create --worktree <worktreeSelector> --title "omp-grok47" --command "omp --model <provider/grok-4.7>" --json
orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 60000 --json
# 3) 把任务派给这个终端（--terminal 不能与 --model 同用）
orca orchestration worker-start --task <taskId> --terminal <handle> --json
```

冒烟测试中确认这条路可用，并记录各模型对应的 `--model` 写法。若不可用，退回到"只用 OMP 默认模型＋CodeBuddy"，在状态表说明。

## 4. 冒烟测试（第 0 波，≤1 小时）

目的：验证"新工作树＋改文件＋跑测试＋回报"在免确认模式下能无人值守跑完。

```bash
orca status --json
orca skills get orchestration
orca orchestration run-create --objective "0.2.1 convergence sprint" --json   # 整个冲刺只建这一个 Run
orca orchestration task-create --task-title "smoke-<agent>" \
  --spec "运行 git log -1 --oneline；在 docs/0.2.1/ 下新建 SMOKE_<agent>.md 写一行字；运行 uv run pytest tests/v2/domain -q -x 并记录通过数；用 worker_done 回报（--outcome succeeded 或 failed）。" --json
orca orchestration worker-start --task <taskId> --worktree new-child --name smoke-<agent> --agent <omp|codebuddy> --json
orca orchestration check --wait --types worker_done,escalation,question --timeout-ms 900000 --json
orca orchestration worker-read --dispatch <dispatchId> --limit 50 --json
orca orchestration worker-release --dispatch <dispatchId> --json
```

对 `codebuddy`、OMP 默认模型，以及按 §3 开出的每个 OMP 模型终端各跑一次。通过标准：收到 `worker_done`；分支上只有那一个新文件；测试结果正确；release 成功。冒烟分支不合并，测试后删除。

**降级方案**（失败时按顺序采用，并记录）：
1. 编排层可用但个别 agent 收不到 `worker_done`：该 agent 只用于无监督交接（`orca worktree create --name x --agent <id> --prompt "…" --json`，再用 `orca terminal wait/read` 取结果），其余照常编排。
2. 编排层整体不可用：全部改用无监督交接，统筹者用 `orca terminal read` 收结果，用 git 分支收代码。
3. Orca 整体不可用：统筹者内联执行 `03_PLAN.md`，在第 0 波简报中说明，不在安装问题上继续消耗时间。

## 5. 分工

默认分配如下；第 1 波结束后统筹者可按实际表现调整，在状态表记录原因。

| 用途 | 默认节点 | 说明 |
|---|---|---|
| "管道"节点：C2 → C5 → C6a → C6b | OMP grok-4.7 或 kimi-k3 | 这几项都改 `work_draft_review.py` 及相邻文件，交给同一节点顺序做 |
| "计算"节点：C1b＋C4 → C3 → C7a | OMP kimi-k3 或 composer 2.5（cursor auto） | 都改 `work_draft_calculation.py`／用药／API，同一节点顺序做 |
| C1a 标记契约 | OMP composer 2.5 或 grok-4.7 | 独立文件集 |
| C8 评测脚本 | OMP glm-5.3-flash 或 gemini-3.8-flash | 新文件 |
| C7b 前端 | OMP composer 2.5（cursor auto）或 gemini-3.8-flash | 浏览器检查由统筹者做 |
| 代码评审（每个待合并 diff） | CodeBuddy deepseek-v4.1-flash | 必须与实现者不同模型；只读；`--worktree current` |
| 医学结果评审（G1、G2 各一次） | OMP gemini-3.8-flash 或 grok-4.6 | D39：可读真实原件页，只读、不留存；不用 glm（它也是产品抽取模型，盲点可能相同） |

## 6. 规则

1. **一个 Run**：整个冲刺只用第 0 波建的那个 Run。统筹者在自己的 Orca 终端里运行并保持绑定；不要每波新建 Run（会改绑，导致仍在运行的节点消息发到旧 Run）。
2. **隔离**：写代码的节点一律 `--worktree new-child`（或 §3 的指定模型终端）；分支名 `w/0.2.1-<任务>`。只读节点可用 `--worktree current`。
3. **基于最新代码**：每次合并后立即推送 `dev/0.2.1`；每个任务说明的第一步是 `git log -1 --oneline`，确认包含它依赖的提交。
4. **依赖**：有依赖的任务用 `task-create --deps '["<taskId>", …]'` 建立（`--deps` 接 JSON 数组）。
5. **并发**：同时最多 3 个实现节点＋1 个评审节点；同一文件同一时刻只派给一个节点。
6. **数据**：执行节点不读写数据目录、`.env`，不启动或停止服务，不发起产品模型调用，不使用浏览器（医学结果评审节点只读统筹者提供的导出和原件页）。
7. **合并**：只有统筹者合并：核对改动文件清单 → 审 diff → 跑任务测试 → 评审节点通过 → 合并到 `dev/0.2.1` → 推送。波次结束快进推 `main`。执行节点不推送、不开 PR。
8. **提问**：节点用 `orca orchestration ask` 问统筹者。统筹者能答的直接答；涉及医学判断的记入医学问题单，告诉节点先做不依赖它的部分，或以 `failed` 回报。
9. **失败**：同一任务两次 `failed` 或两次回报不合格，统筹者收回（`worker-stop`／`worker-release`），重写任务说明或亲自处理。
10. **收尾**：接受回报后立即 `worker-release`；需要排查时才 `worker-retain`，用完再 release。
11. **看板**：任务进度看 `orca orchestration task-list`；状态表只在波次结束时更新。

## 7. 统筹者循环（示例）

```bash
# 第 0 波已建 Run：run_xxx。第 1a 波：
orca orchestration task-create --task-title "C2"  --spec "$(cat output/0.2.1/specs/C2.md)"  --json
orca orchestration task-create --task-title "C1a" --spec "$(cat output/0.2.1/specs/C1a.md)" --json
orca orchestration task-create --task-title "C8"  --spec "$(cat output/0.2.1/specs/C8.md)"  --json
orca orchestration task-create --task-title "C5"  --spec "$(cat output/0.2.1/specs/C5.md)"  --deps '["<C2>","<C1a>"]' --json
# 派发（指定模型时按 §3 先开终端，再 worker-start --terminal）
orca orchestration worker-start --task <C2> --terminal <omp-grok47-handle> --json
orca orchestration worker-start --task <C1a> --worktree new-child --name c1a --agent omp --json
orca orchestration worker-start --task <C8> --worktree new-child --name c8 --agent codebuddy --json
# 等待并处理每条消息
orca orchestration check --wait --types worker_done,escalation,question --timeout-ms 1800000 --json
#   worker_done：worker-read 看回报 → git diff --name-only 核对文件 → 审 diff、跑测试 → 派评审 → 合并、推送，或打回
#   question：能答就回复；医学问题记入问题单
orca orchestration check --ack <deliveryId> --wait --types worker_done,escalation,question --timeout-ms 1800000 --json
orca orchestration worker-release --dispatch <dispatchId> --json
orca orchestration task-list --json
```

任务说明文件放本机 `output/0.2.1/specs/`，不入库。
