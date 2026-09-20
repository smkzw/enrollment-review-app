# 执行输出：phase5-prompt-contract-versioning-20260902 - worker_03

## 边界与上下文检查

- 角色：`worker_03`，工作项 3（独立审查旧历史不可变性、当前重建确定性及聚焦/完整协议测试，记录剩余风险）。只读审查 + 系统临时目录内的诊断性重建；未写入任何工作区文件，未做最终临床/监管验收，未审同侪，未开会议。
- 已读初始读取集：`context/phase5-prompt-contract-versioning-20260902_execution_context.md`、`plans/codex_execution_phase5-prompt-contract-versioning-20260902.md`。因上下文 Source-Of-Truth 为 TODO 且我的职责是独立复核 worker_01/02 的结论，额外读取：`runs/execution/phase5-prompt-contract-versioning-20260902/worker_01.md`、`worker_02.md`（作为被审查主张的来源，非指令）、三份检查点 JSON（v1/v2/v3）、`app/agents/protocol_control_deconstructor.py`（节选）、`app/protocols/protocol_replay_harness.py`（节选）、`tests/v2/protocols/test_protocol_replay_harness.py`（节选）。全部读取均在 workspace 内。
- 防写入措施：pytest 加 `-p no:cacheprovider` 与 `PYTHONDONTWRITEBYTECODE=1`；双构建 out-dir 与临时产物均在 `/tmp`（已清除）；会话末复核确认近 15 分钟无新增 `__pycache__` 写入，171 个已跟踪脏文件均为派发前既存的 phase 5 工作，本会话未触碰。

## 已执行的工作

三项审查全部独立通过，与 worker_01/02 报告一致；结论：**旧历史不可变、当前链确定性可重建、聚焦与完整协议回归全绿**。剩余风险见第 7 节，其中"关键工件未入 git 历史"建议在验收时处理。

### 1. 旧历史不可变性（独立复核，通过）

- **mtime 证据**：config v1 `2026-08-29 03:47`、REANCHOR 政策 `08-29 04:00`、checkpoint v1 `08-30 14:25`、v2 `08-30 23:56`，全部早于本执行包创建（09-02 06:04:33）；`checkpoints/` 目录内唯一新文件为 v3（09-02 06:20）。暂停的 live 回放 `runs/protocol_control_replay/d001-phase-ii-20260831/`（`run_record.json` 08-31 09:42）与权威库 `data_v2/enrollment-review-v2.sqlite3`（08-31 22:07）均未被触碰。
- **冻结源证据**：`source-input/blobs/protocol_sources/362443131f0d….docx`（405,567 字节）实测 SHA-256 与其内容寻址文件名及三份检查点的 `protocol_document_sha256` 逐一相等。
- **身份链证据（逐字段读取三份 JSON 交叉核对）**：方案哈希、`snapshot_id snp-e3e8befc…`、`manifest_id su-8f734878…`、`batch_id pcb-b29b96bc…`、单元计数（3581/1848/3/7）、工具链钉扎（Python 3.12.13 / pydantic 2.13.3 / docx-ooxml 1.4.0）在 v1/v2/v3 完全一致；仅 `prompt_sha256`（v1 `35d5d5fb…` → v2 `115812e7…` → v3 `df0d573a…`）与整包指纹（`d83e1032…` → `e842e33c…` → `c32bc9dd…`）沿版本轴演化。v3 `supersedes_checkpoint` 指向 v2，`model_invoked=false`、`clinical_acceptance=false`。
- **测试钉扎证据**：`test_previous_d001_replay_checkpoint_remains_immutable_history` 现同时钉死 v1 `35d5d5fb…` 与 v2 `115812e7…`/`e842e33c…`（只追加、未删改 v1 原有断言），并断言三版指纹互异、方案哈希与身份轴相同；全库检索确认无其他文件以代码形式钉扎这些哈希或仍把 v2 当作重建目标。

### 2. 当前重建确定性（独立复核，通过）

