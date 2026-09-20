# 执行输出：phase5-prompt-contract-versioning-20260902 - worker_01

## 边界与上下文检查

- 角色：`worker_01`，任务项 1（只读分析现有提示词版本、重放配置与 v1/v2 检查点，给出最小兼容边界和不得修改项）。未写入任何工作区文件；未执行任何生产写入。
- 已读取初始读取集：`context/phase5-prompt-contract-versioning-20260902_execution_context.md`，`plans/codex_execution_phase5-prompt-contract-versioning-20260902.md`。上下文的 Source-of-Truth（事实来源）部分为待办（TODO），因此我自行在工作区内定位了权威文件；下方记录了所有额外读取的内容。
- 超出初始读取集的读取内容：`app/agents/protocol_control_deconstructor.py`，`app/agents/phase_applicability.py`，`app/agents/protocol_deconstructor.py`，`app/domain/contracts/agents.py`，`app/protocols/protocol_replay_harness.py`，`app/protocols/docx_structure.py`，`app/services/protocol_control_execution.py`，`scripts/run_protocol_replay_harness.py`，`tests/v2/protocols/test_protocol_replay_harness.py`，检查点目录 `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/checkpoints/`，`CHECKPOINT_20260831_D001_READONLY_REPLAY_PAUSED.md`，`implement.md`，`.trellis/workspace/codex/journal-1.md`，运行记录 `runs/protocol_control_replay/d001-phase-ii-20260831/run_record.json` 和 `runs/protocol_control_smoke/quality-positive-control-packed48-v4-20260831/run_record.json`，以及之前记录此偏差的归档 worker/评审报告。
- 执行了一次诊断性测试运行（见命令部分），并采取了防止写入措施（`-p no:cacheprovider`，`PYTHONDONTWRITEBYTECODE=1`）；`pytest` 的 `tmp_path` 写入了系统临时目录，而非工作区。原理：确认当前实时偏差状态是当前工作项的核心可交付成果，而非第二/三工作项（worker 02/03）的构建/回归范围。

## 已执行的工作

### 1. 现有提示词版本清单（观察）

方案控制链路当前版本常量均在 `app/agents/protocol_control_deconstructor.py`：

| 版本轴 | 当前值 | 位置 |
|---|---|---|
| 深析 Agent 提示词 | `phase5/control-agent-prompt/v1.5` | `protocol_control_deconstructor.py:110` |
| 发现阶段提示词 | `phase5/control-discovery-prompt/v1` | `protocol_control_deconstructor.py:112` |
| 深析 wire / input | `phase5/control-agent-wire/v1`，`phase5/control-agent-input/v1` | `:107-108` |
| 发现 input / wire | `phase5/control-discovery-input/v1`，`phase5/control-discovery-wire/v1` | `:111,113` |
| 发现响应格式名 | `protocol_control_discovery_wire_v1` | `:115` |
| 发布门禁 | `phase5/control-publication-gate/v1` | 见 `runs/protocol_control_smoke/.../run_record.json` |

链路外但同属"提示词版本"的轴（本任务不得触碰）：`phase5/phase-applicability-agent-prompt/v13`（`app/agents/phase_applicability.py:64`）；领域合同 `PromptVersion(prompt_version_id, node, template_sha256, schema_version_id)`（`app/domain/contracts/agents.py:20`）；方案解构 Agent 已有的运行时"版本哈希与正文一致"强制校验（`app/agents/protocol_deconstructor.py:4295-4301`）；事实规范化的 `prompt_versions` DB 表及 `fact_normalization_runs.prompt_version_id`（迁移 `0002_domain_schema.py:138`、`0013_clinical_facts_profile_v2.py:136`）；证据 normalizer 提示词哈希。

