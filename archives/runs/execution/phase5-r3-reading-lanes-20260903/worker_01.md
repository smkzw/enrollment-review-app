# 执行输出：phase5-r3-reading-lanes-20260903 - worker_01

## 边界与上下文检查

- 工作目录绑定为 `phase5-clinical-facts-profile` worktree，全程只读审计，未修改任何文件，未触碰临床数据、`projects/`、`data_v2/`、`archives/` 原始资料。
- 已读初始指定文件：`context/phase5-r3-reading-lanes-20260903_execution_context.md`、`plans/codex_execution_phase5-r3-reading-lanes-20260903.md`。本worker只承担工作项1（只读审计+最小修订范围），工作项2/3不越界。
- 审计源：设计书 `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`、实施计划 `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`、`.env.example`、`app/config.py`、`app/llm/client.py`、`app/evidence/selective_vision_review.py`、`app/agents/evidence_normalizer.py`、`app/pipeline/ocr.py`、`.trellis/tasks/08-22-phase5-clinical-facts-profile/implement.md`、`docs/PROJECT_CONTEXT.md`、`docs/v2/phase0/DECISION_AND_REGRESSION_INDEX.md`、`tests/v2/agents/test_mtplx_semantic_route_regressions.py`、`tests/v2/agents/test_evidence_normalizer_transport_config.py`。

## 已执行工作

逐页核对设计书 §7.0/§7.2/§7.3/§7.4/§11/§12、实施计划 Phase 5.5 与统一验证矩阵、全部模型路由配置、V2 证据语义节点代码路径和既有回归测试，比对目标读道边界（GLM与MiniMax双主读；Qwen3.8-Flash-Next仅手写第三读、只能写handwriting；消除降级主读表述；建立回归门禁），产出下列最小修订范围。

**关键事实基线（观察，非推断）：**
- 双VLM逐页判读harness尚未实现：实施计划 `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md:15` 明示 Phase 5.5 工作项3–8未开始；app代码中无 main-A/main-B/handwriting-C 读道实现（仅 `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md:143` 定义了读道标识）。因此本次修订主体是文档与配置表述，代码门禁归 worker_02。
- 现行V2证据语义节点（Evidence Normalizer）默认路由 MTPLX：`app/config.py:287-293`（`EVIDENCE_NORMALIZER_PROVIDER=mtplx`、model=`mtplx-flash-next-optimized-speed`，即 Qwen3.8-Next-Flash）；`.trellis/.../implement.md:1440-1450` 记录 2026-09-03 31001 事实规范化正在该模型上执行（已受控暂停）。
- 遗 Legacy 审核链（`app/pipeline/reviewer.py`，`REVIEW_BACKEND=mtplx|omlx|deepseek`）按实施计划工程纠偏项5冻结只读；已验证 `app/api|services|evidence|agents` 无 import（`app/llm/client.py:166-173` 仅为 legacy 选择器）。
- MiniMax 现仅作可选远程 OCR 后端（`app/llm/client.py:132-160`；`app/pipeline/ocr.py:380-393` 大文件走 minimax）；main-B 规格所需的 `CMS_SMK_API_KEY`/cms-smk 端点在 `.env.example` 与 `app/config.py` 中**均不存在**。

## 产物与证据

### 最小修订范围（建议，Codex裁定后执行）

**A. 设计书 `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`（约12行、8处）**

