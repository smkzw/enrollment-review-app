# 模型可用性：2026-09-22最小真实诊断

用户追加要求：核查前任所说模型不可用是否属实，还是配置问题。此文更新01_REVIEW C06，但不宣布已修产品或完成病例读取。

## 结论
不是“所有模型不可用”。现场有两类配置缺陷，另有一个真实上游失败：

| 检查 | 现场证据 | 可得结论 |
|---|---|---|
| 当前产品.env | main-A=ollama-cloud / deepseek-v4.1-flash / https://ollama.com/v1；无PAGE_REVIEW_MAIN_A_API_KEY，实际route.api_key等于INDEPENDENT_VLM_API_KEY（GLM） | 明确凭据/供应商错配；本轮未向Ollama发送这个密钥 |
| 未改动产品客户端→OpenCode三模型 | 纯文字和1024×768合成图均HTTP400，error.type=MissingSessionID，明确缺x-opencode-session | 不是只有大图片才失败，旧“已排除参数配置”不成立 |
| 隔离补会话标识和真实自有User-Agent→MiMo | 文本OK 1.916秒；图片准确抄CONTROL 4729，3.041秒；stop | 当前该通道基本文字和视觉可用 |
| 同样隔离设置→DeepSeek | 文本OK 1.856秒；图片准确抄CONTROL 4729，4.080秒；stop | 当前该通道基本文字和视觉可用 |
| 同样隔离设置→Muse | 文本HTTP503，Upstream request failed: Endpoint is unavailable，1.014秒 | 本次请求确有上游不可用；不证明长期/全球不可用，未浪费图片重试 |

三个模型分别为muse-spark-1.3-contributor、mimo-v2.6-flash、deepseek-v4.1-flash。全部high、max_tokens=65536、采样默认；没有通过调小额度让它通过。成功响应服务声明模型与请求一致。

## 方法与原始证据
诊断使用本产品app.llm.page_review_harness.direct_completion，不调用OMP/Hermes。脚本在本目录probe_model_availability.py。
- 原客户端回执：model_diagnostic/receipts.json，6次失败。
- 隔离兼容实验回执：model_diagnostic_header/receipts.json，5次请求，4成功、1上游失败。
- 第二组仅在该诊断进程包装AsyncOpenAI的default_headers；未修改app源码、.env、服务配置或数据库。每模型同一稳定诊断session，User-Agent如实自报enrollment-review-connectivity-diagnostic/20260922，不冒充别的客户端。
- 输入为合成控制图，不含病例或金标；回复、usage、错误正文、耗时及图像hash已保留。凭据只来自当前产品.env，回执不含密钥。
- Ollama错误凭据只比是否相等，不打印、复制或发往其他服务。

## 官方说明及使用边界
[OpenCode Go官方接入要求](https://opencode.ai/docs/go/#where-can-i-use-it)明确要求每次会话稳定x-opencode-session及自有User-Agent；同时定位典型coding-agent请求。本轮是接入工程诊断，不把可用性视为已确认可长期运行医学业务。正式部署前需确认服务使用范围或使用合适API，不靠伪装客户端绕过限制。

## 下一步最小修复
1. W0先阻止跨供应商密钥回退，缺专用凭据应本地报配置缺失，不发出错误请求。不替用户猜/复制新密钥。
2. W3为批准且适用的OpenCode通道在产品传输层支持产品自有稳定session与User-Agent，并覆盖首次/修复/重试的一致身份；不能读取~/.omp/install-id当运行依赖，不把session硬编码进每请求。
3. 同一产品路径单页真实资料验证Schema、来源、正文结束和临床忠实度，再小批/全链；这项尚未执行。通过本合成图不证明完整长prompt/高分辨率多图/复杂中文病历已可用。
4. Muse单独列供应商本次失败，不用一个模型失败概括整个池。暂不更改默认模型；用户本轮要求Review和实施规划，不是授权更换产品路线。

不能据本轮结果反推9月21每次400均是同一原因：旧调用若无完整请求/错误体，历史原因仍未知。但当前缺头已明确复现并通过受控兼容实验消除。
