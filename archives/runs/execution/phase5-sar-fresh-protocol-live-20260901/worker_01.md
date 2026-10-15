# Execution Output: phase5-sar-fresh-protocol-live-20260901 - worker_01

## Boundary And Context Check

- 严格执行只读核对；未启动模型、未创建方案作业、未调用 POST、未修改应用源代码、清单、临床文件或数据库。
- 未读取旧 `runtime-data/sar31001` 数据库，也未读取或恢复 D001 第 20 包。
- 仅使用声明的 fresh runtime、哈希清单、V2 启动代码、路由配置和任务检查点。
- 未创建或修改 runner 管理的报告文件。

## Work Performed

1. 核对全新运行根目录、marker、runtime identity 和数据库身份。
2. 使用正式入口执行 fresh runtime 只读门禁。
3. 复验协议 DOCX 与 31001 受试者资料清单的哈希和副本状态。
4. 核对 SQLite 版本门禁及 V2 数据根路径解析。
5. 核对 V2 启动命令、当前专用端口和实际监听进程。
6. 核对复杂方案语义路由顺序及当前环境中的 GLM 可用性。
7. 形成启动前、创建作业前和污染阻断清单。

## Artifacts And Evidence

### Fresh runtime identity

`artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/` 初始仅包含：

- `.phase5_fresh_acceptance`
- `runtime-identity.json`
- `backups/`
- `blobs/`

`runtime-identity.json` 声明：

- schema：`phase5.fresh_runtime.v1`
- 数据库路径：`.../sar31001-fresh/enrollment-review-v2.sqlite3`
- `database_must_be_absent_until_service_start: true`
- `ENROLLMENT_V2_DATA_DIR` 指向 `sar31001-fresh`
- 禁止复用 3 个旧 job ID：
  - `1653540a54c747e4bc60d94ae65b0b18`
  - `3259ab5f070447c3938ff2de5f45c9cd`
  - `384a7b3b802d46009e039c81ea7f7cc0`
- `old_failed_database_reuse: forbidden`
- `old_job_id_reuse: forbidden`
- `old_model_config_reuse: forbidden`
- `immutable_isolation_inputs_only: true`

### Input manifest

协议清单：

- 文件：`4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx`
- SHA-256：`075c93b45414dcb4bb33ef1cf623d295a9d8f029d7560ca484a0c0267c4fdabd`
- 大小：`418455` bytes
- `source_immutability.verified: true`
- `copy_verification.verified: true`
- `run_artifact_files: 0`
- 清单 label：`MG-K10-SAR-III-PROTOCOL-V2.1-20260901`

31001 清单包含 5 份 PDF，全部副本和源不可变复验通过：

| 相对路径 | SHA-256 | 大小 |
|---|---|---:|
| `2.筛选-基线病历/31001-病历.pdf` | `0c8e4f54f2cd4ea1f9d6309c9a7ce77e3304f39028c2ebe7efc0fe7f41341d0b` | 1,944,719 |
| `4.筛选-基线检验报告单/31001-基线血常规.pdf` | `3baf84ced110a071c8c41d3c42088906330c9445f325cb162ce0ac2487cd1d92` | 373,916 |
| `4.筛选-基线检验报告单/31001筛选期检查报告单.pdf` | `13d5eb1104b06f7fee7c58066081060e1f217a48bdea5aa1689e035174029b28` | 2,338,449 |
| `4.筛选-基线检验报告单/乙肝DNA-31001.pdf` | `b31d4536ac16a0e70bfbfb3180d7ed75cb61f27a3f50735842854caed355d194` | 233,682 |
| `5.入组审核过程及结果邮件、中心监查员-医学沟通记录或截图（如有）、Q&A记录（如有）/邮件.pdf` | `4ccfa3ca66a4d3fc36efa361fc86c0603bf6466c8dcd393a680d45b2e51d3b0c` | 1,271,901 |

此外清单明确排除 `.DS_Store`，不作为输入。

### Fresh runtime validation

正式入口：

```bash
/usr/bin/python3 tools/phase5_acceptance/fresh_runtime.py validate \
  --runtime-root artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh \
  --contract artifacts/phase5-acceptance/20260901/runtime-data/fresh-subject-runtime-contract.json \
  --manifest artifacts/phase5-acceptance/20260901/manifests/sar-protocol.json \
  --manifest artifacts/phase5-acceptance/20260901/manifests/sar-31001.json
```

第一次验证结果：

- `ok: true`
- fresh marker 存在
- 数据库不存在
- 协议清单重哈希：1
- 受试者清单重哈希：5
- 两份清单均 `verified: true`
- `run_artifact_files: 0`
- `job_ids: []`
- `business_state_counts: {}`
- `pollution_reasons: []`

在后续复查时，另一个进程已经启动 V2，数据库出现；再次验证仍为：

