全部 20 个测试均已通过，且 `git status` 确认仅创建了两个授权文件。最终报告如下：

# 执行输出：medication-component-isolated-20260909 - worker_01

## 边界与上下文检查

- 运行路径：zcode / GLM-5.3-Flash，允许的最大思考时间；本次会话是在北京 `off_peak` 边界之后启动的，因此根据调度说明，使用当前的 `off_peak` 路线；无需回退。
- 仅在授权的工作区内操作。仅读取了初始读取集加上两个直接依赖项：`app/domain/page_timestamp.py`（确认 `normalize_scalar` 如何规范化日期值）和 `app/domain/publication.py` 的导入头部（确认测试导入无副作用）。没有网络调用、没有模型调用、没有凭据、没有原始临床文件。
- 没有修改任何 `app/` 文件、现有脚本、文档、配置或临床工件。`git status --porcelain` 显示恰好有两个新的未追踪文件，均为授权文件。
- 备注：在此 ZCode 测试框架中无法调用 `apply_patch` 二进制文件；我使用了测试框架的 Write/Edit 工具作为文件创建的等效工具，严格仅针对这两个新文件。未编写任何报告/同级进程文件。

## 已执行工作

创建了 `scripts/medication_component_experiment.py` —— 一个用于每个观察值药物成分验证的紧凑型纯 Pydantic 契约 + 提示词构建器 + 验证 + 比较（无 CLI，无持久化，无新依赖，无药物/项目别名）：

- 输入 `MedicationObservation`：一个读取者的一个观察值 —— `observation_id`，`raw_value`，`excerpt`，可选 `context`，以及 `SourcePageIdentity`（`page_artifact_id`，`source_document_version_id`，`page_number`，`page_image_sha256`，`clause_pack_sha256`），镜像了现有的页面对齐实验的标识元组。
- 输出 `MedicationComponentExtraction`：必需的 `drug_name`/`dose`/`frequency`/`route`/`time`；每个组件都需要显式的 `value` + `source_quote`（对于缺失组件均为 null，配对强制执行）；`time` 还需要 `role` ∈ `prescription_date | use_start | use_end | administration_date | unclear`（无 `encounter_date` 角色 —— 在架构级别拒绝该角色）。所有位置均为 `extra="forbid"`。
- `validate_extraction` / `validate_extraction_batch`：拒绝未知的观察 ID、重复的输入 ID 以及重复的输出 ID；要求引用必须是观察值**自身**的 `excerpt`/`raw_value` 的精确子串（仅上下文或借用的引用会被拒绝）；要求 `value` 必须是引用支持的文本（空格规范化包含，而不是释义）。仅绑定文本 —— 不是医疗范围或正确性。
- `build_component_prompt`：原生中文，简洁，仅携带一个观察值（绝不包含配对的读取者），负载和输出架构中包含明确的 `EXPERIMENT_VERSION = "medication-component/v1"`，提供了 JSON 架构。实际的模型调用/图像附件/编排按分配保留给 Codex 处理。
- `compare_component_outputs`：每个组件的确定性比较，无语义模型。`agree` 仅在两个绑定值均非空 + `normalize_scalar` 相等（值和单位元组，因此单位永远不会被丢弃）时；`time` 还需要相等的 `role`；任何一侧缺失 -> `missing`（从不借用）；其他任何情况 -> `conflict`；需要相同的源页面标识。所有结果携带 `product_acceptance: Literal[False]` 和 `source_qc_required: Literal[True]`（`BoundComponentExtraction` 上的冻结常量 —— 覆盖它们会在验证时失败）。