**关键机制事实（观察）**：
- `protocol_control_agent_prompt_template_sha256`（`:1786`）= SHA-256 over `(版本常量, 模板正文, _CONTROL_AGENT_SYSTEM_CONTRACT, _CONTROL_REPAIR_CONTRACT, schema JSON)`，逐批次记录到运行载荷（`app/services/protocol_control_execution.py:1176` discovery、`:1469` deep）。
- `build_protocol_control_agent_prompt`（`:1799`）构建的提示词正文**不含版本字符串**（全文件中 `v1.5` 仅出现在常量定义处）。因此：只升版本号会改变运行记录里的 `prompt_template_sha256`，但**不会**改变重放包 `prompt_sha256` 与整包指纹；v2 冻结后的漂移来自模板/合同/schema 的**正文内容**修改。
- 重放 harness（`app/protocols/protocol_replay_harness.py`）schema：config `/v1`（`:86`）、input `/v1`（`:87`）、summary `/v1`（`:88`）。`replay-summary.json`（`:518-534`）记录 `prompt_sha256` 但**没有任何 prompt_version 字段**——这正是工作项 2 要补的"版本声明/版本记录"缺口。
- CLI 入口 `scripts/run_protocol_replay_harness.py`：`--config / --verify / --verify-pack DIR --expected-fingerprint / --out-dir`，退出码 0/2/3。
- 再锚定政策文档 `checkpoints/REANCHOR_MODEL_FREE_REPLAY.md`：仅允许在 Python/Pydantic/DOCX 解析器/确定性产品链**有意变更**导致检查点失败时再锚定；必须双目录独立构建指纹一致、方案哈希/refs/身份不变、`model_invoked=false`、`clinical_acceptance=false`、聚焦+完整协议回归通过；临时重放包不得入库。

### 2. D001 v1/v2 历史检查点（观察）

"v1/v2 检查点"即 `…/research/d001-ii-phase-closure/checkpoints/` 下的模型无关重放检查点（全库唯一以 v1/v2 命名的 D001 检查点对）：

- **config v1**（`p803-p805-model-free-replay-config.v1.json`）：冻结源 `research/d001-ii-phase-closure/source-input/blobs/protocol_sources/362443131f0d….docx`（405,567 字节，SHA 与检查点一致，已实地核对）；owned `body.p803/p804/p805`，attached `body.t5.r18 + body.p328,p685-689`；`pinned_created_at 2026-08-29`；`out_dir artifacts/phase5-slice61ao-p803-p805-model-free-replay`（该包按政策未入库）。
- **checkpoint v1**（schema `phase5/protocol-replay-checkpoint/v1`）：`prompt_sha256 = 35d5d5fb9f62…`，指纹 `d83e1032…`；notes 记录 2026-08-29/30 多轮通用合同修订均只重算提示词与指纹、方案/结构/批次/单元数不变。
- **checkpoint v2**（schema `…/v2`，`supersedes_checkpoint: v1`，冻结于 08-30 23:56）：`prompt_sha256 = 115812e731ff…`，指纹 `e842e33c…`；note 明示"v2 对应当前 phase5/control-agent-prompt/v1.5 合同"。方案哈希、`snapshot_id snp-e3e8befc…`、`manifest_id su-8f734878…`、`batch_id pcb-b29b96bc…`、单元数（blocks 3581 / manifest 1848 / owned 3 / context 7）与 v1 完全一致。
- 工具链钉扎：Python 3.12.13 / pydantic 2.13.3 / parser `docx-ooxml` 1.4.0。实地核对当前 `.venv` 为 Python 3.12.13、pydantic 2.13.3，`docx_structure.PARSER_VERSION = "1.4.0"`（注意这是产品常量，非 python-docx 包版本 1.2.0）——**工具链与钉扎一致，不构成再锚定条件**。
- 固定这两份历史的测试：`tests/v2/protocols/test_protocol_replay_harness.py:454`（用 config v1 重建、逐字段断言 v2）、`:488`（钉死 v1 的 `35d5d5fb…` 且断言 v1≠v2 指纹、方案哈希相同）。
- 中立性护栏：`tests/v2/protocols/test_protocol_control_anti_overfit.py:370-371` 断言提示词中不得出现 `D001` / `MG-K10-SAR`。

