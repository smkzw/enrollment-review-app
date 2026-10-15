# Slice 4.0 oMLX OCR 门禁检查与探针记录（实测）

日期：2026-08-19  |  工作树：`phase4-evidence-ocr-v2`  |  脱敏合成样本、无安装

## 1. 共享 oMLX 工作负载门禁（已检查源码与运行时）

- 脚本：`/Users/smkzw/.codex/tools/omlx_workload_gate.py`（跨进程 SQLite/WAL 门禁）。
- 额度：OCR 8、翻译 8、总计 16；`run` 命令在租约内执行子命令，心跳续租、释放。
- 权威模型选择由门禁持有：`{"ocr": "GLM-OCR-bf16", "translation": "dawncr0w--Hy-MT2-30B-A3B-oQ8-MLX"}`（schema `omlx_gate_selection_v1`）。
- **调用方不得自行传模型**；门禁拒绝任何与权威选择不一致的模型覆盖。
- 租约机制实测通过：`run --kind ocr --owner phase4-evidence-ocr-v2 -- echo "gate-lease-ok"` 成功，结束后 active=0/queued=0，租约正常获取与释放。
- 门禁 DB：`/Users/smkzw/.codex/state/omlx_workload_gate.sqlite3`（chmod 600）。

## 2. 当前 OCR 适配器核对

- `app/llm/client.py::call_vision_ocr`：AsyncOpenAI 指向 `OMLX_BASE_URL=http://127.0.0.1:8000`（`app/config.py`），
  模型默认 `models--PaddlePaddle--PaddleOCR-VL-1.6`，`max_tokens=4096, temperature=0.1`，重试 ≤3。
- 现状：返回类型是 `str`，且对响应用正则删除 `<|LOC_数字|>` 再折叠空行（`app/llm/client.py:449-452`）；
  **原始响应不落盘、无布局 schema/parser/坐标**。这与 Phase 4「先保存 provider 原响应、再由版本化 parser 派生」的要求不符。
- 结论：现有适配器可作为 `OcrProvider` 文本识别后端的起点，但不能直接成为 V2 布局坐标真相。

## 3. 真实 gated OCR 探针

- 旧应用配置仍指向被其它桌面应用占用的 `127.0.0.1:8000`，属于配置真相漂移，不能据此误判“本机没有 oMLX”。
- 成功探针使用任务私有 `--base-path` 在 `127.0.0.1:8002` 启动隔离 oMLX，模型为共享门禁权威选择 `GLM-OCR-bf16`；探针结束后服务已停止。
- 复核时仍有独立服务监听 `127.0.0.1:8001`，但其 `/v1/models` 不包含 `GLM-OCR-bf16`，不能把它当作本次成功探针的复现端点；当前配置、服务模型目录和门禁选择仍需在后续适配器中统一。
- 同会话复核尝试直接复跑 `8001` 时，健康端点正常但 OCR 请求返回 HTTP 404；门禁 request_id=`12c9270bcb6540c18658910ce0682fc3` 已释放，失败复跑未覆盖原成功证据。
- 真实请求必须通过共享门禁执行：
  `omlx_workload_gate.py run --kind ocr --owner phase4-evidence-ocr-v2 -- <probe>`。
- 门禁 SQLite 记录与响应时间相符：owner=`phase4-evidence-ocr-v2`、kind=`ocr`、model=`GLM-OCR-bf16`、request_id=`b5c63d50e99949baa113536ec912269b`、创建时间
  `1787104668.8576288`，状态为 `released`。该次命令在一个租约内顺序执行两个请求，证明本次调用在门禁内完成，但不构成并发峰值验收。
- 样本：脱敏合成扫描 PDF 1 页、照片 1 页；均包含否定句“胸部X线检查未见异常”和日期“2026-04-02”。
- 结果：2/2 页规范化逐字回读一致，所有目标片段均找到；推理耗时分别为 1.621 秒、0.742 秒。
- 原始 provider 响应保存于 `slice4-real-omlx-probe.json`，包含严格 UTF-8 文本、Base64、响应 SHA-256、HTTP 状态、响应模型和完成原因；
  两页响应均只有文字，未发现 LOC token、bbox、coordinates 或其它显式数值坐标结构，故 `layout_coordinates_observed=false`。
- 模型身份边界：gate 的 `model=GLM-OCR-bf16` 是请求选择，响应 JSON 的 `model=GLM-OCR-bf16` 是 provider 自报；成功记录没有保留 8002 的 `/v1/models` 清单、启动参数或服务日志，不能把这两项当作独立的实际加载身份证明。
- 证据边界：该历史探针记录没有保存每次原始请求/页图的 SHA-256，也没有把 gate SQLite 记录与响应字节做密码学签名绑定；gate request_id/时间/释放状态是独立运行时交叉核对，不能替代正式适配器的请求工件审计。
  当前探针代码已为后续实测输出请求体哈希和页图哈希，但本记录不把这些未捕获字段追写成“实测证据”。

## 4. 采用/拒绝决策（已冻结）

- **原生 PDF 坐标路径（pdfplumber）：** 已由本 Slice 金标准实测通过（见 `slice4-goldset-coordinate-spike.md`），可直接采用。
- **扫描/照片文字路线（门禁选择为 GLM-OCR-bf16）：在本合成能力样本范围内作为 text-only fallback 采用。** 本轮门禁请求的原始响应 2/2 页逐字一致；这冻结的是文字路线选择和无坐标行为，
  不是独立证明实际加载模型身份、一般医学资料准确率或生产适配器已完成的声明。后续适配器必须保存 provider 原响应，再由版本化 parser 派生识别文字，
  不得像旧适配器一样先删 LOC token 后只返回字符串。
- **扫描/照片红框坐标路线：本阶段拒绝采用。** 真实响应没有机器可读坐标。此类证据只能降级为文本范围、页内摘录或页码，
  前端不得渲染红框；只有未来独立布局解析器达到 ≥90% 且全部区域页码/边界/文字覆盖验证通过后，才可另行启用。
- **PaddleOCR-VL：本阶段不采用、不作性能声明。** 当前共享门禁的权威 OCR 模型是 GLM-OCR；不能绕过门禁另选模型来制造
  布局能力结论。若未来门禁模型策略变更，必须重新执行同一金标准和坐标采用门槛。

## 5. 后续适配器约束

1. V2 OCR 适配器不得沿用 `8000 + PaddleOCR-VL` 的旧默认组合；应从统一运行时配置获取当前 oMLX 地址，并校验响应模型身份与
   共享门禁选择一致。地址发现与模型选择是两个不同职责，不得再次形成三套配置真相。
2. 保存请求/页图哈希、模型/解析器版本和原始响应字节及哈希后，才允许生成派生页文字；无真实坐标时必须显式记录降级原因。
3. OCR 并发统一由共享门禁控制，应用层不得再维护第二套互相冲突的并发上限。

## 6. 已固化的度量/门禁（本轮交付）

- 布局候选度量与真实绘制区域对照机制已实现并测试通过（`app/evidence/eval.py::evaluate_layout_candidates`）。
- 合成候选演示通过 ≥90%，但**不**代表布局模型已采用；采用与否以本探针结果为唯一依据。
