"""Compare DeepSeek V4 Flash/Pro reasoning modes on focused review regressions.

This is an experiment script, not a production pipeline path. It builds compact
case packets from existing protocol rules and evidence bundles, asks each model
configuration to review only the known risky rule(s), and writes a horizontal
comparison report.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.llm.client import _get_deepseek_client


OUT_DIR = Path(os.getenv("DEEPSEEK_COMPARE_OUT_DIR", "output/deepseek_reasoning_mode_comparison_20260625"))
REQUEST_TIMEOUT_SEC = 180
CONCURRENCY = int(os.getenv("DEEPSEEK_COMPARE_CONCURRENCY", "2"))


@dataclass(frozen=True)
class Mode:
    label: str
    model: str
    reasoning_effort: str | None


@dataclass(frozen=True)
class Case:
    case_id: str
    project: str
    subject_id: str
    phase: str
    focus_rule_ids: tuple[str, ...]
    keywords: tuple[str, ...]
    expected: dict[str, Any]
    note: str


MODES = [
    Mode("V4 Flash default", "deepseek-v4-flash", None),
    Mode("V4 Flash max", "deepseek-v4-flash", "max"),
    Mode("V4 Pro high", "deepseek-v4-pro", "high"),
    Mode("V4 Pro max", "deepseek-v4-pro", "max"),
]


def selected_modes() -> list[Mode]:
    raw = os.getenv("DEEPSEEK_COMPARE_MODES", "").strip()
    if not raw:
        return MODES
    wanted = {item.strip() for item in raw.split(",") if item.strip()}
    return [mode for mode in MODES if mode.label in wanted]


CASES = [
    Case(
        case_id="SAR-31001-EX09e",
        project="MG-K10-SAR-III",
        subject_id="31001",
        phase="baseline_randomization",
        focus_rule_ids=("EX-09", "EX-09e", "EX-09g"),
        keywords=("ALT 57.8", "AST 34.9", "TBIL 30.5", "GGT 146", "CS 肝功能"),
        expected={
            "overall_not": {"fail"},
            "rules": {
                "EX-09e": {"acceptable": {"pass"}, "forbidden": {"fail"}},
                "EX-09g": {"acceptable": {"investigator", "insufficient"}, "forbidden": {"fail"}},
            },
            "bad_patterns": [r"GGT.{0,20}触发.{0,20}EX-09e"],
        },
        note="实验室阈值自我矛盾：ALT/TBil未达阈值，GGT不能替代EX-09e。",
    ),
    Case(
        case_id="SAR-31010-IN05",
        project="MG-K10-SAR-III",
        subject_id="31010",
        phase="baseline_randomization",
        focus_rule_ids=("IN-05", "EX-09", "EX-09e", "EX-09g"),
        keywords=("EOS", "EO#", "血EOS250", "D1需进行检测", "OCR严重损坏", "ALT 75.1"),
        expected={
            "overall_not": {"fail"},
            "rules": {
                "IN-05": {"acceptable": {"insufficient"}, "forbidden": {"fail", "pass"}},
                "EX-09e": {"acceptable": {"insufficient", "pass", "investigator"}, "forbidden": {"fail"}},
            },
            "bad_patterns": [r"OCR.{0,20}(不可读|损坏).{0,60}不满足", r"无.{0,20}D1.{0,20}证明.{0,20}不满足"],
        },
        note="当前阶段资料不可读：不能把缺D1/基线可判读EOS证明当作硬失败。",
    ),
    Case(
        case_id="SAR-31015-EX09e",
        project="MG-K10-SAR-III",
        subject_id="31015",
        phase="baseline_randomization",
        focus_rule_ids=("EX-09", "EX-09e", "EX-09g"),
        keywords=("ALT 76.1", "AST 50.0", "TBil 10.2", "CS肝功能不全", "低密度脂蛋白"),
        expected={
            "overall_not": {"fail"},
            "rules": {
                "EX-09e": {"acceptable": {"pass"}, "forbidden": {"fail"}},
                "EX-09g": {"acceptable": {"investigator", "insufficient"}, "forbidden": {"fail"}},
            },
            "bad_patterns": [r"AST 50.{0,40}触发.{0,20}EX-09e", r"ALT 76.1.{0,40}触发.{0,20}EX-09e"],
        },
        note="EX-09e阈值：ALT/AST均未超过2倍ULN，CS肝功能异常应转EX-09g。",
    ),
    Case(
        case_id="D001-SA01025-EX20g",
        project="D001-02-II",
        subject_id="SA01025",
        phase="screening_run_in",
        focus_rule_ids=("EX-20",),
        keywords=("GGT 210", "ALT 29.3", "AST 37.8", "总胆红素 TBIL 7.80", "HGB 121"),
        expected={
            "overall_not": {"fail"},
            "rules": {
                "EX-20": {"acceptable": {"investigator", "insufficient", "pass"}, "forbidden": {"fail"}},
            },
            "bad_patterns": [r"GGT.{0,30}(触发|达到).{0,30}EX-20g", r"GGT.{0,40}ALT或AST或总胆红素"],
        },
        note="GGT不能替代ALT/AST/总胆红素触发EX-20g。",
    ),
    Case(
        case_id="D001-SA03009-EX07-EX20h",
        project="D001-02-II",
        subject_id="SA03009",
        phase="screening_run_in",
        focus_rule_ids=("EX-07", "EX-20"),
        keywords=("葡萄糖", "潜血", "活动性感染", "急性疾病状态", "不可接受风险"),
        expected={
            "overall_not": {"fail"},
            "rules": {
                "EX-07": {"acceptable": {"pass", "investigator"}, "forbidden": {"fail"}},
                "EX-20": {"acceptable": {"investigator", "insufficient", "pass"}, "forbidden": {"fail"}},
            },
            "bad_patterns": [
                r"尿.{0,20}(葡萄糖|潜血).{0,60}(感染|活动性感染)",
                r"(葡萄糖|潜血).{0,40}直接.{0,12}(排除|不通过)",
                r"实验室异常.{0,30}有临床意义.{0,30}不通过",
            ],
        },
        note="尿糖/潜血不能证明活动性感染；EX-20h是AND条件。",
    ),
    Case(
        case_id="D001-SA16002-EX22",
        project="D001-02-II",
        subject_id="SA16002",
        phase="screening_run_in",
        focus_rule_ids=("EX-22",),
        keywords=("TPPA", "梅毒特异性抗体", "TRUST", "目前无不适", "未予治疗", "既往感染已治愈"),
        expected={
            "overall_not": {"fail"},
            "rules": {
                "EX-22": {"acceptable": {"investigator", "insufficient"}, "forbidden": {"fail", "pass"}},
            },
            "bad_patterns": [
                r"TRUST.{0,30}阴性.{0,60}(通过|不触发)",
                r"目前无不适.{0,60}(例外|通过|不触发)",
                r"非活动性感染.{0,60}(例外|通过|不触发)",
            ],
        },
        note="梅毒特异性抗体阳性例外：还需研究者明确既往感染已治愈。",
    ),
]


SYSTEM_PROMPT = """\
你是一名资深临床试验入排审核专家。只审核用户给出的指定规则，不要扩展到其它规则。

