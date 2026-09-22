# HANDOFF 2026-09-22：阶段性交接文档

## 系统当前状态

### 管线完成度

31001 补证重放链的每一步实际完成情况：

| 步骤 | 状态 | 说明 |
|---|---|---|
| 补证上传 | ✅ | 1页PDF成功上传 |
| OCR处理 | ✅ | 25页全部处理完成 |
| 风险核对 | ✅ | 6个blocking风险逐项核对通过 |
| 完整修订构建 | ✅ | complete-d6487542… 激活（seq 4） |
| **页判读** | **❌ 阻塞** | **所有可用 main-A 模型均无法通过25页判读** |
| 事实重整 | ⏸ 等页判读 | 上次成功产出143条（旧修订） |
| 投影 | ⏸ 等事实重整 | 当前69条全未决 |
| 绑定/资格核对 | ⏸ 等页判读 | 等新事实产生后重跑 |
| 官方报告发布 | ⏸ 等方法采用 | 用户签字（决策边界） |

### 当前阻塞点：main-A 页判读模型

25页全部因 main-A 读取失败而阻塞。已尝试的模型：

| 模型 | 端点 | 结果 |
|---|---|---|
| muse-spark-1.3-contributor | opencode-go | ❌ 上游不可用 |
| mimo-v2.6-flash | opencode-go | ❌ 全25页 400 BadRequest |
| deepseek-v4.1-flash | opencode-go | ❌ 全25页 400 BadRequest |

**根因**：opencode-go 端点对页判读的完整请求（base64大图像+临床prompt+65536 max_tokens+reasoning_effort+response_format json_object）返回 400 BadRequest。简单文本和小图测试均通过，排除密钥/配额/参数格式问题——是端点对大体量多模态请求的处理限制。

main-B（cms-router/cms-model）在20/25页上成功，仅5页双路都失败。

## 需要用户做的决策

### 1. 指定可用的 main-A 页判读模型

当前 opencode-go 端点无法处理页判读的多模态大请求。可选方案：
- 提供 another cloud provider 的视觉模型 API key
- 确认 opencode-go 端点是否有特定的请求参数要求
- 或指定其他可用的模型和端点组合

### 2. 轮换已暴露的 opencode API key

该 key（sk-3V4p...）已进过 git 历史（284fb7f1 之前的守望脚本硬编码）。
删除源码不等于失效，需在 opencode 控制台轮换。

### 3. 金标标注与方法采用签字

页判读完成后需要：
- 金标标注（build_binding_gold_split_template.py 已备）
- 方法采用签字（record_review_method_adoption.py）
- 官方报告发布（publish 端点）

这些是临床决策边界，AI 不可代签。

## 本轮完成的修复（全部推送）

| 项 | 内容 | 提交 |
|---|---|---|
| F01/P0 | 守望脚本密钥移除 + F01-followup .env读取 | 284fb7f1 + e090219e |
| F02 | 资格选择语义内核（拒绝/未决不升级） | 07f9abca |
| F03 | scope 查询（不再全库 LIMIT 5） | 07f9abca |
| F04（预览侧） | 更正预览枚举同源兄弟事实 | d6a120bd |
| F06 | 规模驱动错误信封检查 | d64d371a |
| F07 | 料集内容寻址+源码树外+全媒体 | d64d371a |
| F08 | 队列严重性取最高档、顺序无关 | c13ee9fc |
| F09 | 默认选中最高优先项 + bullet 详情 + 动作指令 + CSS/页脚 | 多个提交 |
| F10 | 页判读主记录身份绑定实际返回模型 | 967b313a |
| 证据面板 | 无事实时也可浏览全部原件 | aba8a358 |
| 守望脚本 | 密钥从 .env 读取（F01 followup） | e090219e |

## 0922 纠偏包完成的验证

- 补证重放③：上传→OCR→风险核对→完整修订→激活→事实重整143条→投影 f2ae0717
- A25④ 旧件不变终验通过（旧修订/清单/快照/事实/元数据全部原样）
- 页判读→事实重整→投影对齐（旧模型组合下完成）
- 语义资格内核生效：拒绝/未决配对不再升级为可用值
- 规模验证脚本契约干跑核查通过

## 踩了哪些坑

1. opencode-go 端点对页判读的多模态大请求返回 400——简单文本调用正常
2. mimo-v2.6-flash 和 deepseek-v4.1-flash 都无法通过页判读 schema 校验
3. cms 网关对长流的流式判读会间歇截断
4. 同值事实多通道 → 单点更正不生效
5. 元数据确认晚于页判读 → 修订重建导致页判读返工
6. 换模型后重试旧任务沿用旧配置 → 应创建新任务
7. 遗留 .env 与最新决策漂移 → 配置漂移引发返工
8. 模型目录 401 → 预检拒绝启动

## 下一步

1. **用户决策**：指定可用的 main-A 页判读模型和端点
2. **用户执行**：轮换 opencode API key
3. **用户提供**：30页级规模验证的真实资料文件夹路径
4. **恢复后自动链**：页判读 → 事实重整 → 投影 → 闭包推送
5. **用户执行**：金标标注 → 方法采用 → 官方报告发布
6. **跨方案验证**：另一研究方案文档走 A 链

## 关键文件索引

| 文件 | 说明 |
|---|---|
| REPLAY_LOG.md | 补证重放完整日志 |
| wp08_baseline.json 等 | 状态快照 |
| wp08_capture_state.py | 状态采集脚本 |
| build_binding_gold_split_template.py | 金标模板生成 |
| record_review_method_adoption.py | 方法采用记录 |
| build_scale_validation_set.py | 规模验证料集构建 |
| run_scale_validation.py | 规模验证全链驱动 |
| HANDOFF_20260922_MUSE_SPARK_WATCH.md | 前一份交接 |
| CHECKPOINT_20260921_C_QUALIFIED_CONSUMPTION.md | 纠偏包执行记录 |