- `ok: true`
- `job_ids: []`
- 业务表全部为 0
- 仅有配置表：
  - `model_configs: 1`
  - `prompt_versions: 1`
- `pollution_reasons: []`

配置表在无 job 时按实现注释不构成旧业务状态。

### Database identity

只读 SQLite inventory 显示：

- `jobs`: 0
- `job_steps`: 0
- `job_events`: 0
- `job_checkpoints`: 0
- `projects`: 0
- `subjects`: 0
- `protocol_source_artifacts`: 0
- `protocol_extraction_snapshots`: 0
- `protocol_draft_revisions`: 0
- 所有临床事实、事件、暴露、Profile、Evidence Normalizer 业务表均为 0
- `model_configs`: 1
- `prompt_versions`: 1

因此当前 fresh 根仍无作业或临床业务状态。

## Commands And Observations

### SQLite runtime

使用系统解释器执行应用 CLI：

```bash
ENROLLMENT_V2_DATA_DIR=.../sar31001-fresh \
/usr/bin/python3 -m app.storage.cli check-runtime
```

结果失败：

```text
ModuleNotFoundError: No module named 'sqlalchemy'
```

这是解释器环境缺依赖，不是 SQLite 版本失败。

使用项目解释器执行：

```bash
ENROLLMENT_V2_DATA_DIR=.../sar31001-fresh \
.venv/bin/python -m app.storage.cli check-runtime
```

结果：

```text
SQLite 运行时版本满足 V2 持久化基线。
```

版本记录：

- Python：`3.12.13`
- SQLite：`3.53.4`
- 最低要求：`3.51.3`
- `.venv/bin/python` 指向 `/opt/homebrew/opt/python@3.12/bin/python3.12`

后续 V2 应用命令必须使用 `.venv/bin/python`；不要使用 `scripts/run_enrollment_review_service.sh` 中的 `/usr/bin/python3`。

### Data root resolution

```bash
ENROLLMENT_V2_DATA_DIR=.../sar31001-fresh \
.venv/bin/python -c 'from app.storage.config import resolve_data_paths; ...'
```

解析结果全部落在 fresh 根：

- root：`.../runtime-data/sar31001-fresh`
- db：`.../sar31001-fresh/enrollment-review-v2.sqlite3`
- backups：`.../sar31001-fresh/backups`
- blobs：`.../sar31001-fresh/blobs`
- migration lock：`.../sar31001-fresh/.migration.lock`

`app/storage/config.py` 的 `WriteBoundary` 会拒绝与旧 `projects/` 根重叠的 V2 数据根。

### Ports

`lsof -nP -iTCP -sTCP:LISTEN` 观察到：

- `127.0.0.1:8000`：已有 `app` 进程；受保护，不得停止或修改。
- `127.0.0.1:8001`：已有 `python3.1` 进程；受保护，不得停止或修改。
- `127.0.0.1:8900`：已有 `Python` 进程；受保护，不得停止或修改。
- `127.0.0.1:8910`：当前已有专用 V2 进程。
- `8911`–`8919`：本次端口检查中没有监听记录，可作为后续空闲候选，但不要并行启动第二个 V2。

当前专用进程：

```text
PID 15671
.../Python -m uvicorn app.api.v2.app:create_app --factory --host 127.0.0.1 --port 8910
```

`lsof -p 15671` 进一步确认其打开的 SQLite 文件均位于：

```text
.../runtime-data/sar31001-fresh/
```

HTTP 只读 smoke check：

```bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  http://127.0.0.1:8910/openapi.json
```

结果：

```text
200
```

### Correct service command

V2 工厂入口在 `app/api/v2/app.py` 文档中明确规定：

```bash
ENROLLMENT_V2_DATA_DIR="$FRESH_ROOT" \
DECONSTRUCT_ROUTE_MODE=graded \
DECONSTRUCT_ROUTE_COMPLEX= \
DECONSTRUCT_ROUTE_SHORT= \
DECONSTRUCT_GLM_PROVIDER=zhipu-coding-plan \
DECONSTRUCT_GLM_MODEL=glm-5.3-flash \
DECONSTRUCT_GLM_REASONING_EFFORT=high \
.venv/bin/python -m uvicorn app.api.v2.app:create_app \
  --factory \
  --host 127.0.0.1 \
  --port 891X \
  --loop asyncio
```

其中 `DECONSTRUCT_GLM_API_KEY` 必须由运行操作者以不打印的方式注入。

不要使用：

```bash
scripts/run_enrollment_review_service.sh
```

原因：

- 启动的是 `app.main:app`，不是 V2 工厂。
- 默认端口为 `8901`，并读取旧 `output/runtime_state/port`。
- 使用 `/usr/bin/python3`，本环境缺少 SQLAlchemy。
- 可能加载桌面启动器的旧运行状态。