**当前漂移状态（实测观察）**：`test_d001_p803_p805_read_only_checkpoint_rebuilds` 在 `prompt_sha256` 断言失败——当前构建产出 `df0d573ae4a57d85b188f01171c9bdcb9412ec7759b629e47a160799d17e2d48`，v2 期望 `115812e7…`；**该断言之前的方案哈希、snapshot/manifest/batch 身份断言全部通过**，即只有提示词正文轴漂移，确定性结构链完好。`test_previous_d001_replay_checkpoint_remains_immutable_history` 通过。归档执行记录（`archives/execution/phase5-visual-observation-normalizer-contract-20260901/.../worker_02.md`、`runs/execution/phase5-ex07-issue-refinement-20260902/worker_01.md`、`reviews/codex_execution_phase5-engineering-corrections-2-4-6-20260902_review.md`）交叉印证：漂移源自 `protocol_control_deconstructor.py` 在 v2 冻结（08-30 23:56）之后、08-31 09:43 之前的正文修改，属先于本执行包的既存版本化欠账；journal 与 `implement.md:1409-1411` 早已裁定"旧检查点不可变，应以新提示词版本+新重放检查点处理"。

**另一条 D001 冻结线（区分轴，不在本提示词任务内改动）**：暂停的 live 只读回放 `runs/protocol_control_replay/d001-phase-ii-20260831/`（run_record + DB 副本；来源任务 `384a7b3b…` 冻结后按约定 `failed_final`，控制任务 `3259ab5f…` 已有 19 个完成批次检查点）、权威库 `data_v2/enrollment-review-v2.sqlite3`、任务级三份 CHECKPOINT 文档（08-29 / 08-31 两份 / 09-01）。

### 3. 最小兼容边界（推断/建议，Codex 裁定）

1. **冻结层绝对不可变**：v1/v2 检查点 JSON、config v1、冻结源 blob、两份测试中已钉死的哈希断言（v1 `35d5d5fb…`；v2 的 `115812e7…` 应升级为同样被"不可变历史"测试钉死）——任何情况下不改写、不原地重冻结。
2. **升级路径唯一**：新的提示词正文 ⇒ 新版本 id（建议 `phase5/control-agent-prompt/v1.6`，沿 v1→v1.5 微升先例）＋**新检查点文件**（建议 `p803-p805-model-free-replay-checkpoint.v3.json`，沿用 v2 的 `supersedes_checkpoint` 链式先例），并按 `REANCHOR_MODEL_FREE_REPLAY.md` 的双构建流程产出。v3 复用 config v1（同冻结范围），记录相同方案哈希/身份/单元数 + 新 `prompt_sha256`/新指纹。
3. **版本常量与重放指纹解耦**是本次"显式版本化"可行的基础：升 `CONTROL_AGENT_PROMPT_VERSION` 只影响运行记录的 `prompt_template_sha256`（增量字段，下游安全），不影响 v1/v2 指纹的"若用旧正文仍可重建"性质。工作项 2 在 summary 中新增版本记录字段（如 `prompt_version`、`prompt_template_sha256`）**会**改变新建包的 summary 内容 ⇒ 指纹变化，必须与新检查点 v3 同一变更内落地；`test_protocol_replay_harness.py:454` 的重建目标同时切到 v3。summary 的 schema 字面量（`…-summary/v1`）建议保持不变（只加字段、不改 schema 版本），避免扩大破坏面。
4. **本任务只做版本化，不改临床规则内容**：v1.6 的正文必须与当前实际产出逐字节一致（`df0d573a…` 即当前正文的指纹），不得借版本化夹带提示词语义修改；v3 notes 按 v2 先例写明"仅登记正文与指纹"。
5. **范围外不动**：discovery 提示词轴（`…/discovery-prompt/v1`，无检查点钉扎、无漂移证据）、phase applicability v13、deconstructor 的 `PromptVersion` 绑定机制、事实规范化 `prompt_versions`、evidence normalizer。
6. 中立性护栏必须继续成立：新提示词正文与包内任何新增字段不得引入 `D001`/`MG-K10-SAR` 等项目专名。

### 4. 不得修改项清单（供 worker_02/03 直接引用）