硬性规则：
- 排除标准只有明确达到方案触发条件才能判 fail；可能性、待确认、缺资料、需研究者评估不能判 fail。
- 方案出现“且/并且/同时/经研究者评估”时，所有组件都必须满足；不得把 AND 弱化为 OR。
- 实验室阈值只能由方案列名项目触发，不能用同类或相邻项目替代。
- 缺少当前阶段应有资料、OCR不可读、无D1/基线证明时，应判 insufficient，不是 fail。
- 若需要研究者判断“不适合入组/不可接受风险/影响评估”，必须有明确判断来源；缺该判断时判 investigator。
- 用户给出的每个官方父级规则ID必须输出；可以在父级行中汇总子项，但不得只输出子项而漏父级。
- “符合所有入排标准/不符合排除标准/可入组”不能替代单条复合条款要求的研究者判断。
- 输出前自检：任何 fail 的依据不得同时写未达阈值、未触发、缺资料、需研究者或待补充；若出现这些保留语，先改成 pass/insufficient/investigator。

请严格输出 JSON，不要输出 Markdown：
{
  "overall_verdict": "pass|fail|insufficient|investigator",
  "rules": [
    {"rule_id": "EX-xx", "verdict": "pass|fail|insufficient|investigator|na", "rationale": "1-3句中文依据"}
  ],
  "risk_flags": ["可选，列出需要人审注意的风险点"]
}
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_rule_blocks(criteria: str, rule_ids: tuple[str, ...]) -> str:
    blocks: list[str] = []
    for rule_id in rule_ids:
        pattern = re.compile(rf"(?ms)^####\s+{re.escape(rule_id)}\b.*?(?=^####\s+(?:IN|EX)-\d+|\Z)")
        match = pattern.search(criteria)
        if match:
            blocks.append(match.group(0).strip())
    return "\n\n".join(blocks)