| # | 位置 | 现状（冲突表述） | 最小修订 |
|---|---|---|---|
| A1 | L3 状态头 | "R3：…双 VLM 主链 … + 手写专项第三读 + **离线降级路**" | 删"+ 离线降级路"，改为双主读+手写第三读 |
| A2 | L83 节点基线 | "**本地降级路同样使用 Qwen3.8-Next-Flash，云端不可执行时替代任一主链模型**并把结果标记为'本地单源待云端复读'" | 整句删除，改写为：Qwen3.8-Next-Flash 仅 handwriting-C，只写手写批注字段，不替代主链；主读失败标记页失败待云端复读 |
| A3 | L302 §7.0 Page Reader 失败处理 | "内容过滤/配额错误换同模型备用端点或**进离线降级路**并标记" | 删"或进离线降级路"，保留"标记页失败、不得由另一模型代笔"（该句已存在且与新边界一致） |
| A4 | L350 §7.3 | "手写字段三源规则；**第三读/仲裁读**触发条件" | 改"手写第三读触发条件"，删仲裁读 |
| A5 | L364 交叉采信规则 | "标记单源候选，需人工确认**或第三仲裁读**" | 删"或第三仲裁读"，只留人工确认 |
| A6 | L365 整条 | "**单源候选的第三仲裁读：**…调用本地降级路模型（Qwen3.8-Next-Flash MTPLX）做仲裁读…" | 整条删除（或改为"单源候选只走人工确认，不调用第三模型"） |
| A7 | L368 main-A 失败模式 | "两类失败都不得静默丢页，**走降级路并标记**" | 改"标记页失败并待云端恢复后复读" |
| A8 | L370-371 模型接入规格 | L371 整条"**本地降级/仲裁 Qwen3.8-Next-Flash**…只做云端不可执行时的替代主链与单源仲裁读" | L371 整条删除；L370 handwriting-C 可加一句"不承担主读替代或仲裁"锁界 |
| A9 | L374 失败路由 | "仍失败**进离线降级路**并在页覆盖标记'**降级读**'，云端恢复后复读" | 改"仍失败在页覆盖标记主读缺席（含模型名与原因），云端恢复后复读并按对账规则替换" |
| A10 | L375 并发配额 | "当前**本地语义读统一使用** Qwen3.8-Next-Flash" | 改"本地语义读仅限手写第三读（handwriting-C）" |
| A11 | L584/589 §12 裁决记录 | "同一模型以独立调用作**本地降级主链与单源仲裁读**"；"内容过滤走备用端点/**降级路**并标记" | 见下方开放决定D3（就地改 vs 追加带日期的收窄裁决条目） |
| A12 | L595 不采纳清单 | "（只在**单源候选与手写字段**做条件第三读）" | 改"（仅手写字段做条件第三读）" |

低优先一致性项：模型名 "Qwen3.8-Flash-Next"（L370、目标句）与 "Qwen3.8-Next-Flash"（L83/L371/L584；implement.md 2026-09-03 记录实际模型为后者）混用，建议统一为实际模型名。

**B. 实施计划 `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`（3处+1新增）**
- B1 L204："手写第三读及**本地降级/仲裁**统一改用 Qwen3.8-Next-Flash" → "手写第三读使用 Qwen3.8-Next-Flash（只写手写字段，不承担主读替代或仲裁）"。
- B2 L206（工作项4）："内容过滤备用端点/**降级路**" → "内容过滤备用端点；主读失败标记页失败待云端复读，无本地降级主读"。
- B3 L208（工作项4c）：标题"Handwriting Reader **与仲裁读**"及"**并承担本地单源仲裁读与离线降级**"删除；保留"各角色调用独立记账、可缺席且缺席可计数"。
- B4 Phase 5.5 退出门槛（L213-221）或统一验证矩阵"双VLM交叉"行（L322）追加读道门禁：路由审计证明 main-A/B 读道无 MTPLX/Qwen 身份、受试者读道无 DeepSeek、OCR 仅侧车、handwriting-C 输出仅 `handwriting[]`（Gate 拒绝其余字段写入）、读道调用无 temperature 参数。

**C. 配置**
- C1（缺口，阻塞 Phase 5.5 接入）：main-B cms-smk 规格（设计书L369 `https://new-api.mediportal.com.cn/v1` + `CMS_SMK_API_KEY`）在 `.env.example`/`app/config.py` 均无对应键，需随读道合同新增并纳入凭据预检（实施计划L209已要求）。
- C2 `.env.example:28-32` MTPLX 段注释"入排审核、证据规范化、协议控制默认使用此服务"：追加一句"受试者逐页判读读道（main-A/B）不经此服务；MTPLX 仅手写第三读"，防止误读。
- C3 `.env.example:139`/`app/config.py:162`：`MINIMAX_BASE_URL=https://mimimax.cn/v1` 疑似拼写笔误（mimimax）；且 MiniMax 同时承担 OCR 后端与未来 main-B（不同端点/密钥），新增 main-B 键时应加注释隔离两个角色，防止 OCR 端点被复用为主读。
- C4 `app/config.py:149-151` "Review model. Semantic review is routed to MTPLX by default"：legacy 冻结链注释，可选加"V1 legacy only"限定；`REVIEW_BACKEND` 含 deepseek（`app/llm/client.py:171`）属 legacy，已验证 V2 不引用，无需改动，由回归门禁钉住。
- C5 明确不在本次范围（避免扩界）：`DECONSTRUCT_*`/`PROTOCOL_CONTROL_*`/`EVIDENCE_NORMALIZER_*` 的 MTPLX 路由（方案侧与下游节点，设计书L83明文"沿用既有节点级配置"）；`.env.example:18` 预检 degrade 语义（启动预检，非读道降级）。

