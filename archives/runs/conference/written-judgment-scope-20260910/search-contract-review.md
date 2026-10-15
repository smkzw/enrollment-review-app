# Conference Output: written-judgment-scope-20260910 - evidence_single_object

## Output

只读复审完成（未改代码；独立运行两套件：**41 项中 1 项确定性失败**，单测与全套件两种运行方式下均失败）。结论：候选检索地基的合同/覆盖/构建器主体符合声明范围（CANDIDATE-only、恒 False 三不变量、无产品接线），但**存在一个当下就红的测试**（篡改测试的期望异常类型与 owner 刚替换的 FactAuthorityValidator 路径不匹配），外加两个文档漂移与若干明确的下一体条件。以下只列实际发现。

### 一、实际缺陷（bug，非未来项）

**F1（确认失败测试）：`test_artifact_tampering_is_bounded_error_without_silent_omission` 确定性失败。** 机制（源码级）：测试期望裸 `RevisionClosureError`，但 owner 把构建器的简化校验替换为 `FactAuthorityValidator` 后，篡改页产的闭包失败现在发生在**验证器内部**：`FactAuthorityValidator._validate_complete_revision` → `CompleteEvidenceProcessingRevisionRepository.get()`（fact_authority.py:168）抛 `RevisionClosureError`（`Slice44RepositoryError`→`RepositoryError` 子类）→ 被 ：171-175 捕获包装为 `FactAuthorityError` → 构建器 ：118-122 再包装为 `JudgmentSearchSourceError`。测试断言 `RevisionClosureError` 落空。失败方向仍是安全闭合（有界拒绝、无静默省略、无数据污染），属测试期望过期而非安全回归；但任何“全绿”报告与当前树不符。**修复**：测试改期望 `JudgmentSearchSourceError`（或在构建器对闭包类失败解包重抛），并同步修 F2。

**F2（文档漂移，同根因）：`JudgmentSearchSourceError` docstring 声称 "`RevisionClosureError` / `OcrRevisionKindError` / 编解码错误原样向上传播"——经验证器路径发现的闭包失败现在会被包装，不再“原样”。** 构建器自身的第二次 `.get()`（judgment_search_source.py:138）在验证器已通过后不会再产生该类错误，文档描述的实际错误面已改变。

**F3（性能备注，非正确性问题）**：构建器每次构建把完整修订闭包全量跑两遍（验证器内一次 + 自身 `.get()` 一次，两处都是 `_verify_referenced` 全链）。正确性无害，集成为高频调用前应复用一次读取结果。

### 二、逐项核查结果（通过项，简要）

- **哈希/身份**：`scope_sha256 = canonical_hash({authority 全量 dump, requirement_id, 有序页身份})`（含 image hash），合同层强制重算相等；读道结果引用范围哈希、逐页页图哈希双重比对，越界页/伪造页图哈希均硬拒（coverage :74-77, :109-116；测试覆盖 requirement/权威/页图漂移）。✓
- **双读伪装边界**：同 provider+model（casefold+strip 后）拒绝；`reasoning_effort` 不入身份且“同模型不同强度”被拒（测试 ：763-769）；重复读道、>2 读道拒绝。跨 provider 别名消解**明确声明不在证明范围**（docstring + 测试注释一致）——这是诚实的未来边界，见第三节条件 2。✓（按声明）
- **多重性/歧义保留**：found 按读道×页×通道原样保留全部摘录（多条不折一）；ambiguous 暂定摘录原样入 `ambiguous_channels`、绝不晋升；unreadable 不得带摘录。测试覆盖两条以上摘录与混合缺口。✓
- **跨文档打印结果不漏**：范围 = 当前活动完整修订**全部清单页**，无状态/日期/类别过滤（合同无过滤字段——测试用字段集断言钉死；构建器 :158-164）；打印通道每页每读道必填；非测量文档页上的打印分析 found → `candidates_present`（测试 ：342-377 用独立 mr 文档验证）。未供给的页由 `source_scope_verified=False` 诚实兜底。✓
- **整修订闭包**：`CompleteEvidenceProcessingRevisionRepository.get()` 读取时全量闭包（:3503-3521 → `_verify_referenced`：页闭包、终态成功页、元数据/风险/定位闭包、清单哈希重算），构建器不复制该校验器；多页链经真实仓储构建测试。篡改场景仍触发闭包拒绝（只是异常类型变了，见 F1）。✓
- **陈旧权威拒绝**：`FactAuthorityValidator` 完整校验（快照作用域、episode 修订号、规则作用域、成对活动指针）；测试覆盖陈旧修订/快照/规则集/episode 修订四种。✓
- **只读行为**：全库指纹哈希 before/after 相等 + `session.new/dirty` 为空。✓
- **额外字段拒绝**：`ContractModel extra="forbid"`（common.py:11-12）覆盖全部新合同；eligibility/professional_judgment/judgment_present/requirement_satisfied 注入均拒；三个不变量布尔 `Literal[False]` 类型锁死。✓

