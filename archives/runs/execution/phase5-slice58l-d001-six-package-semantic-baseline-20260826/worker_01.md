# Execution Output: phase5-slice58l-d001-six-package-semantic-baseline-20260826 - worker_01

## Boundary And Context Check

本次仅执行 worker_01：核对冻结清单、v2 计划与执行服务，生成六包受控输入。

已读取并使用：

- execution context、Codex execution plan
- D001 II coverage manifest、v2 execution snapshot、unit-phase evidence view、closed matrix、freeze metadata
- phase applicability plan、Agent input/prompt builder、execution service contracts

未读取原始 DOCX、受试者资料或视觉工件；未调用模型；未运行其余 131 包；未修改临床源文件或生产路径。

## Work Performed

通过 `apply_patch` 新增：

`.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/build_six_package_baseline_input.py`

完成以下校验与生成：

- 当前计划确认是 v2：137 个冻结包、1298 个待处置结构单元，137 个批次均为 `pending`。
- 保留原始 package ordinal 与 package ID，未重新编号。
- 选择六个冻结代表包：59、63、69、70、73、79；排除 131 个冻结包。
- 复用既有 Agent input/prompt builder，并记录同会话修复参数。
- 发现证据视图的 `referenced_*` 是矩阵引用子集，不是完整包成员；工件同时保存引用子集与完整冻结包，未错误要求二者相等。
- 明确聚合文件仅作控制索引/审计记录，模型调用必须逐包进行。

## Artifacts And Evidence

输出目录：

`artifacts/phase5-slice58l-d001-six-package-semantic-baseline-20260826/`

包含：

- `controlled-input.json`
- `controlled-input.sha256`
- 六个 `package-xxxx-agent-input.json`

| 序号 | package_id | 分层 | 完整 owned/context | prompt 字符数 |
|---:|---|---|---:|---:|
| 59 | `pap-abce70bf2da564416cbe046f` | opposite_phase_reference | 12 / 39 | 26,341 |
| 63 | `pap-e1c89d26f6d3b56819967f29` | validity_retest | 6 / 37 | 23,216 |
| 69 | `pap-e2ecad607cf61c1757ebc571` | shared_unknown_leaf | 11 / 52 | 33,308 |
| 70 | `pap-62c6bf0a59bef3060745c0b3` | table_5 | 12 / 41 | 29,538 |
| 73 | `pap-87a010ad5cadad903caefb83` | explicit_phase_ii_flow；post_dose_contamination | 9 / 169 | 74,781 |
| 79 | `pap-d6a1c7d3d06a1c9d18281cda` | tuberculosis_pregnancy | 11 / 40 | 26,818 |

范围计数：

- owned：61
- context：378
- 唯一结构单元：235
- 聚合 prompt：214,002 字符

哈希证据：

- controlled input SHA：`f93a6a773524ec1228ff5e335efdc882d2c672f14e1741238ccf5ecec7ab0d77`
- `controlled-input.json` 文件 SHA：`ad5024ec4e911fd79845784e2d2eea55c4fe9c77c118ce5b893f6a355f4612a7`
- 当前 v2 plan ID：`papl-45fde1ba5b326315737bda77`
- 当前 v2 plan canonical SHA：`af34e9378242ad054b9b7d9a10bef9703c19306f54f2165619baae4897fff733`
- protocol document SHA：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`

聚合工件记录：

- `provider_call_scope`: `exactly_six_listed_packages`
- `provider_payload_mode`: `one_package_file_per_call`
- `same_session_repair`: `true`
- `max_transport_retries`: 1
- `max_schema_repairs`: 2
- `aggregate_file_must_not_be_submitted_to_runner`: `true`

## Commands And Observations

执行：

```text
./.venv/bin/python .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/build_six_package_baseline_input.py
```

结果：成功生成六个逐包输入。

独立验证结果：

- 两次内存构建结果完全一致：`deterministic_payload: PASS`
- 聚合 canonical hash 重算：`PASS`
- 六个逐包文件与聚合记录一致：`PASS`
- 六个逐包输入均低于 240,000 字符：`PASS`
- 五个源工件记录哈希与当前文件一致：`PASS`

源工件当前哈希：

```text
coverage_manifest              b9fae80301e7947e259e2be22a31b5baa0e6de8a26b53afae9dfb68688577329
prepared_v2_execution_snapshot 948a43e21e044b8912635f32ca744a490a4576b5b3967f608699940ab2b4775d
unit_phase_evidence_view       57500f020c516c1636a8f32decbff283a5f2e27fc5903c388fb39dfd1d0025dd
closed_matrix                  04850a2537999a2c563930e776b211d895d61d566dab5826ffc2921b7f94a6ba
freeze_metadata                51684f391654a17a3bb9a6fa0c62fd97cd9f1ef7935ea0465460573825651cd6
```

观察到：

- `app.services.phase_applicability_execution` 的 generic `execute()` 会迭代完整 137 个批次，不能直接把完整 state 交给六包基线执行。
- 聚合 JSON 约 962,803 字符，超过 runner 输入上限；六个逐包 JSON 均在限制内，因此已在工件中显式禁止提交聚合文件。
- prepared state prompt hash 为 `94d1d928f1b90f341c6234846f83ef574f61b86f384f59b7d428b3530d434028`；当前运行时 hash 为 `719c90ab3590f94c73c5259e9ce29310b232d59343ef65ebaee4b20377d934ec`，二者不一致。

## Blockers Or Missing Environment

环境无缺失，`.venv` 可正常运行。

当前不能宣称模型执行就绪，原因：

1. prepared state 与当前运行时 prompt contract 哈希不一致，工件已标记 `ready_for_model_execution: false`。
2. generic execution service 会运行完整 137 包，必须由后续执行者采用六包 allowlist 或逐包 Runner。

## Rerun Requests Or Next Step

请 Codex 确认并处理 prompt contract：

- 重建与当前 prompt 一致的 prepared state，或明确恢复旧 prompt contract；
- 之后重新运行生成器并复核哈希；
- worker_02 仅使用六个 `package-xxxx-agent-input.json`，逐包执行并保留同会话修复证据；
- 不要把 `controlled-input.json` 直接提交给 runner，也不要启动其余 131 包。

本报告不构成最终模型、临床、视觉或项目验收。