**D. `docs/PROJECT_CONTEXT.md`**：在"2026-09-02 横评终报"节（约L3476-3484）后追加带日期的读道边界收窄记录（不改写历史条目）。

**E. 回归门禁缺口（供 worker_02/03 参考，本次不实现）**
- 既有 `tests/v2/agents/test_mtplx_semantic_route_regressions.py` 现行断言与门禁兼容性：`test_default_semantic_route_is_mtplx_and_ocr_stays_omlx`（L123）、`test_evidence_normalizer_factory_preserves_mtplx_identity_and_mtp_wire`（L190）钉住的是方案侧/规范化节点，与"主读不含MTPLX"不冲突，D1a 下无需改动。
- 缺失的新门禁（可沿用 `test_route_model_defaults_never_use_legacy_27b_identity` L313 的身份防回退模式）：读道身份枚举/配置断言（main-A=zhipu-coding-plan glm-5.3-flash、main-B=cms-smk MiniMax-M3、handwriting-C=mtplx Qwen3.8-Next-Flash effort=low）、handwriting-C 输出权限（仅 handwriting[]）、读道调用无 temperature（normalizer 已有同型先例 `test_evidence_normalizer_transport_config.py:125` 拒绝 temperature）、读道模块不 import DeepSeek 客户端与 legacy reviewer。

### 需Codex裁定的开放决定
- **D1（影响范围最大）**：目标句"Qwen3.8-Flash-Next仅手写第三读"是否延伸到 Evidence Normalizer 节点（当前默认同模型 MTPLX 且 31001 规范化在其上暂停）。证据：worker_03 核对项措辞是"MTPLX不会进入**主读**"，设计书L83"下游…沿用既有节点级配置" → 倾向 **D1a：边界限于受试者逐页判读读道**，规范化节点路由不变，上述A/B修订均按此表述；若取 D1b（模型级禁令）则 `EVIDENCE_NORMALIZER_*` 需改路由，且既有回归测试与暂停作业计划需联动修订——超出"最小修订"。
- **D2（推断，待确认）**：由"只能写handwriting"推断单源候选仲裁读一并取消（涉及A4/A5/A6/A8/B3）。若保留仲裁读，则"只能写handwriting"需弱化，与目标句字面冲突。
- **D3**：§12 裁决日志 L584/589 是就地改写还是追加带日期的收窄条目（项目惯例倾向保留决策轨迹）。

## 命令与观察结果

- `grep -rn` 关键词扫描（minimax/降级/主读/读道/mtplx/qwen/handwriting/third read/lane/仲裁 等）覆盖 docs/plans/contracts/prompts/app/tests/.trellis；`grep -rn -l` 定位，`Read`/`sed -n` 精读：设计书 L280-399 与全文件关键词行、实施计划 L195-337、`.env.example` 全文、`app/llm/client.py` L120-215、`.trellis/.../implement.md` L1430-1451、PROJECT_CONTEXT L3455-3490。
- 观察1：读道冲突表述全部集中于设计书8处段落与实施计划3处工作项；代码中无读道实现，无降级/仲裁代码路径（`grep 仲裁|arbitrat app/ tests/` 零命中）。
- 观察2：`app/pipeline/ocr.py:7,380-393` MiniMax 仅在 OCR 侧车做大文件后端；`app/evidence/selective_vision_review.py` 头注释明示 GLM 观察性核验"不是入排结论、不覆盖原OCR、失败显式关闭"——与 OCR 侧车定位一致，非读道冲突。
- 观察3：V2 事实规范化链（`app/services/fact_normalization_command_service.py:114` 调 `validate_evidence_normalizer_model_config`）默认走 MTPLX，是唯一仍在 MTPLX 上运行的受试者侧语义节点（已暂停状态）。

## 阻碍或缺失环境

- 无工具/环境阻碍。两个待裁定决定（D1 边界是否延伸至规范化节点、D2 仲裁读去留）直接决定 A4-A6/A8/B3/C5 与既有测试是否纳入修订范围；不阻塞本审计结论，但阻塞 worker_02 的合同定稿口径。

## 重跑请求或下一步

- 无重跑请求。建议下一步：Codex 裁定 D1/D2/D3 后，将本报告 A-E 清单作为 worker_02（固化读道/身份/输出权限/无temperature合同与测试）与配置修订的输入；worker_03 按新门禁执行聚焦回归。本worker未做任何写入，未宣称验收；所有修订表述均为建议，最终以 Codex 裁定为准。
