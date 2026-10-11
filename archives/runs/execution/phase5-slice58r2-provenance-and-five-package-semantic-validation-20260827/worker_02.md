# Execution Output: phase5-slice58r2-provenance-and-five-package-semantic-validation-20260827 - worker_02

## Boundary And Context Check

- 已读取指定 execution context 与 plan。
- 本工作项限定为只读核查运行配置、入口、健康/模型身份验证及测量字段。
- 未修改代码、源文件、生产路径或报告文件；未调用模型、`/chat/completions` 或语义 Provider。
- 未读取 `.env`、外部 oMLX 配置、生产目录或其他 worker 报告。
- 未改变 `claims_complete=false`。

## Work Performed

1. 核查期别语义模型配置与实际 transport 参数。
2. 核查限包脚本的 package ordinal 映射、derived plan、provenance 与 checkpoint 顺序。
3. 核查健康检查和精确模型身份验证方式。
4. 核查产品及历史运行证据中的速度、调用、解析和质量字段。
5. 输出无模型调用的五包构建前置命令及后续真实执行命令模板。

主要发现：

- 当前期别语义模型默认继承 `DECONSTRUCT_*` 配置：
  - backend：`omlx`
  - model：`Qwen3.8-27B-oQ8e-fp16-mtp`
  - reasoning：`default`
  - 配置层 `max_tokens`：`60000`
- 本地 oMLX transport 会将有效输出上限裁剪为 `8192`，因此实际执行应同时记录 configured/effective 两个值。
- 本地默认 timeout 为 `600s`，OpenAI client `max_retries=0`；Runner 默认 transport retry 为 `1`、schema repair 为 `2`。
- 本地调用默认 temperature 为 `0.0`，使用严格 `phase_applicability_agent_wire_v2` JSON Schema。
- `GET /api/health` 只返回 oMLX/DeepSeek 布尔可达性，不能证明具体模型身份。应额外执行 `GET /v1/models` 并核对 model ID。
- 当前 checkpoint 的 `transport_identity` 未包含 temperature、timeout、client max_retries、response format 及 configured max token，存在参数改变但 resume identity 不变的持久化可观测性缺口；本 worker 未修改。
- 限包脚本当前已具备：先校验同 run-id provenance，再 `prepare()`，从而在冲突映射下阻止重建不同 checkpoint；本 worker 未执行该路径。

## Artifacts And Evidence

配置与入口：

- `app/config.py:20-38,70-86`
- `app/agents/phase_applicability_transport.py:63-80,129-218,248-273`
- `app/services/phase_applicability_execution.py:109-136,451-461`
- `scripts/run_phase_applicability_acceptance.py:1-17,102-173,176-293,322-435`

健康和身份：

- `app/router/health.py:15-32`
- `app/llm/client.py:62-68,460-480`
- `scripts/start_enrollment_review.command:34-44,90-112`

协议与质量字段：

- `app/agents/phase_applicability.py:1669-1690,1697-1809`
- `tests/v2/protocols/test_phase_applicability_live_execution.py:171-215`
- `tests/v2/protocols/test_deconstruction_transport_config.py:116-175`

当前 D001 前置证据：

- `artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/coverage_manifest.json`
  - `claims_full_coverage=false`
  - `protocol_version_id=D001-02-002:v1.0:phase-ii`
- `artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/prepare_summary.json`
  - coverage units：1846
  - expected agent units：1303
  - package count：138
  - status：`planned`
- `artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/verification-results.json`
  - `claims_complete=false`
  - semantic Provider calls：`0`
  - target package ordinals：67、78、79、80、111
  - package input reload checks：pass
  - semantic execution：not run by scope

历史运行测量模板：

- `artifacts/phase5-slice58l-d001-six-package-semantic-baseline-20260826/qwen38-baseline-worker_02-real-run-20260826/run-metadata.json`
- `.../package-0070/metrics.json`

历史 metrics 中可复用的字段包括：

- execution：`attempt_count`、`elapsed_seconds`、`first_round_elapsed_seconds`、`repair_elapsed_seconds`、`transport_retry_elapsed_seconds`、`output_chars_total`、`response_call_count`、`same_session_repair_observed`
- input：`context_packets`、`context_units`、`owned_units`、`prompt_chars`、`prompt_sha256`、`frozen_source_span_count`
- calls：调用类型、状态、耗时、prompt/output 字符数及 hash、session ID
- gate：deterministic input、output parse、formal resolution、manual clinical QC
- package identity：package ordinal、package ID、selection strata

这些是历史 acceptance harness 证据，不是当前产品 checkpoint 的完整字段。

## Commands And Observations

当前只读 HTTP 探针：

```sh
for endpoint in \
  http://127.0.0.1:8000/v1/models \
  http://127.0.0.1:8001/v1/models \
  http://127.0.0.1:8900/api/health \
  http://127.0.0.1:8901/api/health
do
  /usr/bin/curl --noproxy '*' -sS -D - \
    --connect-timeout 1 --max-time 3 "$endpoint"
done
```

