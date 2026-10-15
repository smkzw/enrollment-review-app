# Conference Output: written-judgment-scope-20260910 - evidence_single_object

## Output

文本级只读复审（本路由不支持图像，无视觉主张；未改代码；五套件独立复跑 **114 passed, 0 failed**，与 owner 数字一致但非临床证明）。v4 探针回执做了轻量绑定字段核对（不复制临床内容）：双读道同 scope（61d1…）/同 target（9887…）、v4 提示版本、请求/响应模型逐道一致且两道不同、stop、`product_acceptance/claims_complete=False`。

### 1. 回执保存/装载/绑定：实际缺陷

**未发现可行动缺陷。** 逐项核验（行号锚定）：
- 装配绑定链完整：scope/target 哈希全等（judgment_search_results.py:119-125）、页身份含图像哈希（:171-176）、页结果身份镜像（:177-191）、同道同页重复拒绝（:193-197）、道内身份一致（:200-210）、同 provider+model 双道拒绝（含同模型不同强度，:254-262）、响应模型必须已知且与请求一致（:140-148）、finish 双重 stop（:151-154）、回答文本哈希镜像（:163-169）、**原始回答重解反伪造成核对**（:215-228，绑定结果与原文通道逐字段一致）。
- 装载侧：`artifacts/raw_response/` 前缀与 `ArtifactStore` 实际引用格式逐字相符（artifacts.py:25,76）；纯 JSON 守卫（judgment_search_artifacts.py:119-120）位于 except 元组之外、正确传播为有界错误；规范字节往返含围栏 `completion.text`（作为字符串值不破坏外层解析）；stale scope/target/prompt 版本、损坏字节、非本类别引用全部有界拒绝且有测试钉死（26 个测试名逐条核对，含 model_copy 变造、markdown 包装、身份漂移）。
- 两条**非缺陷边界**（如实声明，不建议新证明架构）：① `messages_sha256`/图像字节只能在读取时证明——装载无法复核字节（调用方持哈希不持字节），链路成立因为回执只能源读器且 save/load 均对当前 scope/target 重绑；② `response_model=None` 的读器回执在装配即被拒（:140-143）→ 经此路径**无法保存**，保持逐页失败待重试——这是“身份未知不得算独立双读”的刻意严格性，非缺陷，编排方需知晓。

### 2. 最小下一步产品集成（复用既有持久 runner，不再造持久化框架）

**模板就是 targeted_page_review 系**（targeted_page_review_jobs.py:36-96 / executor :29-101）：JobService 步骤 DAG + retryable 读步骤（max_attempts=2）+ 逐（轮×读道）检查点 + `lane_failure` 簿记 + 条件跳过 + 幂等键 + 每步 `FactAuthorityValidator` 重验 + 版本/路由身份钉死（`TARGETED_REVIEW_CONTRACT_CHANGED` 模式）+ 复用普通读执行器做实际调用。映射到判断检索：新 job 类型（如 `judgment_candidate_search`），步骤 `read:{page}:{lane}`（retryable）+ `assemble`；payload 携带版本、v4 提示版本、authority、按 `prepare_judgment_search_target` 现准备的 scope+target 清单、双独立直连路由身份；每步现备现验（无缓存信任标记，防绕过）；成功即 `save_judgment_search_receipt`（工件库已有、已线程化）；失败保持失败。缺页/缺道/失败恢复语义与 targeted 系一致。

**确立“当前到期且显式需研究者评估”的既有真相字段（已trace）**：`EvidenceRequirement.required_source_types ∋ "investigator_assessment"`（发布行；prepare 的模板↔要求语义全量重核 judgment_search_source.py:256-284）+ `EvidenceExpectationTemplate.due_stage/workflow_stage_id` 与节点合同 `due_requirement_ids`（:296-329）+ `FactAuthorityValidator` 活动指针；投影判断分支用同一 `required_source_types` 字段门（evidence_expectations.py:278-280）。**必须保持未决的条件情形**：适用性取决于父规则/其他条件结果的（prepare 只证结构性到期，不证本例适用）；未到期/同阶段他节点；流程必做来源（prepare 显式不支持）；有 referenced 缺文件（保留缺文件理由）；任何覆盖缺口（缺道/缺页/unreadable/ambiguous/found 未核实）→ 一律 `observation_unverified`，绝不转缺失。

### 3. 效率：有界目标批处理 vs 并入下一次主读合同

- **反对** N 要求×24 页×2 道独立全扫。两条路线对比：**(a) 有界目标批处理**（每页×读道一次调用、目标组逐目标显式结果、组大小=实测预算非接受阈值、同摘录跨目标→降级待核对非采纳）——不改主读合同、不动全量判读流水线、逐要求状态/失败簿记完整；**(b) 把“评估存在性”抽取并入下一次主读页合同**——省一次全页扫，但主读无要求级目标上下文，相关性判定会被推给对账层（弱化逐要求区分度），且提示版本升级波及所有页作业与规范化链，风险面大。**现在走 (a)**；(b) 仅当主读合同因其他原因必须改版时再评估。**已完成读的复用规则**：主读/定向复核已有的手写观察与摘录只作**候选提示**（如已知 CS/NCS 候选页可先行适用性复核、可能缩短扫描），绝不得为未按该要求目标搜过的页发明缺席。**缓存/版本语义（未来显式）**：以回执为缓存单元，键含（页图像哈希、目标组清单哈希、提示版本、路由身份）——目标内容或提示版本一变即失效；装载端的版本钉死已天然强制。双独立直连端点保持（PageReaderRoute/direct_completion），不引 Hermes/OMP；现有失败证据（围栏、逐道分歧）已被 v4 与既有传输解决，**无需**嵌入式 pi。
- 缺失生产者（P2 规则）仍按上轮设计消费装配摘要，语义边界（本次提交资料措辞、不称从未发生、缺文件不重标、不满足条件即未核实）全部不变。

同厂商同家族复审独立性受限；本报告为工程复审输入，非产品/临床验收，不含任何自动正式用药摄取或 claims_complete 主张。
