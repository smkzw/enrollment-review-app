# 入排审核系统综合评估报告

> **评估日期**: 2026-06-25
> **评估人**: 资深医学检查员 + 网络工程师视角
> **评估范围**: `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app` 全栈系统
> **测试项目**: 【测试用】评价CMS-D001片治疗中度至重度斑块状银屑病成人患者的有效性和安全性的多中心、随机、双盲、安慰剂对照Ⅱ/Ⅲ期临床研究
> **测试受试者**: SA07002（7个PDF文件，25页，103秒完成全流程）

---

## 目录

- [1. 测试概况](#1-测试概况)
- [2. 系统亮点](#2-系统亮点)
- [3. P0 严重问题（必须修复）](#3-p0-严重问题必须修复)
- [4. P1 重要问题（应尽快修复）](#4-p1-重要问题应尽快修复)
- [5. P2 一般问题（建议改进）](#5-p2-一般问题建议改进)
- [6. 优化方向与实施优先级](#6-优化方向与实施优先级)
- [7. 测试产物清单](#7-测试产物清单)

---

## 1. 测试概况

### 1.1 端到端测试链路

```
方案解构(DeepSeek V4 Pro, Ⅱ期)
  → 创建项目 D001-02-II-TEST
  → 创建受试者 SA07002
  → 上传7个PDF文件(分类: 筛选病历/检验单/既往病历/邮件/合格性讨论表)
  → 完整审核流程 SSE (OCR→Bundle→LLM Review)
  → 审核报告生成与检查
```

### 1.2 关键指标

| 指标 | 数值 |
|------|------|
| 方案解构耗时 | 240秒（DeepSeek V4 Pro） |
| OCR耗时 | 55秒（7文件25页，14页原生提取+11页VLM） |
| LLM审核耗时 | 40秒（DeepSeek V4 Pro） |
| 全流程总耗时 | 103秒 |
| 入选标准数 | 6条（IN-01 ~ IN-06） |
| 排除标准数 | 30条（EX-01 ~ EX-30） |
| 审核判定分布 | pass=26, pass_verify=1, investigator=8, insufficient=3 |
| 总体结论 | insufficient（证据不足）— 正确 |

### 1.3 模型配置

| 用途 | 模型 | 后端 |
|------|------|------|
| OCR | PaddleOCR-VL-1.6 | 本地 oMLX (127.0.0.1:8000) |
| 方案解构 | DeepSeek V4 Pro | 远程 API |
| 入排审核 | DeepSeek V4 Pro | 远程 API |
| 手写增强 | 百度OCR (可选) | 远程 API |

---

## 2. 系统亮点

### 2.1 审核Prompt设计专业严密

审核系统Prompt（`reviewer.py` `_SYSTEM_PROMPT`）直接对准临床试验入排审核的真实痛点：

- **证据层级规则**：5类证据按优先级排序（筛选病历 > 检验报告 > 既往病历 > 既往检验 > 邮件），冲突时按"当期事实"vs"既往事实"分别采信
- **判定闭环规则**：防止表格结论与推理依据矛盾——排除标准只有"明确触发"才能判❌，"存在违规可能/需确认"只能判⚠️
- **合取条件完整性**：`异常 + 有临床意义 + 研究者评估不可接受风险` 必须同时满足，不得弱化为 OR
- **检验项目精确匹配**：GGT不能替代ALT/AST/总胆红素触发肝功能排除条款
- **梅毒例外逻辑**：TPPA阳性 + TRUST阴性 + 研究者判断既往感染已治愈，三条件缺一不可

### 2.2 审核报告质量高

38条规则逐条给出判定结果和推理依据，每条引用原文关键句和证据类别标注。示例：

> `IN-01 知情同意 | ✅通过 | 【筛选-基线病历】p2 提及："受试者于2026年03月05日09时06分57秒...签署了知情同意书"`

总体结论"insufficient"正确——基线PASI/PGA/BSA评分缺失、妊娠试验缺失、泌尿系感染需研究者评估。

### 2.3 OCR三层优化有效

| 层级 | 机制 | 效果 |
|------|------|------|
| Layer 1 | 原生文本提取跳过VLM | 25页中14页原生提取，省去VLM调用 |
| Layer 2 | 文件级+页面级并发 | 7文件并行处理，8路VLM信号量控制 |
| Layer 3 | 模型路由 | 预留MiniMax/百度OCR备用通道 |

### 2.4 前端SSE处理有韧性

- 连接中断自动重试3次
- 有取消按钮（`cancelProcessing()`）
- 进度展示分4阶段（分类→OCR→组包→LLM审核）
- 心跳消息每30秒更新

### 2.5 方案解构DOCX结构提取准确

正确识别6条入选、30条排除标准，子项保留在父级条目内。Ⅱ/Ⅲ期选择机制工作正常，选择Ⅱ期后只解构Ⅱ期条款。

### 2.6 前端XSS防护到位

所有用户数据通过 `escapeHtml()` 转义后渲染，未发现 innerHTML 直接拼接用户输入的情况。

---

## 3. P0 严重问题（必须修复）

### 3.1 路径遍历漏洞

- **文件**: `app/router/subjects.py` line 86, `app/shared.py` subject_dir()
- **严重性**: CRITICAL — 可在项目目录外创建任意目录
- **测试验证**: 用 `subject_id = "../../../etc/passwd"` 成功在 `enrollment-review-app/etc/passwd/` 创建了目录（含 raw/cache/llm 子目录），已清理

**根因**: 受试者ID直接拼接为目录路径，无字符校验：

```python
# subjects.py line 86-88
sid = body.subject_id.strip()
if not sid:
    raise HTTPException(status_code=400, detail="subject_id is required")
sd = subject_dir(code, sid)  # ← 直接拼接路径，无校验
```

**影响**:
- 攻击者可创建任意路径目录
- 结合文件上传可写入任意位置文件
- GCP环境下数据完整性风险

**修复方案**:

```python
# app/shared.py — 在 subject_dir() 入口添加校验
import re

def _validate_id(value: str, name: str = "ID") -> str:
    """Reject path traversal characters in user-supplied IDs."""
    value = (value or "").strip()
    if not re.match(r'^[A-Za-z0-9_.-]+$', value):
        raise HTTPException(
            status_code=400,
            detail=f"{name} 只允许字母、数字、下划线、连字符和点号"
        )
    if '..' in value:
        raise HTTPException(status_code=400, detail=f"{name} 不允许包含 '..'")
    return value

# 在 subject_dir()、create_subject()、create_project() 等所有ID入口调用
```

**同样需要校验的入口**:
- `app/router/subjects.py`: create_subject (subject_id), upload_files (sid)
- `app/router/projects.py`: create_project (project_code)
- `app/router/pipeline.py`: run_ocr, run_review_only, process_subject (sid)
- `app/router/reports.py`: get_report_json, get_bundle (sid)

### 3.2 OCR严重幻觉污染证据

- **文件**: `app/pipeline/ocr.py` — 无后处理质检
- **严重性**: CRITICAL — 幻觉文本直接进入LLM审核证据包

**实测发现的幻觉**:

| 文件 | 页码 | 问题 | 严重程度 |
|------|------|------|----------|
| SA07002筛选期病历 | p1 | "患者已开始进行免疫治疗并持续症状加重"重复40+次，年份幻觉至2099年 | 极严重 |
| SA07002筛选期检查单 | p6 | "李明"重复50+次，覆盖真实检验数据 | 严重 |
| SA07002筛选期量表评分 | p2 | 重复率98%，内容为"表面温度/湿度/压力变化率"等无意义文本 | 严重 |

**影响**:
- 幻觉文本原样写入证据包，直接输入给LLM审核
- 本次DeepSeek V4 Pro足够智能忽略了幻觉内容，但若幻觉包含与入排标准相关的虚假信息（如虚假实验室值），可能导致错误审核结论
- 幻觉文本增大了证据包体积（筛选期病历p1单页5473字符，其中约70%是重复幻觉）

**修复方案**:

```python
# app/pipeline/ocr.py — 新增幻觉检测函数

def _detect_hallucination(text: str) -> tuple[bool, str, str]:
    """检测OCR结果中的重复幻觉。
    
    Returns: (is_hallucinated, cleaned_text, warning_message)
    """
    lines = text.split('\n')
    if len(lines) < 10:
        return False, text, ""
    
    # 检测1: 行级重复率
    non_empty = [l.strip() for l in lines if l.strip()]
    if not non_empty:
        return False, text, ""
    unique = set(non_empty)
    repetition_ratio = 1 - len(unique) / len(non_empty)
    
    if repetition_ratio > 0.5:
        # 截断重复内容，只保留唯一行
        seen = set()
        cleaned = []
        for line in lines:
            s = line.strip()
            if s and s in seen:
                continue  # 跳过重复行
            if s:
                seen.add(s)
            cleaned.append(line)
        cleaned_text = '\n'.join(cleaned)
        warning = f"[OCR质量警告: 检测到{repetition_ratio:.0%}重复内容，已截断]"
        return True, f"{warning}\n\n{cleaned_text}", warning
    
    # 检测2: 单页字符数异常（>8000字符的单页可能为幻觉）
    if len(text) > 8000:
        # 检查是否有长段落重复
        paragraphs = text.split('\n\n')
        if len(paragraphs) > 5:
            para_repetition = 1 - len(set(paragraphs)) / len(paragraphs)
            if para_repetition > 0.3:
                warning = f"[OCR质量警告: 单页{len(text)}字符，段落重复率{para_repetition:.0%}]"
                return True, f"{warning}\n\n{text[:4000]}", warning
    
    return False, text, ""

# 在 _ocr_page_smart() 和 _ocr_image_bytes() 写入缓存前调用
```

### 3.3 ICF日期提取错误

- **文件**: `app/subject_dates.py` `extract_icf_date_from_cache()`
- **严重性**: HIGH — 错误日期传入审核Prompt可能误导LLM

**实测详情**:

| 来源 | 日期 | 说明 |
|------|------|------|
| 合格性讨论表（SA07202的数据） | 2024-03-05 | ❌ 被系统提取为SA07002的ICF日期 |
| 筛选期病历（SA07002实际数据） | 2026-03-05 | ✅ LLM正确识别 |
| 审核报告底部标注 | 2024-03-05 | ❌ 显示错误日期 |

**根因**: `extract_icf_date_from_cache()` 从**所有**OCR缓存文件中搜索含"知情同意"/"签署"关键词的日期，但不校验：
1. 日期来源文件是否属于当期受试者
2. 日期来源文件的证据类别（合格性讨论表属于 enrollment_comm，不应作为ICF日期权威来源）
3. 日期合理性（2024年早于项目启动日期，显然不合理）

**修复方案**:

```python
# app/subject_dates.py — 修改 extract_icf_date_from_cache()

def extract_icf_date_from_cache(cache_dir: Path, project_start_date: str = "") -> str:
    """从筛选期病历类别的缓存中提取ICF签署日期。
    
    只从高优先级证据类别（screening_record）中提取，
    不从入组审核邮件/沟通记录中提取。
    """
    if not cache_dir.exists():
        return ""

    # 只从筛选病历目录中搜索（cache子目录名包含"筛选"或"病历"）
    valid_doc_keywords = ["筛选", "病历", "screening", "record"]
    
    candidates: list[tuple[int, str, str]] = []
    for path in sorted(cache_dir.rglob("*.md")):
        doc_name = path.parent.name
        # 只从筛选期病历类别的文档中提取
        if not any(kw in doc_name.lower() for kw in valid_doc_keywords):
            continue
            
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for match in DATE_RE.finditer(text):
            start = max(0, match.start() - 80)
            end = min(len(text), match.end() + 80)
            context = text[start:end]
            score = _candidate_score(path, context)
            if score <= 0:
                continue
            date_str = normalize_date_text(match.group(0))
            # 合理性校验：不早于2024年，不晚于当前日期
            if date_str and date_str >= "2024-01-01" and date_str <= datetime.now().strftime("%Y-%m-%d"):
                candidates.append((score, date_str, doc_name))

    if not candidates:
        return ""
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    return candidates[0][1]
```

---

## 4. P1 重要问题（应尽快修复）

### 4.1 Admin密码硬编码且无安全加固

- **文件**: `app/authz.py` line 18-19
- **问题**:
  - `ADMIN_PASSWORD = "20121116"` 明文硬编码在源码
  - 密码哈希使用 SHA-256（不适用于密码存储，应用 bcrypt/argon2）
  - Admin token 是确定性的（`sha256("admin:20121116:local-admin")`），每次登录相同，无会话过期

**修复方案**:

```python
# app/authz.py
import os
from datetime import datetime, timedelta

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")  # 从.env读取
ADMIN_ROLE = "admin"

# 密码哈希改用 bcrypt
import bcrypt
def password_hash(password: str) -> str:
    if not password:
        return ""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    if not hashed:
        return not password  # 空密码=无密码
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

# Token 增加时间戳
def admin_token() -> str:
    import secrets
    return secrets.token_urlsafe(32)

# 验证时检查过期（24小时）
def validate_user_token(username: str, token: str) -> Optional[dict]:
    # ... 现有逻辑 + 检查 token 生成时间是否在24小时内
```

### 4.2 无审计日志（API操作）

- **文件**: 所有 router 模块
- **问题**: 通过API创建项目、创建受试者、上传文件、执行审核等操作不写入 `audit_ledger.jsonl`。只有批量脚本写审计日志。
- **影响**: GCP/CFDI核查要求完整操作审计追踪。当前系统无法回答"谁在什么时候对哪个受试者做了什么操作"。

**修复方案**:

```python
# app/audit.py — 新建审计日志模块

import json
from datetime import datetime
from pathlib import Path
from app.config import PROJECTS_DIR

def log_audit(project_code: str, event: str, user: str = "", **kwargs):
    """记录审计日志到项目目录。"""
    ledger = PROJECTS_DIR / project_code / "audit_ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "project_code": project_code,
        "event": event,
        "auth_user": user,
        **kwargs,
    }
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

# 在所有写操作中调用：
# log_audit(code, "create_subject", user["username"], subject_id=sid)
# log_audit(code, "upload_files", user["username"], subject_id=sid, file_count=len(saved))
# log_audit(code, "process_start", user["username"], subject_id=sid, phase=phase)
# log_audit(code, "process_done", user["username"], subject_id=sid, verdict=report.overall_verdict)
```

### 4.3 审核后处理逻辑过度工程化

- **文件**: `app/pipeline/reviewer.py`（1211行，64KB）
- **问题**:
  - 约50个正则操作，大量硬编码规则特定逻辑（EX-07尿检替换、EX-11系统性疾病、EX-20g肝功能、EX-22梅毒例外等）
  - 每条规则按规则ID硬编码，换项目排除标准编号不同就失效
  - 正则模式极度复杂且脆弱，LLM输出措辞稍变就可能漏匹配
  - `_neutralize_definitive_fail_wording()` 直接替换LLM推理文本，可能改变语义

**影响**: 系统可维护性差，换项目需要大量修改reviewer.py。后处理与LLM输出之间的耦合使模型切换或Prompt调整都可能破坏现有逻辑。

**优化方向**:
- 将后处理逻辑通用化：不按规则ID（EX-07/EX-11）匹配，而是按语义模式匹配
- 长期方向是改进Prompt让LLM自己输出正确结论，减少后处理干预
- 考虑将后处理规则外置为JSON/YAML配置，而非硬编码在Python中

### 4.4 前端SPA路由竞态导致空白页

- **文件**: `static/index.html` `route()` 和 `navigate()` 函数
- **问题**: `navigate()` 设置 `window.location.hash` 触发 `hashchange`，`hashchange` 调用 async `route()`。如果快速连续导航，多个 `route()` 并发执行，`app.innerHTML` 可能在两个渲染之间被清空。测试中多次遇到点击"进入"/"查看报告"后页面变空白。
- **影响**: 用户体验差，需要刷新页面重新登录。

**修复方案**:

```javascript
// static/index.html — 添加导航锁

let _routeLock = false;
let _routeSeq = 0;

async function route() {
  if (_routeLock) return;  // 防止并发
  _routeLock = true;
  const mySeq = ++_routeSeq;
  
  await ensureAuthStatus();
  
  // 如果在await期间有新的导航请求，放弃当前渲染
  if (mySeq !== _routeSeq) {
    _routeLock = false;
    return;
  }
  
  renderHeaderNav();
  if (!hasAuthSession()) {
    _routeLock = false;
    return renderAuth();
  }
  
  const hash = location.hash || '#/';
  const cleanHash = hash.split('?')[0];
  const parts = cleanHash.replace('#/', '').split('/');
  
  if (parts[0] === '' || parts[0] === 'dashboard' || parts[0] === 'task') {
    renderTaskHome();
  } else if (parts[0] === 'help') {
    renderHelpPage(false);
  } else if (parts[0] === 'first-deconstruct') {
    renderFirstDeconstructPage();
  } else if (parts[0] === 're-deconstruct') {
    renderReDeconstructPage();
  } else if (parts[0] === 'audit') {
    renderAuditProjectList();
  } else if (parts[0] === 'project' && parts[1] && parts[2] === 'subject' && parts[3]) {
    await renderReport(parts[1], parts[3]);
  } else if (parts[0] === 'project' && parts[1]) {
    renderProject(parts[1]);
  } else {
    renderTaskHome();
  }
  
  _routeLock = false;
}
```

### 4.5 并发处理无锁

- **文件**: `app/router/pipeline.py` `process_subject()`
- **问题**: 两个并发的 `/process` 请求可以同时对同一受试者执行审核。状态设为"processing"但不检查当前是否已经是"processing"。
- **影响**: 两个OCR/LLM流水线并发运行浪费资源，可能导致缓存文件冲突和info.json写入竞态。

**修复方案**:

```python
# app/router/pipeline.py — 在 process_subject() 开头添加

@router.get("/process")
async def process_subject(code: str, sid: str, request: Request, ...):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    sd = ensure_subject(code, sid)
    info = load_subject_info(sd)
    require_subject_modify(user, cfg, info)
    
    # ★ 新增：防止并发处理
    if info.status == SubjectStatus.PROCESSING.value:
        raise HTTPException(
            status_code=409,
            detail=f"受试者 {sid} 正在处理中，请等待完成或重置状态后再试"
        )
    
    # ... 后续逻辑
```

### 4.6 取消处理只关闭前端连接，后端继续运行

- **文件**: `static/index.html` `cancelProcessing()`, `app/router/pipeline.py`
- **问题**: `cancelProcessing()` 只调用 `currentEventSource.close()`，后端的OCR和LLM调用仍在继续执行。
- **影响**: 用户取消后系统资源仍被占用，可能与其他操作冲突。

**修复方案**:

```python
# app/router/pipeline.py — 在SSE生成器中检查客户端断开

async def event_generator():
    try:
        # ... 各阶段处理
        
        # Stage 4: LLM Review — 检查客户端是否还连着
        review_task = asyncio.create_task(run_review(...))
        
        while not review_task.done():
            await asyncio.sleep(5)
            # ★ 检查客户端是否断开
            if await request.is_disconnected():
                review_task.cancel()  # 取消LLM调用
                logger.info("Client disconnected, cancelling review for %s", sid)
                return
            # ... 心跳消息
```

---

## 5. P2 一般问题（建议改进）

### 5.1 证据包来源文件扩展名硬编码

- **文件**: `app/pipeline/bundler.py` line 199
- **问题**: `f"- 来源文件：{doc_stem}.pdf"` 硬编码 `.pdf` 扩展名，上传 `.docx` 文件时标注错误
- **修复**: 记录原始文件扩展名，在证据包中正确标注

### 5.2 解构规则中项目代号显示"未提供"

- **问题**: DeepSeek V4 Pro解构时输出"项目代号: 未提供"，但 `extract_protocol_metadata()` 正则提取正确识别了 D001-02
- **修复**: 在解构Prompt中明确要求从方案文档元信息中提取项目代号和方案编码，或在保存规则时用元数据提取结果覆盖LLM输出

### 5.3 Swagger UI在生产中暴露

- **文件**: `app/main.py` line 35-38
- **问题**: `/docs` 端点可访问Swagger UI，暴露所有API接口定义
- **修复**: 在生产配置中设置 `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)`

### 5.4 文件上传无类型校验

- **文件**: `app/router/subjects.py` `upload_files()`
- **问题**: 接受任意文件类型，无MIME检查
- **修复**: 校验文件扩展名白名单（.pdf, .docx, .doc, .jpg, .png, .txt）

### 5.5 前端统计面板不准确

- **问题**: 项目列表"可入组/不可入组/待处理"统计不包含"insufficient"和"investigator"状态
- **修复**: 将 insufficient 和 investigator 状态纳入"待处理"统计，或新增"证据不足"和"需研究者"统计列

### 5.6 review_phases.json未保存

- **问题**: 通过 `save-protocol-draft` 创建项目时传入空 `workflow_json`，导致研究流程配置未保存，系统回退到默认阶段
- **修复**: 在 `save-protocol-draft` 端点中，如果 workflow_json 为空，从方案文件重新提取 workflow

### 5.7 合格性讨论表中的受试者编号与文件夹不一致

- **问题**: SA07002文件夹中的合格性讨论表PDF实际包含SA07202的数据
- **说明**: 这是源数据问题（文件放错文件夹），但系统不做任何校验
- **建议**: OCR后可增加受试者编号一致性检查——从各文档OCR结果中提取SA编号，与文件夹名比对，不一致时警告

### 5.8 百度OCR密钥明文存储在.env中

- **文件**: `.env`
- **问题**: BAIDU_OCR_API_KEY 和 BAIDU_OCR_SECRET_KEY 明文存储
- **说明**: .env 已在 .gitignore 中，但密钥仍以明文形式存在于磁盘
- **建议**: 敏感密钥考虑使用系统钥匙串或加密存储

---

## 6. 优化方向与实施优先级

### 6.1 优先级矩阵

| 优先级 | 编号 | 问题 | 修复复杂度 | 预计工时 | 影响 |
|--------|------|------|-----------|----------|------|
| **P0** | 3.1 | 路径遍历漏洞 | 低 | 1h | 安全Critical |
| **P0** | 3.2 | OCR幻觉检测 | 中 | 4h | 审核准确性Critical |
| **P0** | 3.3 | ICF日期提取修复 | 低 | 2h | 审核准确性High |
| **P1** | 4.1 | 密码安全加固 | 中 | 3h | 安全High |
| **P1** | 4.2 | 审计日志完善 | 中 | 4h | GCP合规 |
| **P1** | 4.3 | 后处理逻辑通用化 | 高 | 16h+ | 可维护性 |
| **P1** | 4.4 | 前端路由竞态修复 | 低 | 1h | 用户体验 |
| **P1** | 4.5 | 并发处理锁 | 低 | 1h | 数据完整性 |
| **P1** | 4.6 | 取消处理联动后端 | 中 | 3h | 资源管理 |
| **P2** | 5.1-5.8 | 各一般问题 | 低 | 各0.5-2h | 工程质量 |

### 6.2 建议实施批次

**第一批（立即修复，1天）**:
- 3.1 路径遍历 — ID校验，1小时
- 3.3 ICF日期提取 — 限定来源+合理性校验，2小时
- 4.4 前端路由竞态 — 导航锁，1小时
- 4.5 并发处理锁 — 状态检查，1小时

**第二批（本周修复，2-3天）**:
- 3.2 OCR幻觉检测 — 重复检测+截断+质量标注，4小时
- 4.1 密码安全加固 — bcrypt+token过期，3小时
- 4.2 审计日志 — 全API操作记录，4小时
- 4.6 取消处理联动 — 后端断开检测，3小时

**第三批（下周改进，1-2周）**:
- 4.3 后处理逻辑通用化 — 语义模式替代规则ID，16小时+
- 5.1-5.8 各一般问题
- 前端统计面板修复
- Swagger UI关闭
- 文件类型校验

### 6.3 长期架构建议

1. **reviewer.py 拆分**: 将1211行的后处理逻辑拆分为独立的检查器模块（`checkers/syphilis.py`, `checkers/lab_substitution.py`, `checkers/compound_logic.py`），每个检查器可独立测试和配置

2. **OCR质量评分**: 为每页OCR结果生成质量评分（重复率、字符密度、日期合理性），低质量页面在证据包中标注警告，并在审核报告中展示

3. **多模型对比机制**: 对同一受试者支持用不同模型审核并对比结果，识别模型偏差

4. **审核结果版本管理**: 同一受试者的多次审核结果保留版本历史，支持diff对比

5. **规则配置外置**: 将项目特定的审核规则（如梅毒例外逻辑、肝功能指标匹配）从Python硬编码迁移到YAML/JSON配置，支持按项目定制

---

## 7. 测试产物清单

### 7.1 创建的测试数据（可删除）

| 路径 | 说明 | 大小 |
|------|------|------|
| `projects/D001-02-II-TEST/` | 测试项目目录 | 20.5 MB |
| `projects/D001-02-II-TEST/subjects/SA07002/` | 测试受试者 | 含7个PDF+OCR缓存+审核报告 |
| `projects/D001-02-II-TEST/criteria_rules.md` | 解构规则（9125字符，6 IN + 30 EX） | 9KB |

### 7.2 已清理的测试产物

| 路径 | 说明 |
|------|------|
| `enrollment-review-app/etc/passwd/` | 路径遍历测试创建的目录，已删除 |

### 7.3 关键审核产物路径

```
projects/D001-02-II-TEST/
├── config.json                              # 项目配置
├── criteria_rules.md                        # 解构规则（6 IN + 30 EX）
└── subjects/SA07002/
    ├── info.json                            # 受试者信息（icf_date错误: 2024-03-05）
    ├── raw/                                 # 原始上传文件（7个PDF）
    ├── cache/                               # OCR缓存（7个文档25页）
    │   ├── SA07002筛选期病历/p1.md           # ⚠️ 含OCR幻觉
    │   ├── SA07002筛选期检查单/p6.md          # ⚠️ 含OCR幻觉
    │   ├── SA07002筛选期量表评分/p2.md        # ⚠️ 含OCR幻觉
    │   └── ...
    ├── evidence_bundle.md                   # 证据包（44828字符，25个片段）
    └── llm/
        ├── review_raw.md                    # LLM原始响应（9455字符）
        └── review_report.md                 # 审核报告（9702字符，38条规则）
```

---

## 附录：审核报告判定分布

```
✅ 通过 (pass)           : 26条  ████████████████████████████
✅ 通过需验证 (pass_verify):  1条  █
🟡 需研究者 (investigator) :  8条  ████████
⚠️ 证据不足 (insufficient)  :  3条  ███
❌ 不通过 (fail)          :  0条

总体结论: ⚠️ 证据不足 (insufficient)
```

**证据不足的3条**:
- IN-04-BSL: 基线期PASI/PGA/BSA评分缺失（本阶段应已完成）
- IN-06: 避孕与生殖计划评估缺失
- EX-29: 妊娠试验报告缺失

**需研究者判定的8条**:
- IN-04: 筛选期评分达标但基线期缺失
- EX-06: 泌尿系感染诊断存在，需确认是否口服抗感染药
- EX-07: 泌尿系感染是否为活动性感染需研究者评估
- EX-11: 胸部CT异常（支气管炎/主动脉硬化），需研究者判断
- EX-18: 禁用治疗洗脱期，首次给药日期未定
- EX-20: 尿常规异常+CS标注，需研究者评估不可接受风险
- EX-21: CT异常需研究者评估
- EX-25: CYP3A强诱导剂/抑制剂洗脱期需根据基线日期核实
