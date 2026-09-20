# Execution Output: phase5-slice58l-d001-six-package-semantic-baseline-20260826 - worker_02

## Boundary And Context Check

已读取指定 execution context 与 plan。仅处理六个冻结包：

`59、63、69、70、73、79`

未运行其余 131 包，未进入受试者审核或视觉测试，未修改临床源文件或生产代码。

## Work Performed

使用现有产品参数顺序真实调用六包：

- Backend：`omlx`
- Model：`Qwen3.8-27B-oQ8e-fp16-mtp`
- Base URL：`http://127.0.0.1:8001`
- Reasoning effort：`default`
- Temperature：`0.0`
- 配置输出上限：`60000`
- oMLX 实际上限：`8192`
- Transport retries：`1`
- Schema repairs：`2`
- 未使用 fallback，未预先调参。

六包均完成两次传输尝试，但本地 socket 被执行环境拒绝，未获得模型输出。

## Artifacts And Evidence

权威执行证据：

`artifacts/phase5-slice58l-d001-six-package-semantic-baseline-20260826/qwen38-baseline-worker_02-real-run-20260826/`

包含：

- `summary.json`
- `run-metadata.final.json`
- 每包 `metrics.json`
- 每包 `runner-result.json`
- 每包 `conversation-history.json`

逐包结果：

| 包 | 输入 prompt 字符 | owned/context | 首轮耗时 | 传输重试耗时 | 修复耗时 | 输出字符 | 结果 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 59 | 26,341 | 12/39 | 0.196388s | 0.002210s | 未发生 | 0 | 需要核对 |
| 63 | 23,216 | 6/37 | 0.001732s | 0.001517s | 未发生 | 0 | 需要核对 |
| 69 | 33,308 | 11/52 | 0.001527s | 0.001527s | 未发生 | 0 | 需要核对 |
| 70 | 29,538 | 12/41 | 0.001517s | 0.001809s | 未发生 | 0 | 需要核对 |
| 73 | 74,781 | 9/169 | 0.001863s | 0.001707s | 未发生 | 0 | 需要核对 |
| 79 | 26,818 | 11/40 | 0.001593s | 0.002185s | 未发生 | 0 | 需要核对 |

汇总：

- Prompt 总规模：`214,002` 字符
- 总耗时：`0.223063s`
- 传输尝试：`12`
- 传输错误：`12`
- 模型回包：`0`
- 同会话修复：`0`
- 解析通过：`0/6`

六包 prompt 字符数与 SHA-256 均通过冻结输入核验；协议源哈希均为：

`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`

## Commands And Observations

执行了：

- 逐包 prompt 构建、字符数与 SHA-256 核验：六包全部 `PASS`
- 配置探针：确认实际模型、backend、端口和输出参数
- `lsof`：观察到 oMLX 进程监听 `127.0.0.1:8001`
- `curl`/Python socket 只读探测：当前执行环境连接本机端口失败
- 逐包 `PhaseApplicabilityAgentRunner` 真实调用：六包均返回 `APIConnectionError: Connection error.`
- 六包范围、身份、门禁和错误一致性复核：全部 `PASS`

门禁状态：

- 冻结输入门禁：通过
- 模型输出解析门禁：未到达
- 正式期别语义门禁：未到达
- 人工临床 QC：未开始

每包均生成两个 transport session ID；由于首轮没有获得响应，未进入 `continue_session` 修复。runner 返回的 `transport-failed-2` 是失败汇总身份，实际 transport session ID 保存在各包 `metrics.json`。

## Blockers Or Missing Environment

共享根因是执行环境禁止访问本机 loopback socket：

```text
PermissionError: [Errno 1] Operation not permitted
```

oMLX 进程存在，但当前 worker 无法访问 `127.0.0.1:8001`。因此本轮耗时是连接失败耗时，不是模型推理耗时；不能据此评价 Qwen 质量或速度。

第一次遥测脚本在第 59 包调用后发生我方变量引用错误，未写入结果；该目录不作为权威证据。修正后的完整六包结果位于 `qwen38-baseline-worker_02-real-run-20260826`。

## Rerun Requests Or Next Step

请在允许访问本机 oMLX loopback 的宿主执行环境中，使用相同六个输入、模型和参数重跑；仅重跑六包，不启动其余 131 包。当前证据保留了输入身份、prompt hash、传输参数、失败会话和门禁状态，可直接作为重跑基线。