- **版本声明**：`app/agents/protocol_control_deconstructor.py:110` `CONTROL_AGENT_PROMPT_VERSION = "phase5/control-agent-prompt/v1.6"`，在 `__all__` 导出。我独立调用 `protocol_control_agent_prompt_template_sha256(DEFAULT_…)` 得 `2e2aaf4db691ad2860109abcf0651053c0539c3ee4233e7c4f8927b3515d943d`，与 v3 记录的 `prompt_template_sha256` 相等。
- **解耦与中立**：模板正文中无 `v1.5`/`v1.6` 字样（版本串不进正文），无 `D001`/`MG-K10-SAR`（中立护栏成立）。
- **双构建复现**：我在 `/tmp` 两个独立 `mktemp` 目录用 CLI 对同一 config v1 各构建一次：两次提示词 SHA `df0d573a…`、整包指纹 `c32bc9dd…`、单元数 3581/1848/3/7 完全一致；`diff -r` 证明两包**逐字节相同**；`--verify-pack --expected-fingerprint c32bc9dd…` 校验通过、exit 0。v3 `recorded_at 2026-09-01T22:20:23+00:00` 即北京时间 09-02 06:20:23，与 mtime 一致（UTC/本地换算，无异常）。
- **版本记录字段**：`protocol_replay_harness.py:537-540` 在 summary 新增 `prompt_version`/`prompt_template_sha256`；schema 字面量仍为 `phase5/protocol-replay-harness-summary/v1`（只加字段）。我读取 verify 逻辑确认：新字段未被 `verify_replay_pack` 强制要求（`.get()` 读取），且 `replay-summary.json` 本身不入整包指纹——新字段对旧包校验向后兼容。全库检索确认 summary 无仓库内其他严格消费方。

### 3. 聚焦/完整协议测试（独立运行，通过）

- 聚焦：`test_protocol_replay_harness.py + test_protocol_control_anti_overfit.py + test_protocol_control_anti_overfit_chain_wide.py` → **57 passed**（1.96s），含 v3 重建、v1/v2 不可变历史、词汇中立护栏。
- 完整：`tests/v2/protocols tests/v2/agents` → **1447 passed, 0 failed**（157.39s）。worker_01 派发前实测的唯一失败项（v1.5 提示词 SHA 漂移导致 v2 重建断言失败）已消除，完整协议回归恢复。
- 变更面收窄复核：包窗口（09-02 05:00 后）内被修改的源/测试文件恰为 worker_02 所述三个文件（`protocol_control_deconstructor.py`、`protocol_replay_harness.py`、`test_protocol_replay_harness.py`）+ 新增 v3 检查点；工具链实测（3.12.13 / 2.13.3 / 1.4.0）与检查点钉扎一致，不构成再锚定条件。

## Artifacts And Evidence

本工作项为独立审查，无新工件。证据落点：

| 审查项 | 证据 |
|---|---|
| 旧历史不可变 | checkpoints 目录 mtime 清单；冻结 blob SHA 实测；三份检查点 JSON 逐字段身份链；v1/v2 哈希钉扎测试通过；live 回放与权威库 mtime |
| 版本声明与登记 | `protocol_control_deconstructor.py:110`；模板 SHA 独立重算 = `2e2aaf4d…` = v3 记录 |
| 重建确定性 | 双临时构建指纹一致 + `diff -r` 逐字节相同 + `--verify-pack` exit 0 + v3 重建单测通过 |
| 版本记录字段 | `protocol_replay_harness.py:537-540`；重建包 summary 实读含两新字段且 schema 仍 `/v1` |
| 回归恢复 | 聚焦 57 passed；完整 1447 passed, 0 failed（157s） |

## Commands And Observations

