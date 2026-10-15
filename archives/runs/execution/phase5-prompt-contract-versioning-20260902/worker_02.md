# 执行输出：phase5-prompt-contract-versioning-20260902 - worker_02

## 边界与上下文检查

- 角色：`worker_02`，工作项 2（实现当前提示词版本声明、重放包版本记录和新的只读检查点；禁止写入项目特异生产逻辑）。未做最终临床/监管验收，未审同侪，未开会议。
- 已读初始读取集两份（execution context、execution plan）。因上下文 Source-Of-Truth 为 TODO 且 journal-2.md Session 103 记录本会话前序实例被 `SIGINT/130` 中断、现场留有未验证的部分产物，额外读取：`.trellis/workspace/codex/journal-2.md`（Session 96–103）、`runs/execution/phase5-prompt-contract-versioning-20260902/worker_01.md`（完整只读分析）、`app/agents/protocol_control_deconstructor.py`、`app/protocols/protocol_replay_harness.py`、`tests/v2/protocols/test_protocol_replay_harness.py`、`scripts/run_protocol_replay_harness.py`、checkpoints 目录五份文件。全部读取均在 workspace 内。
- 关键边界执行情况：**未改写 v1/v2 历史检查点**（mtime/内容双证）、**未改提示词正文/系统合同/JSON schema 的临床语义**（漂移 SHA `df0d573a…` 为 worker_01 派发前实测的既存事实，本次仅登记）、**未引入项目特异逻辑**（反过拟合护栏测试通过）。

## 已执行的工作

前序 worker_02 会话（06:04–06:20，SIGINT 中断）已留下实现但未经任何验证。本会话按"先审差异、不视为已完成修复"原则逐项独立复核，全部通过，无需补码：

1. **当前提示词版本声明**（确认已实现）：`app/agents/protocol_control_deconstructor.py:110` `CONTROL_AGENT_PROMPT_VERSION = "phase5/control-agent-prompt/v1.6"`，且在 `__all__`（:121）导出。采用 worker_01 建议的微升先例 v1.5→v1.6。
2. **重放包版本记录**（确认已实现）：`app/protocols/protocol_replay_harness.py:537-540` 在 `replay-summary.json` 新增 `prompt_version` 与 `prompt_template_sha256` 两字段；summary schema 字面量保持 `…-summary/v1` 不变（只加字段），与 worker_01 边界 3 一致。注释明确"版本串不进提示词正文，包身份与版本轴解耦"——我实测模板正文/系统合同/修复合同中均无 `v1.5`/`v1.6` 字样，解耦不变量成立。
3. **新的只读检查点**（确认已实现）：`…/research/d001-ii-phase-closure/checkpoints/p803-p805-model-free-replay-checkpoint.v3.json`，schema `phase5/protocol-replay-checkpoint/v3`，`supersedes_checkpoint: v2`（链式先例），记录 `prompt_version v1.6`、`prompt_template_sha256 2e2aaf4d…`、`prompt_sha256 df0d573a…`、整包指纹 `c32bc9dd…`，`model_invoked=false`、`clinical_acceptance=false`。
4. **测试对齐**（确认已实现）：`test_protocol_replay_harness.py` 重建目标切至 v3（:454-490，逐字段含新版本字段断言）；不可变历史测试（:493-538）钉死 v1 `35d5d5fb…` 与 v2 `115812e7…`/`e842e33c…`，只追加不删改，符合 worker_01 不得修改项。
5. **完整协议回归恢复**（本会话核心增量验证）：`tests/v2/protocols + tests/v2/agents` 共 **1447 passed, 0 failed**（167 秒）。Session 102 以来的唯一失败项（D001 v1.5 提示词 SHA 漂移）已消除。
6. **REANCHOR 政策合规复核**：按 `REANCHOR_MODEL_FREE_REPLAY.md` 独立执行双目录重建（系统临时目录，不入库），两次整包指纹一致且等于 v3 记录值；方案哈希、snapshot/manifest/batch 身份、单元数（3581/1848/3/7）与 v1/v2 完全一致；`verify_replay_pack` 对 v3 指纹校验零不一致。

## 工件与证据

本会话未新写/未改任何工作区文件；全部产出为对前序部分产物的验证证据：

