# Worker 02 同会话返修：统一矩阵契约与控制点临床边界

你上一轮完成了 D001 II 期方案的官方入排和研究流程人工核对，但父级验收发现产物不能接受。请在同一会话内直接返修你拥有的两个产物：

- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-official-flow-controls.json`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-official-flow-controls.md`

## 根因与必须修正

1. 你另建了 `official_rows` / `flow_rows` 临时结构，没有使用 Worker 01 已完成的 `ProtocolControlMatrix`。这会绕过稳定身份、来源闭包、期别、逻辑、序列化和中文可见层校验。必须把 JSON 改成可由 `ProtocolControlMatrix.model_validate_json()` 直接加载的真实合同；不得再保留并行临时 schema。
2. 必须通过 `build_protocol_control_matrix_json()`、`render_protocol_control_matrix_markdown()` 和 `validate_protocol_control_matrix_serializations()` 生成及验收两个产物。可见 Markdown 不得出现 `body.p628`、`body.t5`、`FLOW-001`、`flow:`、`pcm-row-`、`pcm-src-`、`stage:`、`proc-`、`pctrl-`、英文枚举值、字段名或其他程序内部身份。来源定位可以保留在 JSON 和 Markdown 注释中，但面向医学监查人员的正文只能使用中文自然语言、官方 IN/EX 编号和“流程必做 01”一类展示标签。
3. 官方入排必须保持方案原始父级编号完全一致：IN-01 至 IN-06、EX-01 至 EX-30，共 36 个官方父级矩阵行。复杂逻辑拆成同一父级行内的条件原子、义务与 DNF；不得发明官方子编号或增加官方条目数。
4. 研究流程表不能以“表格中出现过”作为纳入入排控制矩阵的充分条件。请逐项回到方案原文，重新区分：
   - 对进入下一入排节点、随机或首次给药构成前置条件的必做检查、评估、记录或结果要求：纳入。
   - 明确为建议、尽量、自愿的项目（例如自愿前提下建议尽量获取皮损照片）：不得作为阻断性“流程必做项”；若为了审计保留，只能以非阻断、非缺失判定的说明表达，不能进入当前要求为必做项的矩阵行。
   - 纯研究性采样、探索性检测（例如 IL-17A 采血），若方案未将其设为入排、随机或首次给药前置条件：不纳入入排控制矩阵。
   - 给药、疗效观察等治疗执行：不纳入。
   - D1 项目只有在明确要求随机/首次给药前完成且影响能否继续时才纳入，并准确写明锚点；不能把“D1 发生”自动解释为入排要求。
   不得为了维持上一轮“50 条”而保留不适格项目；数量必须服从临床含义和来源证据。
5. 不得添加方案未明确支持的工作流解释，例如把后续退出处理、一般性提醒写成当前节点判定要求。每项 `required_action_zh`、`attainment_criteria_zh`、`prohibition_zh`、节点角色、时间锚点和最低证据都必须能回指直接来源；方案没有规定某类要求时使用合同允许的空值，不要编造占位要求。
6. 使用 D001 真实方案版本、文档 SHA、冻结快照和覆盖清单身份。官方/流程矩阵当前尚未合并跨章节控制，`claims_complete` 必须为 `false`。
7. 重新构建只读 D001 `ProtocolSectionCoverageManifest` 或使用现有确定性构建链，在内存中执行 `validate_protocol_control_matrix()`。如正式 `required_procedure_catalog` 仍因 DOCX 缺少 ALIGNED TEXT_RANGE/PAGE_ONLY 定位而无法建立，应保留为真实阻断说明，但不能因此绕过矩阵合同。矩阵仍须通过冻结 manifest 的来源单元与 source span 闭包。
8. `required_procedure_catalog_item_id` 不得使用 `REQ-01` 等保留/伪造编号。若正式目录身份尚不可用，必须使用从冻结结构来源确定性派生、不会伪装为已发布目录项的稳定内部身份，并保持 `claims_complete=false`；在可见 Markdown 中隐藏该身份。
9. 期别结论必须由来源范围支持。共享条款可以标记跨期共享，但选定 II 期后面向用户的正文只呈现其在 II 期的要求，不反复出现“仅 II 期/与 III 期相同”等噪声。
10. 保持 D001 原始 DOCX 严格只读并在报告中复核 SHA-256、大小和 mtime_ns 未变化。LibreOffice 已知失败无需重试；不要用失败渲染制造页码。

## 验收证据

- `ProtocolControlMatrix.model_validate_json()` 成功。
- `validate_protocol_control_matrix()` 对冻结覆盖清单来源闭包成功；任何权威目录未闭合处明确阻断且不宣称完整。
- `validate_protocol_control_matrix_serializations()` 成功。
- 官方父级行严格 6 IN + 30 EX。
- 流程行逐项给出纳入/排除的临床理由；可在运行报告中列出排除项，不要把内部日志写入面向用户 Markdown。
- focused tests 通过；不得修改 Worker 01 合同/校验器，也不得修改你未获授权的应用文件。

完成后在本次同会话输出中简要列出：实际官方行数、实际流程控制行数、被排除的建议/研究采样/治疗执行项目、合同与序列化验证结果、仍存在的真实定位阻断、原文件指纹。