创建了 `tests/v2/scripts/test_medication_component_experiment.py` —— 20 个重点测试，仅使用合成数据，涵盖了所有必需的案例：匹配字段一致；单侧和双侧缺失的时间从未被借用；单位转换/丢弃冲突（`1g` vs `1000mg`, `100mg` vs `100`, `2片` vs `2`）；仅空格 `100mg`/`100 mg` 一致，同时保留单位字符串；批处理/单个中的重复和未知 ID；来自其他观察值和仅上下文的外来引用被拒绝；释义被拒绝；组件/子键必需（显式 null）；顶层、组件和观察值级别的额外字段被拒绝；值/引用/角色配对；时间角色差异 -> 冲突；提示词逐字保留输入且绝不查看其他读取者；批处理回显错误的实验版本被拒绝；输出在结构上永远不会被接受。

## 工件与证据

- `scripts/medication_component_experiment.py` (新建，约 230 行)
- `tests/v2/scripts/test_medication_component_experiment.py` (新建，20 个测试)

可调用 API（所有类型均为纯 Pydantic v2）：

```python
EXPERIMENT_VERSION = "medication-component/v1"
TimeRole = Literal["prescription_date", "use_start", "use_end", "administration_date", "unclear"]
class SourcePageIdentity(BaseModel)          # page_artifact_id, source_document_version_id, page_number, page_image_sha256, clause_pack_sha256
class MedicationObservation(BaseModel)       # observation_id, raw_value, excerpt, context: str|None, page
class MedicationComponent(BaseModel)         # value: str|None, source_quote: str|None (both required keys)
class MedicationTimeComponent(MedicationComponent)  # + role: TimeRole|None
class MedicationComponentExtraction(BaseModel)      # observation_id + 5 required components
class MedicationExtractionBatch(BaseModel)   # experiment_version: Literal["medication-component/v1"], items
class BoundComponentExtraction(BaseModel)    # frozen; product_acceptance=Literal[False], source_qc_required=Literal[True]

build_component_prompt(observation: MedicationObservation) -> list[dict[str, str]]
validate_extraction(extraction: MedicationComponentExtraction, observation: MedicationObservation) -> BoundComponentExtraction
validate_extraction_batch(batch: MedicationExtractionBatch, observations: list[MedicationObservation]) -> list[BoundComponentExtraction]
compare_component_outputs(left: BoundComponentExtraction, right: BoundComponentExtraction) -> dict
```

## 命令与观察

- `.venv/bin/pytest tests/v2/scripts/test_medication_component_experiment.py -q` -> **20 个通过**（这是本次任务允许运行的唯一检查）。
- 测试迭代观察：4 个初始失败是测试夹具错误，验证器正确捕获了这些错误（b-side 提取仍然带有 `obs-a` ID 或引用了 b 摘录中不存在的 `qd`/`口服` 的组件）—— 这些拒绝是绑定契约按预期工作的证据；已修复夹具，无需更改模块。

## 阻碍或缺失环境

无。所有必要的工具和依赖项（pydantic 2.13.3, pytest 9.0.2, venv）均已存在。

## 重跑请求或下一步

无需重跑。对于 Codex 在孤立的运行编排中需要注意的事项：

1. **明确保留的限制（根据合同说明）：** 子串绑定仅证明文本来自此观察值自身的摘录；摘录内相邻药物文本仍需要源 QC —— 子串匹配本身绝不能证明其归属于该药物。`validate_extraction` 验证文本绑定，而不是医疗正确性、范围或归属权。
2. 空格/标点符号规范化的包含偶尔可能会拒绝一个合理的非连续值（保守的拒绝；被拒绝的项目将保持未接受状态）。
3. 比较不携带读取者身份；将哪个绑定提取配对（每个读取者 lane 的一个）由编排器决定。比较两个具有相同观察 ID 的相同绑定提取是允许的，并且会轻易达成一致。
4. `normalize_scalar` 会规范化日期格式（例如 `2025年3月2日` ≡ `2025-03-02`）并在比较时统一全角/半角标点符号；无法解析的日期垃圾数据将回退到文本比较，而不会崩溃。
5. 实际模型、图像附件、孤立的运行编排以及任何扩展评估仍然属于 Codex；此处没有任何内容连接到产品病史，也没有任何东西被呈现为已接受的临床事实。