```
.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/checkpoints/p803-p805-model-free-replay-checkpoint.v1.json
.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/checkpoints/p803-p805-model-free-replay-checkpoint.v2.json
.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/checkpoints/p803-p805-model-free-replay-config.v1.json
.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/checkpoints/REANCHOR_MODEL_FREE_REPLAY.md   # 政策文档，引用不改写
.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/source-input/                               # 冻结 DOCX blob
runs/protocol_control_replay/d001-phase-ii-20260831/                                                                          # 暂停 live 回放状态（含 DB 副本）
data_v2/enrollment-review-v2.sqlite3（含 -wal/-shm）                                                                          # 权威库：D001 任务与 19 个批次检查点
runs/protocol_control_smoke/**（历史运行记录）
CHECKPOINT_20260829 / 20260831 两份 / 20260901 任务级检查点文档
tests/v2/protocols/test_protocol_replay_harness.py:488-513 中 v1 哈希钉扎（只可扩展钉 v2，不得删除）
提示词/合同的临床规则语义正文（本任务只登记、不修改）
D001/MG-K10-SAR 原始语料（工作区内外的只读验收锚点）
```

## 工件与证据

本工作项为只读分析，无新工件。证据落点：
- 漂移实测：`tests/v2/protocols/test_protocol_replay_harness.py.py::test_d001_p803_p805_read_only_checkpoint_rebuilds` 失败输出（actual `df0d573a…` vs v2 `115812e7…`）。
- 版本常量与哈希机制：`app/agents/protocol_control_deconstructor.py:107-115, 1786-1821`；运行记录写入点 `app/services/protocol_control_execution.py:1176, 1469`。
- 重放链与版本记录缺口：`app/protocols/protocol_replay_harness.py:86-88, 445-534, 596-790`；CLI `scripts/run_protocol_replay_harness.py`。
- 检查点内容：`checkpoints/*.json` 全文已在上面引用（哈希、身份、单元数、工具链钉扎、notes）。
- 既有裁定链：`implement.md:1409-1411`；`journal-1.md:2104, 2113`；三份历史 worker/评审报告。

## 命令与观察

- `grep`/`find`/`sed` 只读检索（文件与行号均在上文）；`git log` 显示 `app/agents/protocol_control_deconstructor.py` 为**未跟踪文件**（本 worktree 有 1212 个未跟踪路径），提示词版本史无法从 git 重建，版本史证据以检查点 notes + journal + 归档执行报告为准。
- `ls`/`sha` 核对冻结 blob 存在且大小 405,567 字节。
- `.venv/bin/python --version` → 3.12.13；pydantic 2.13.3；`docx_structure.PARSER_VERSION` = 1.4.0（工具链与 v1/v2 钉扎一致）。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/v2/protocols/test_protocol_replay_harness.py::test_d001_p803_p805_read_only_checkpoint_rebuilds tests/v2/protocols/test_protocol_replay_harness.py::test_previous_d001_replay_checkpoint_remains_immutable_history -p no:cacheprovider -q --no-header` → `1 failed, 1 passed`，失败即上述 `prompt_sha256` 漂移；无工作区写入。

## 阻塞项或缺失环境

无阻塞。环境完整（`.venv` 可用、测试可运行、全部冻结工件可读）。

不确定性（已标注）：v2 冻结后至 08-31 09:43 之间提示词正文的具体修改条目无法逐条归因（模块无 git 历史）；对本任务而言只需"当前正文即登记对象"，不影响结论。

## 重跑请求或下一步

- worker_02 可直接依据本报告实现：升 `CONTROL_AGENT_PROMPT_VERSION` 至新 id（建议 v1.6，待 Codex 定夺）、在 `replay-summary.json` 增加版本记录字段（保持 schema 字面量 `/v1` 不变）、按 REANCHOR 流程双构建产出 checkpoint v3、将 `test_protocol_replay_harness.py:454` 重建目标切到 v3 并在 `:488` 不可变历史测试中**追加**钉死 v2 的 `115812e7…`。
- 需 Codex 裁定的一个精确问题：新提示词版本 id 取 `v1.6`（微升先例）还是 `v2.0`（里程碑式切档）？两者对重放指纹无影响（版本串不进提示词正文），仅影响运行记录与可读性。
- worker_03 复核时可用同一单测命令验证"旧不可变测试通过 + 重建测试指向新检查点通过"作为回归恢复的判据。