### 三、image hash 的真实边界（按嘱核实，不替未接线模块认领）

`page_image_sha256` 由渲染器从实际 PNG 字节计算（render.py：“同一字节输入 → 同一 PNG 字节 → 同一 hash”）并冻结在页产合同里；读取路径验证的是 **payload/列镜像与 payload 哈希**——即“存储行自洽”，**没有任何代码在读取时对存储的图像字节重哈希比对**。因此本模块的范围身份只 authenticated 到“页产行未被篡改”层面，**不证明将来送给检索模型的图像字节等于该哈希**。**下一强制字节核验边界**：读道派发/取图时，取到的图像字节必须重哈希并与范围页身份的 `page_image_sha256` 全等，读道结果才可对该范围生效（结果应绑定已核验哈希）。当前未接线的模块**没有**做这件事——列为下一体条件，不是已完成性质。

### 四、下一体条件（producer/页面提示/应用完备性，均为未来项非 bug）

1. **无生产者**：`JudgmentSearchLaneResult` 无任何填充方。需要每页×双通道四态（found/not_found/unreadable/ambiguous）的页面检索提示与严格输出 schema（extra-forbid）、逐字摘录纪律、且**每范围页必须返回一条结果**（覆盖核验的缺页反查是正确后盾，但生产者不能依赖它补数）。
2. **独立性收据**：跨 provider 别名消解与真实路由身份需运行时凭据（两条独立端点的回执）核验，当前合同仅拒绝显式同身份。
3. **摘录逐字性未核验**：found 摘录文本是模型声称，无 OCR/字节交叉核对；且双读结果**未对账**——单道 found + 另一道 not_found 目前只作 candidates_present 保留（候选阶段正确），任何消费者把它当佐证前必须先定义对账规则（如双道同文 → 相互印证；分歧 → 歧义）。
4. **无持久化**：读道结果与摘要均为内存对象；D2 消费前需要追加式、权威绑定的运行/回执存储。
5. `reasoning_effort` 为任意非空白串（无枚举约束，仅审计）——生产者侧应收敛取值。
6. 小项：构建器对 requirement 只查“恰好一条模板命中”，不校验该要求确属判断类（`required_source_types` 含 investigator_assessment）——通用地基可接受，D2 消费侧应加该绑定。

### 边界

源码锚定：judgment_search.py（合同/哈希/身份冲突 ：67-94, :142-191, :288-291）、judgment_search_coverage.py（:53-181）、judgment_search_source.py（:109-174）、evidence_locator_repositories.py（:3503-3521 读取闭包、:2668 页集核对）、fact_authority.py（:159-175 包装链）、ocr_repositories.py（:505-529 解码镜像）、common.py（:11-12）。我运行的证据：两套件 41 项 1 失败（失败项单测复现，异常链完整读出）。D2 缺席证明、producer、字节核验均为未完成未来工作；本报告非临床验收、不扩展架构。
