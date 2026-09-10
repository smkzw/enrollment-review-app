"""Page-read response format validation and the single format-repair reread.

从 read_page 抽出的响应格式校验与修复封装：只处理"回答如何组织"的格式错误
（invalid JSON、多余字段、价值标记矛盾、未知条款引用）；日期/数值等来源内容
问题不属于格式纠正，不得借纠正重写。修复调用复用同一模型、同一原图、同一
ClausePack 与同一完整原提示，仅追加一条带校验错误与上一回答（不可信参考）
的纠正消息；是否可接受仍由同一严格合同判定，第二次仍错误则显式失败。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.domain.contracts.clause_pack import ClausePack
from app.domain.contracts.page_review import ObservationContext, PageReviewPayload
from app.domain.contracts.page_review_focus import PageReviewFocus
from app.domain.page_normalization import fact_normalization_key, handwriting_normalization_key
from app.domain.publication import canonical_hash

PAGE_REVIEW_FORMAT_REPAIR_VERSION = "page-review-format-repair/v1"

_FORMAT_REPAIR_REQUIREMENTS = (
    "上一回答未通过本系统的格式校验，仅作不可信参考：不得原样复制，也不得把它转发给任何其他模型。",
    "必须重新读取本页原图后，重新返回符合 output_schema 的完整 JSON 合同对象，不得省略任何字段。",
    "只修复列出的格式问题：将放错位置的信息移到合同允许的字段，删除不允许的字段名但不得丢失原件观察；不得改写日期数值或原文摘录、不得猜测条款、不得新增原件没有的内容。",
    "has_eligibility_value 与 facts、clause_signals、handwriting 必须一致；与上一回答矛盾时以本页原件为准。",
    "仍只输出一个 JSON 对象，不输出解释、Markdown 或其他文字。",
)


class PageResponseFormatError(Exception):
    """一次已完成的回答违反页级合同；repairable 表示允许一次格式纠正重读。"""

    def __init__(self, message: str, *, failure_kind: str, repairable: bool,
                 errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.failure_kind = failure_kind
        self.repairable = repairable
        self.errors = list(errors or [])


@dataclass(frozen=True)
class PageResponseEvaluation:
    raw: dict[str, Any]
    payload: PageReviewPayload
    response_sha256: str


def _format_errors(exc: ValidationError, limit: int = 10) -> list[str]:
    errors = [
        ".".join(str(part) for part in error["loc"]) + ": " + str(error["msg"])
        for error in exc.errors()
    ]
    if len(errors) > limit:
        errors = errors[:limit] + [f"共 {len(errors)} 项格式错误，仅显示前 {limit} 项"]
    return errors


def evaluate_page_review_response(
    text: str,
    *,
    clause_pack: ClausePack,
    review_focus: PageReviewFocus | None,
) -> PageResponseEvaluation:
    """Validate one completed response against the strict page contract."""
    # Deferred import: the harness owns extract_json_object and imports this module.
    from app.llm.page_review_harness import PageReviewHarnessError, extract_json_object

    try:
        raw = extract_json_object(text)
    except PageReviewHarnessError as exc:
        raise PageResponseFormatError(
            str(exc), failure_kind="invalid_json", repairable=True, errors=[str(exc)]
        ) from exc

    normalized = dict(raw)
    for field_name in ("facts", "handwriting"):
        if isinstance(raw.get(field_name), list):
            observations = []
            for item in raw[field_name]:
                if not isinstance(item, dict):
                    observations.append(item)
                    continue
                item = dict(item)
                if item.get("context") is not None:
                    try:
                        item["context"] = ObservationContext.model_validate(item["context"]).model_dump()
                    except ValidationError as exc:
                        raise PageResponseFormatError(
                            "资料对象或时间关联不符合合同",
                            failure_kind="schema",
                            repairable=True,
                            errors=_format_errors(exc),
                        ) from exc
                if field_name == "facts" and all(
                    isinstance(item.get(key), str) for key in ("field_name", "raw_value")
                ):
                    try:
                        key, value, unit = fact_normalization_key(
                            item["field_name"], item["raw_value"], context=item.get("context")
                        )
                    except ValueError as exc:
                        # 日期/数值歧义是来源内容问题：不得借格式纠正改写，直接显式失败。
                        raise PageResponseFormatError(
                            "资料包含无效日期或数值，请核对原件",
                            failure_kind="schema",
                            repairable=False,
                            errors=[str(exc)],
                        ) from exc
                    item.update(normalization_key=key, normalized_value=value, normalized_unit=unit)
                elif field_name == "handwriting" and all(
                    isinstance(item.get(key), str) for key in ("kind", "raw_text")
                ):
                    key, normalized_text = handwriting_normalization_key(
                        item["kind"], item["raw_text"], context=item.get("context")
                    )
                    item.update(normalization_key=key, normalized_text=normalized_text)
                observations.append(item)
            normalized[field_name] = observations
    try:
        payload = PageReviewPayload.model_validate(normalized)
    except ValidationError as exc:
        raise PageResponseFormatError(
            f"模型输出不符合页级合同：{exc}",
            failure_kind="schema",
            repairable=True,
            errors=_format_errors(exc),
        ) from exc

    known_clauses = {item.clause_id for item in clause_pack.clauses}
    if review_focus is not None and review_focus.handwriting_review and not review_focus.targets and payload.facts:
        raise PageResponseFormatError(
            "本次仅核对手写批注，不应新增普通事实",
            failure_kind="schema",
            repairable=True,
            errors=["手写专项复核必须返回 facts=[]"],
        )
    if review_focus is not None and payload.clause_signals:
        raise PageResponseFormatError(
            "辅助事实复核不得输出条款证据关系",
            failure_kind="schema",
            repairable=True,
            errors=["针对性复核必须返回 clause_signals=[]"],
        )
    unknown = sorted({item.clause_id for item in payload.clause_signals} - known_clauses)
    if unknown:
        raise PageResponseFormatError(
            "页级摘录引用了当前条款包不存在的条款",
            failure_kind="schema",
            repairable=True,
            errors=[f"未知 clause_id：{'、'.join(unknown)}；只能引用条款包内条款或返回空数组"],
        )
    return PageResponseEvaluation(
        raw=raw, payload=payload, response_sha256=canonical_hash(raw)
    )


def build_format_repair_messages(
    messages: list[dict[str, Any]],
    *,
    previous_response_text: str,
    errors: list[str],
) -> list[dict[str, Any]]:
    """Append the one versioned format-repair turn to the unchanged original prompt."""
    instruction = {
        "format_repair": {
            "repair_version": PAGE_REVIEW_FORMAT_REPAIR_VERSION,
            "validation_errors": list(errors),
            "previous_response": previous_response_text,
            "requirements": list(_FORMAT_REPAIR_REQUIREMENTS),
        }
    }
    return [*messages, {"role": "user", "content": json.dumps(instruction, ensure_ascii=False)}]


__all__ = [
    "PAGE_REVIEW_FORMAT_REPAIR_VERSION",
    "PageResponseEvaluation",
    "PageResponseFormatError",
    "build_format_repair_messages",
    "evaluate_page_review_response",
]