| 工件（前序会话产物，本次验证） | 证据 |
|---|---|
| `app/agents/protocol_control_deconstructor.py:110` | 版本常量 v1.6；`protocol_control_agent_prompt_template_sha256` 实测 = `2e2aaf4db691ad2860109abcf0651053c0539c3ee4233e7c4f8927b3515d943d`，与 v3 记录一致 |
| `app/protocols/protocol_replay_harness.py:537-540` | 重建包 summary 含 `prompt_version`/`prompt_template_sha256`；mode=model_free，transport_instantiated=false |
| `checkpoints/p803-p805-model-free-replay-checkpoint.v3.json` | mtime Sep 2 06:20；双构建指纹 `c32bc9dd…` 复现；`verify --expected-fingerprint` exit 0 |
| v1/v2/config/冻结 blob 不可变性 | v1 mtime 08-30 14:25、v2 08-30 23:56、config 08-29 03:47 均早于本包；冻结 DOCX SHA `362443131f0d…` 与三份检查点一致；`runs/protocol_control_replay/d001-phase-ii-20260831/`（暂停 live 回放）mtime 08-31/09-01 未动 |
| 变更面收窄证据 | 中断窗口（09-02 06:00–06:40）内源码/测试改动仅上表三个文件 + v3 检查点；`docs/PROJECT_CONTEXT.md`、`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` 的 06:01 mtime 早于包创建（06:04:33），属 Codex 派发前编辑，非本执行包产物 |

## 命令与观察

- `pytest tests/v2/protocols/test_protocol_replay_harness.py tests/v2/protocols/test_protocol_control_anti_overfit.py tests/v2/protocols/test_protocol_control_anti_overfit_chain_wide.py -q` → **57 passed**（含 v3 重建、v1/v2 不可变历史、提示词/夹具词汇中立护栏）。
- `pytest tests/v2/protocols tests/v2/agents -q` → **1447 passed, 0 failed**（2:47）。
- `scripts/run_protocol_replay_harness.py --config p803-p805-…-config.v1.json --out-dir $TMP_A/pack` 与 `$TMP_B/pack` 两次独立构建 → 两次 `包指纹 c32bc9dd…`、`提示词 SHA df0d573a…` 完全一致；`--verify-pack $TMP_A/pack --expected-fingerprint c32bc9dd…` → `校验通过`，exit 0；临时包已清除，未入 workspace。
- `.venv/bin/python` 直接计算 `protocol_control_agent_prompt_template_sha256(DEFAULT_…)` → 与 v3 `prompt_template_sha256` 相等。
- `py_compile` 三个改动文件 → OK；`git diff --check` → 干净。
- 工具使用记录：Read（初始读取集、journal、worker_01 报告、harness/测试/CLI/检查点源文件）、Bash（grep/find/pytest/双构建/shasum/py_compile/git）、无写入类工具调用。

## 阻塞项或缺失环境

无阻塞。环境完整（`.venv` Python 3.12.13 / pydantic 2.13.3 / parser 1.4.0 与检查点钉扎一致）。

不确定性（如实记录）：
- 三个改动文件均为未跟踪文件（本 worktree 约 1212 个未跟踪路径），无法用 git 逐字节 diff 前序会话改动。缓解：worker_01 派发前实测已钉当前正文 SHA=`df0d573a…`（即漂移先于本包存在，本次版本化未改正文）；模板 SHA、双构建指纹、1447 项回归三路独立复核一致。
- v2 冻结后至 08-31 09:43 的正文漂移具体条目无法逐条归因（无 git 历史），与 worker_01 结论相同；对本任务仅需登记当前正文，不影响验收。
- 新增 summary 字段使新建包整包指纹相对 v2 必然变化（v3 notes 已声明）；v1/v2 记录的旧指纹仅代表其冻结时点，属既定设计取舍，非缺陷。

## 重跑请求或下一步

- 无重跑请求。实现与验证均已完成，建议 Codex 采纳为工作项 2 完成，并交 worker_03 做独立审查（其范围含旧历史不可变性、重建确定性与聚焦/完整协议测试，我已留全三路证据）。
- 留给 Codex 的既有裁定项（不阻塞）：worker_01 提出的版本 id 取 `v1.6` vs `v2.0` 问题，前序会话已按其建议默认取 `v1.6`；若 Codex 改判 `v2.0`，只需改常量并重算 v3 的 `prompt_template_sha256`（重放包指纹不受影响，版本串不进正文）。
- Phase 5 `claims_complete=false` 维持；本检查点仅证明确定性链可重建，不构成临床验收，不授权模型重放。