def extract_focus_evidence(bundle: str, keywords: tuple[str, ...], *, max_chars: int = 7000) -> str:
    windows: list[str] = []
    seen: set[tuple[int, int]] = set()
    for keyword in keywords:
        for match in re.finditer(re.escape(keyword), bundle, re.IGNORECASE):
            start = max(0, match.start() - 850)
            end = min(len(bundle), match.end() + 1100)
            key = (start // 200, end // 200)
            if key in seen:
                continue
            seen.add(key)
            windows.append(bundle[start:end].strip())
            if sum(len(item) for item in windows) > max_chars:
                break
        if sum(len(item) for item in windows) > max_chars:
            break
    if not windows:
        return bundle[:max_chars]
    joined = "\n\n--- 证据片段分隔 ---\n\n".join(windows)
    return joined[:max_chars]


def build_messages(case: Case) -> list[dict[str, str]]:
    root = Path("projects") / case.project
    criteria = _read(root / "criteria_rules.md")
    bundle = _read(root / "subjects" / case.subject_id / f"evidence_bundle_{case.phase}.md")
    rules = extract_rule_blocks(criteria, case.focus_rule_ids)
    evidence = extract_focus_evidence(bundle, case.keywords)
    user_prompt = f"""\
案例：{case.case_id}
项目：{case.project}
受试者：{case.subject_id}
审核阶段：{case.phase}
本次只审核规则：{', '.join(case.focus_rule_ids)}

## 方案规则
{rules}

## 证据摘录
{evidence}
"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object found")
    return json.loads(match.group(0))


def normalize_verdict(value: Any) -> str:
    text = str(value or "").strip().lower()
    mapping = {
        "通过": "pass",
        "不通过": "fail",
        "证据不足": "insufficient",
        "需研究者": "investigator",
        "需研究者判定": "investigator",
        "不适用": "na",
    }
    return mapping.get(text, text)


def evaluate(case: Case, data: dict[str, Any] | None, raw: str, error: str = "") -> dict[str, Any]:
    if error or not data:
        return {"score": 0, "flags": [f"parse_or_call_error: {error or 'empty data'}"], "rule_verdicts": {}}
    flags: list[str] = []
    score = 100
    overall = normalize_verdict(data.get("overall_verdict"))
    if overall in set(case.expected.get("overall_not", set())):
        score -= 25
        flags.append(f"overall_unacceptable:{overall}")

    rule_map: dict[str, str] = {}
    rationale_map: dict[str, str] = {}
    for row in data.get("rules") or []:
        rid = str(row.get("rule_id") or "").strip()
        if not rid:
            continue
        rule_map[rid] = normalize_verdict(row.get("verdict"))
        rationale_map[rid] = str(row.get("rationale") or "")

    for rid, expectation in (case.expected.get("rules") or {}).items():
        verdict = rule_map.get(rid, "")
        if not verdict:
            score -= 25
            flags.append(f"{rid}:missing")
            continue
        if verdict in set(expectation.get("forbidden", set())):
            score -= 45
            flags.append(f"{rid}:forbidden_verdict:{verdict}")
        elif verdict not in set(expectation.get("acceptable", set())):
            score -= 20
            flags.append(f"{rid}:unexpected_verdict:{verdict}")

    combined_text = raw + "\n" + "\n".join(rationale_map.values())
    for pattern in case.expected.get("bad_patterns", []):
        if re.search(pattern, combined_text, re.IGNORECASE):
            score -= 15
            flags.append(f"bad_pattern:{pattern}")

    return {"score": max(0, score), "flags": flags, "rule_verdicts": rule_map}


async def call_mode(case: Case, mode: Mode, sem: asyncio.Semaphore) -> dict[str, Any]:
    messages = build_messages(case)
    client = _get_deepseek_client()
    raw_path = OUT_DIR / f"{case.case_id}__{mode.label.replace(' ', '_')}.raw.txt"
    enqueued = time.monotonic()
    api_elapsed = 0.0
    raw = ""
    error = ""
    usage: dict[str, Any] = {}
    try:
        async with sem:
            api_started = time.monotonic()
            request_kwargs: dict[str, Any] = {
                "model": mode.model,
                "messages": messages,
                "max_tokens": 12000,
            }
            if mode.reasoning_effort:
                request_kwargs["reasoning_effort"] = mode.reasoning_effort
                request_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            response = await asyncio.wait_for(
                client.chat.completions.create(**request_kwargs),
                timeout=REQUEST_TIMEOUT_SEC,
            )
            api_elapsed = round(time.monotonic() - api_started, 1)
        msg = response.choices[0].message
        raw = msg.content or ""
        usage_obj = getattr(response, "usage", None)
        if usage_obj is not None:
            try:
                usage = usage_obj.model_dump()
            except Exception:
                usage = {
                    "prompt_tokens": getattr(usage_obj, "prompt_tokens", None),
                    "completion_tokens": getattr(usage_obj, "completion_tokens", None),
                    "total_tokens": getattr(usage_obj, "total_tokens", None),
                }
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    elapsed = round(time.monotonic() - enqueued, 1)
    raw_path.write_text(raw or error, encoding="utf-8")

    data: dict[str, Any] | None = None
    parse_error = ""
    if raw and not error:
        try:
            data = extract_json_object(raw)
        except Exception as exc:
            parse_error = f"{type(exc).__name__}: {exc}"
    eval_result = evaluate(case, data, raw, error or parse_error)
    return {
        "case_id": case.case_id,
        "project": case.project,
        "subject_id": case.subject_id,
        "phase": case.phase,
        "mode": mode.label,
        "model": mode.model,
        "reasoning_effort": mode.reasoning_effort,
        "elapsed_sec": elapsed,
        "api_elapsed_sec": api_elapsed,
        "queue_wait_sec": round(max(0.0, elapsed - api_elapsed), 1),
        "usage": usage,
        "raw_path": str(raw_path),
        "parse_error": parse_error,
        "call_error": error,
        "data": data or {},
        "evaluation": eval_result,
    }


def _tokens(result: dict[str, Any]) -> str:
    usage = result.get("usage") or {}
    total = usage.get("total_tokens")
    details = usage.get("completion_tokens_details") or {}
    reasoning = details.get("reasoning_tokens")
    if total is None:
        return "-"
    if reasoning is not None:
        return f"{total} / reasoning {reasoning}"
    return str(total)


def render_markdown(results: list[dict[str, Any]]) -> str:
    by_case: dict[str, dict[str, dict[str, Any]]] = {}
    case_meta = {case.case_id: case for case in CASES}
    for result in results:
        by_case.setdefault(result["case_id"], {})[result["mode"]] = result

    lines = [
        "# DeepSeek V4 审核参数小样本横向对比",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "说明：本实验是聚焦历史错误类型的语义审核对比，不是全规则全流程重审。评分以既定医学监查边界为准：硬失败误判、AND弱化、项目替代、证据缺失误判会扣分。",
        "",
        "| 案例 | 历史风险点 | " + " | ".join(mode.label for mode in MODES) + " |",
        "|---|---|" + "|".join("---" for _ in MODES) + "|",
    ]
    for case_id, mode_map in by_case.items():
        case = case_meta[case_id]
        cells = []
        for mode in MODES:
            result = mode_map.get(mode.label)
            if not result:
                cells.append("未运行")
                continue
            score = result["evaluation"]["score"]
            flags = "；".join(result["evaluation"]["flags"]) or "无"
            verdicts = ", ".join(f"{k}={v}" for k, v in result["evaluation"]["rule_verdicts"].items()) or "-"
            cells.append(
                f"score {score}<br>{verdicts}<br>{result.get('api_elapsed_sec', result['elapsed_sec'])}s API / {result['elapsed_sec']}s total<br>{_tokens(result)}<br>{flags}"
            )
        lines.append(f"| {case.case_id} | {case.note} | " + " | ".join(cells) + " |")

    lines.extend([
        "",
        "## 汇总",
        "",
        "| 模式 | 平均分 | 满分案例数 | 超时/解析失败数 | 平均耗时(s) |",
        "|---|---:|---:|---:|---:|",
    ])
    for mode in MODES:
        mode_results = [r for r in results if r["mode"] == mode.label]
        if not mode_results:
            continue
        avg_score = sum(r["evaluation"]["score"] for r in mode_results) / len(mode_results)
        perfect = sum(1 for r in mode_results if r["evaluation"]["score"] == 100)
        failed = sum(1 for r in mode_results if r.get("call_error") or r.get("parse_error"))
        avg_elapsed = sum(r["elapsed_sec"] for r in mode_results) / len(mode_results)
        elapsed_key = "api_elapsed_sec" if any("api_elapsed_sec" in r for r in mode_results) else "elapsed_sec"
        avg_elapsed = sum(r.get(elapsed_key, r["elapsed_sec"]) for r in mode_results) / len(mode_results)
        lines.append(f"| {mode.label} | {avg_score:.1f} | {perfect}/{len(mode_results)} | {failed} | {avg_elapsed:.1f} |")

    return "\n".join(lines) + "\n"


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(CONCURRENCY)
    modes = selected_modes()
    tasks = [call_mode(case, mode, sem) for case in CASES for mode in modes]
    results: list[dict[str, Any]] = []
    for task in asyncio.as_completed(tasks):
        result = await task
        results.append(result)
        print(
            json.dumps(
                {
                    "case": result["case_id"],
                    "mode": result["mode"],
                    "score": result["evaluation"]["score"],
                    "flags": result["evaluation"]["flags"],
                    "elapsed_sec": result["elapsed_sec"],
                    "error": result.get("call_error") or result.get("parse_error"),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    results.sort(key=lambda r: (r["case_id"], r["mode"]))
    (OUT_DIR / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "comparison.md").write_text(render_markdown(results), encoding="utf-8")
    print(f"RESULTS_JSON={OUT_DIR / 'results.json'}")
    print(f"COMPARISON_MD={OUT_DIR / 'comparison.md'}")


if __name__ == "__main__":
    asyncio.run(main())