- `stat`/`shasum -a 256`：冻结 blob 哈希 `362443131f0d…` 与文件名一致；checkpoints/live 回放/权威库 mtime 核对。
- `.venv/bin/python -c`：独立计算 `protocol_control_agent_prompt_template_sha256` → `2e2aaf4d…`；模板正文无版本串、无 D001/MG-K10-SAR。
- `mktemp -d` ×2 + `scripts/run_protocol_replay_harness.py --config p803-p805-…-config.v1.json --out-dir $TMP/pack` ×2 → 两次提示词 SHA `df0d573a…`、包指纹 `c32bc9dd…` 一致；`diff -r` → 逐字节相同；`--verify-pack --expected-fingerprint c32bc9dd…` → 校验通过，exit 0；临时目录已清除。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest …`（`-p no:cacheprovider`）：聚焦 57 passed；完整 `tests/v2/protocols tests/v2/agents` → 1447 passed, 0 failed, 157.39s。
- `find -newermt` / `git status --porcelain`：包窗口内源/测试改动仅三个文件 + v3 检查点；四个关键路径均为 git 未跟踪状态（`??`）；近 15 分钟无新增 `.pyc`，确认本会话零工作区写入。

## Blockers Or Missing Environment

无阻塞。环境完整（`.venv` Python 3.12.13 / pydantic 2.13.3 / parser 1.4.0，与检查点钉扎一致）。

剩余风险（按影响排序；均为记录项，无一项阻塞验收）：

1. **关键工件未入 git 历史（最需处理）**：`protocol_control_deconstructor.py`、`protocol_replay_harness.py`、`test_protocol_replay_harness.py` 及整个 checkpoints 目录（含 v1/v2/v3）在本 worktree 均为未跟踪文件。在提交之前，"不可变"仅有 mtime + 测试钉扎 + 身份链交叉核对支撑，git 无法提供防篡改证据。**建议**：验收通过后尽快把这四个路径纳入提交（至少 checkpoints 目录），把 mtime 证据升级为可审计的 git 历史。
2. **历史漂移不可归因（继承自既存欠账）**：v2 冻结（08-30 23:56）至 08-31 09:43 之间的提示词正文改动无 git 历史可逐条归因。本包已把当前正文原样登记为 v1.6（未做语义修改，模板 SHA `2e2aaf4d…` 与漂移实测 `df0d573a…` 双向印证），但那批漂移本身从未被逐行评审——属已登记、未追溯的既存事实。
3. **版本号裁决未闭合**：worker_01 提出 v1.6 vs v2.0，实现按其建议取 v1.6。若 Codex 改判 v2.0，只需改常量并更新 v3 的 `prompt_version`/`prompt_template_sha256` 字段；版本串不进正文、summary 不入指纹，整包指纹 `c32bc9dd…` 不受影响，已冻结双构建结论依然有效。
4. **未来漂移的流程约束靠测试兜底**：模板正文再变更而未升版本号时，重建单测会以 `prompt_sha256` 失败的形式报警（检测机制有效），但此后每次都要走完整 REANCHOR 双构建 + 新检查点流程；目前没有阻止"改正文不升版本"提交的自动化门禁，属流程性而非缺陷性风险。
5. **summary 加字段的兼容边界**：schema 字面量保持 `/v1`、verify 用宽松读取、仓库内无严格外部消费方；但若未来引入拒绝未知键的严格消费者需重新评估。旧包（无新字段）仍可通过 verify，向后兼容已实测确认。
6. **重建 ≠ 临床验收**：v3 明示 `model_invoked=false`、`clinical_acceptance=false`；本检查点只证明确定性产品链可重现，不构成任何临床结论，也不授权模型重放；暂停的 live 回放（19 个批次检查点）与权威库仅以 mtime 未动为证据，未在本包内重建（超出本工作项范围）。

## Rerun Requests Or Next Step

- 无重跑请求。三项审查全部通过，建议 Codex 将工作项 3 记为完成，并可采信"旧不可变测试通过 + v3 重建测试通过 + 聚焦 57 / 完整 1447 全绿"作为回归恢复判据（我已独立复跑同一判据）。
- 提请 Codex 裁定的既有事项：版本 id v1.6 vs v2.0（见风险 3，不阻塞）；以及风险 1 的提交时机——建议与本包验收一并处理，使检查点链在合并前进 git 历史。
- Phase 5 `claims_complete=false` 维持不变；本审查不构成临床/监管验收，Codex 保留最终验收权。
