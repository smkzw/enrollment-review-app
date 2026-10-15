# Codex Execution Plan: phase5-representative-subject-acceptance-harness-20260901

Objective: 为 Phase 5 建立最小、通用、可恢复的代表受试者验收路径：从只读原始受试者文件建立清洁隔离输入清单，复用现有 V2 证据处理、来源绑定视觉观察、真实 Evidence Normalizer、确定性门禁与 Patient Profile 投影，生成逐事件来源核对数据包。智谱独立视觉通道必须复用当前 OMP zhipu-coding-plan/glm-5.3-flash Coding Plan 接入合同；不得读取或写入凭据值，不得修改旧项目、旧缓存、旧 LLM 结果或暂停中的 D001 控制任务，不得写入 D001/SAR 项目特异临床规则。完成标准是最小实现、聚焦测试和父级可据此启动单一代表病例真实探针；本任务不宣称医学验收完成。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读检查员：核对现有 V2 上传、证据修订、事实规范化、Patient Profile 与独立视觉通道的真实入口；以文件形态选择 D001 II SA01025 和 MG-K10-SAR III 31001 作为异质锚点，给出最短清洁隔离运行路线、现有能力和最小缺口。禁止修改代码或临床源文件，禁止引用旧 OCR/LLM 结果作为新输入。 | `runs/execution/phase5-representative-subject-acceptance-harness-20260901/worker_01.md` |
| `worker_02` | 单一实现者：在不新增编排框架的前提下，补齐可复用的代表受试者验收清单/运行数据包能力及必要测试。输入必须是原始文件路径与内容哈希，输出必须显式记录隔离数据根、源只读指纹、运行权威、候选/发布/个例档案统计和逐事件来源核对项；不得硬编码疾病、药物、评分、日期或项目编号语义。优先复用现有服务/API；若现有能力已足够，仅补最薄的验收导出层。不要启动昂贵真实模型调用。 | `runs/execution/phase5-representative-subject-acceptance-harness-20260901/worker_02.md` |
| `worker_03` | 独立对抗审阅者：只读检查实现及相关合同，攻击旧缓存复用、源文件变更、跨受试者/跨节点污染、无事实却假成功、无来源定位却发布、视觉观察替代 OCR、项目特异硬编码和人为宣称医学通过等失败模式；提出可执行的阻断测试和接受边界。禁止修改文件。 | `runs/execution/phase5-representative-subject-acceptance-harness-20260901/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
