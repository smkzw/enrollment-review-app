# Codex Main-Venue Plan: phase5-slice61aq-native-pdf-structure-entry-audit-20260829

Date: 2026-08-29
Objective: 只读独立审查 Phase 5.8d 原生文本 PDF 方案结构入口。核查：一、原始 PDF 字节与来源哈希身份是否保持；二、页码、文本区间与坐标框定位是否可验证且不制造伪精确；三、扫描件、加密、损坏及文本不足 PDF 是否失效关闭；四、DOCX 冻结序列化和 D001 指纹是否保持兼容；五、真实 120 页 MG-K10-SAR PDF 的重复确定性验证能否支持“原生文本 PDF 入口已工程接受”的有限结论。必须明确区分入口能力与标题/表格语义恢复质量；后者尚未达到 DOCX 等价。仅审阅，不修改文件，不运行临床模型，不发布控制点。输出具体文件/测试证据、阻断问题、非阻断后续项和接受/拒绝结论。

## Task Decomposition

1. 独立核对 PDF 原始字节、哈希、页号、文本区间和坐标框合同。
2. 核对扫描件、加密、损坏、零页及部分页无文本层的失效关闭。
3. 核对 DOCX 冻结序列化与 D001 回放指纹兼容。
4. 核对真实 120 页 SAR V2.1 PDF 的两次确定性记录。
5. 明确本轮只验收原生文字 PDF 入口，不验收标题、表格和多栏阅读顺序与 DOCX 等价。

## Source Packet

TODO

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `general_single_object` | `codebuddy-cli` | `deepseek-v4-flash` | `runs/conference/phase5-slice61aq-native-pdf-structure-entry-audit-20260829/general_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

- `general_single_object` 使用 CodeBuddy / DeepSeek V4 Flash max 完成一次同会话只读审查，用时 415.610 秒。
- 未触发备选路线，未采用迟到输出。
- 审查提出的两项证据阻断已由 Codex 补齐；不需要重复派发第二个独立角色。

## Codex Verification Checklist

- [x] 持久化 D001 指纹回归与 PDF 失效关闭测试：`12 passed`。
- [x] 持久化真实 SAR V2.1 PDF 两次验证 JSON 和标准输出。
- [x] 后端全量：`2977 passed, 1 skipped, 139 warnings, 2 subtests passed`。
- [x] `git diff --check` 和验证 JSON 解析通过。
- [x] 没有调用临床 LLM/VLM，没有发布控制点。
- [ ] PDF 标题/表格/多栏版面恢复和空白页与扫描页分流属于下一质量切片。