四个 endpoint 均返回连接失败，curl exit code 为 `7`：

```text
Failed to connect to 127.0.0.1 ... Couldn't connect to server
```

最小无模型五包构建前置命令：

```sh
STATE_DIR="<fresh-isolated-state-dir>"
SUMMARY_PATH="$STATE_DIR/summary.json"

python3 scripts/run_phase_applicability_acceptance.py \
  --coverage-manifest artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/coverage_manifest.json \
  --plan artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/frozen_phase_plan.json \
  --package-ordinals 67,78,79,80,111 \
  --state-dir "$STATE_DIR" \
  --run-id d001-ii-phase-closure-20260827-slice58r2-5pkg \
  --build-only \
  --max-owned-units-per-batch 12 \
  --context-radius 1 \
  --summary "$SUMMARY_PATH"
```

该命令只生成隔离的 derived plan、checkpoint、package-selection provenance 和 summary，不调用模型。应随后确认：

```sh
jq '{
  run_id,
  status,
  batch_count,
  expected_agent_unit_count,
  transport_identity,
  input_scope_sha256,
  prompt_template_sha256
}' "$SUMMARY_PATH"

jq '{
  schema_version,
  run_id,
  selected_source_ordinals,
  source_plan_id,
  derived_plan_id,
  package_mappings
}' "$STATE_DIR/d001-ii-phase-closure-20260827-slice58r2-5pkg.package-selection-provenance.json"
```

模型身份验证命令模板；当前未执行成功，因为本地服务未启动：

```sh
OMLX_PHASE_URL="http://127.0.0.1:8000"

curl --noproxy '*' -fsS \
  --connect-timeout 2 --max-time 4 \
  "$OMLX_PHASE_URL/v1/models" |
python3 -c '
import json, sys
expected = "Qwen3.8-27B-oQ8e-fp16-mtp"
payload = json.load(sys.stdin)
rows = payload.get("data", [])
print(json.dumps(
    [{"id": row.get("id"), "owned_by": row.get("owned_by")} for row in rows],
    ensure_ascii=False,
))
assert any(
    row.get("id") == expected and row.get("owned_by") == "omlx"
    for row in rows
), f"expected oMLX model not found: {expected}"
'
```

后续真实执行参数模板，仅供 Codex 在 build-only、endpoint 和 model identity 均通过后使用；本 worker 未执行：

```sh
python3 scripts/run_phase_applicability_acceptance.py \
  --coverage-manifest artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/coverage_manifest.json \
  --plan artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/frozen_phase_plan.json \
  --package-ordinals 67,78,79,80,111 \
  --state-dir "<same-fresh-isolated-state-dir>" \
  --run-id d001-ii-phase-closure-20260827-slice58r2-5pkg \
  --backend omlx \
  --base-url "<verified-omlx-base-url>" \
  --model Qwen3.8-27B-oQ8e-fp16-mtp \
  --reasoning-effort default \
  --max-tokens 8192 \
  --temperature 0.0 \
  --max-transport-retries 1 \
  --max-schema-repairs 2 \
  --summary "<same-fresh-isolated-state-dir>/summary.json"
```

## Blockers Or Missing Environment

- 当前 worker 环境中 8000、8001、8900、8901 均无监听服务。
- 由于 delegated hard boundary，未读取用户主机外部 oMLX 配置，因此实际活动端口无法确认；代码 fallback 是 8000，历史 acceptance artifact 曾使用 8001。
- 当前产品 execution checkpoint 未记录完整速度字段；没有 provider usage token 字段，不能从 output 字符数可靠计算 tokens/s。
- 当前产品 run result 记录解析/失败/问题/拒绝单元等质量字段，但不包含独立临床质量评分；`manual_clinical_qc` 仍需独立执行。
- 当前 worktree 本来就存在大量其他改动；本 worker 未发出任何写入命令，不能将 `git status` 解释为全局清洁证明。

## Rerun Requests Or Next Step

1. 由 Codex/worker_01 完成或确认 checkpoint/provenance 修复后，在 fresh isolated state dir 执行上述 `--build-only` 命令。
2. 核验 derived plan 仅包含原始 67、78、79、80、111 五包，并确认 provenance 保存 source ordinal → derived ordinal/package ID 映射。
3. 启动或确认 oMLX 后，先执行 `/v1/models` 精确身份核验，再决定是否进行真实语义执行。
4. 真实执行时同时保存 configured/effective max tokens、model/backend/base URL、temperature、timeout、retry/repair 限额、prompt/input hashes、每次调用耗时、输出字符数/hash、attempt outcome、gate 状态和 aggregate elapsed。
5. 继续保持 `claims_complete=false`，不扩展到其他包、受试者或前端。