`start_enrollment_review.command` 还会写入旧 `output/runtime_state`、扫描 `8901`–`8910`，并可能管理 MTPLX；不适合作为本次 fresh V2 专用启动器。

### Semantic route

当前代码默认复杂方案路由：

```text
zhipu-coding-plan:glm-5.3-flash:high
-> mtplx:mtplx-qwen38-27b-optimized-quality:medium
-> deepseek:deepseek-v4-flash:high
```

短提示路由：

```text
mtplx:mtplx-qwen38-27b-optimized-quality:medium
-> deepseek:deepseek-v4-flash:high
```

当前 shell 中执行的无模型路由快照为：

```text
route_mode: graded
complex_identities:
  zhipu-coding-plan:glm-5.3-flash:high
  mtplx:mtplx-qwen38-27b-optimized-quality:medium
  deepseek:deepseek-v4-flash:high
short_identities:
  mtplx:mtplx-qwen38-27b-optimized-quality:medium
  deepseek:deepseek-v4-flash:high
```

## Blockers Or Missing Environment

1. **GLM credential 未在本检查 shell 中出现。**

   `candidate_availability_error()` 对当前 shell 的 GLM 候选返回：

   ```text
   GLM 方案解构服务尚未配置（缺少 DECONSTRUCT_GLM_API_KEY）；
   已显式跳过该候选并继续尝试下一模型。
   ```

   因此当前检查环境不能证明 GLM 已可用。运行中的 PID 15671 可能使用了单独注入的环境变量，但未在不暴露 secret 的前提下确认。

   在创建 job 前，必须在**与 V2 进程相同的环境**中确认：

   - `DECONSTRUCT_ROUTE_MODE=graded`
   - `DECONSTRUCT_ROUTE_COMPLEX` 未覆盖默认复杂链
   - `DECONSTRUCT_GLM_PROVIDER=zhipu-coding-plan`
   - `DECONSTRUCT_GLM_MODEL=glm-5.3-flash`
   - `DECONSTRUCT_GLM_REASONING_EFFORT=high`
   - `DECONSTRUCT_GLM_API_KEY` 非空但不得打印

2. **系统 Python 不适合应用 CLI。**

   `/usr/bin/python3` 缺少 SQLAlchemy；不安装包、不改环境的最小处理是统一使用项目 `.venv/bin/python`。fresh runtime 独立脚本仍可用系统 Python，因为它只依赖标准库。

3. **当前 8910 已被专用 V2 占用。**

   不得再次启动第二个服务。不得停止 PID 15671，除非由拥有 runtime writer 权限的 worker 处理。

## Rerun Requests Or Next Step

### 可执行前置检查

服务启动前：

```bash
FRESH_ROOT="$PWD/artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh"
CONTRACT="$PWD/artifacts/phase5-acceptance/20260901/runtime-data/fresh-subject-runtime-contract.json"
PROTOCOL_MANIFEST="$PWD/artifacts/phase5-acceptance/20260901/manifests/sar-protocol.json"
SUBJECT_MANIFEST="$PWD/artifacts/phase5-acceptance/20260901/manifests/sar-31001.json"

/usr/bin/python3 tools/phase5_acceptance/fresh_runtime.py validate \
  --runtime-root "$FRESH_ROOT" \
  --contract "$CONTRACT" \
  --manifest "$PROTOCOL_MANIFEST" \
  --manifest "$SUBJECT_MANIFEST"

FRESH_ROOT="$FRESH_ROOT" \
.venv/bin/python -m app.storage.cli check-runtime
```

创建作业前必须再次运行同一 `fresh_runtime.py validate`。若数据库中出现 job、业务表、终态 job、旧 job ID 或非允许的模型身份，立即停止。

### 作业创建要求

只使用已验证副本：

```text
.../isolated-inputs/sar/protocol/4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx
```

首次方案解构接口：

```text
POST /api/v2/protocol/deconstructions
```

要求：

- 使用唯一新 `idempotency_key`。
- `file` 使用上述 DOCX 副本。
- 不提供 `project_id`，进入 `first_deconstruction`。
- 不使用 `/from-form`。
- 不引用旧 job ID。
- 不读取或上传原始 source root 文件。
- 不在本 worker 中执行 POST。

创建后应核对：

1. 返回 job ID 不在 forbidden job IDs 中。
2. job 位于 `sar31001-fresh` 数据库。
3. route audit 位于 fresh 根 `blobs/` 下。
4. audit contract 为 `protocol-semantic-route-audit/v1`。
5. 复杂任务 route attempt 1 为：
   `zhipu-coding-plan / glm-5.3-flash / high`。
6. 任意 fallback 必须是新的完整尝试，并记录 terminal reason、session、耗时和结果。
7. 未出现旧 job、旧数据库、D001 第 20 包或项目特异规则引用。
