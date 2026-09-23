"""通用选择性视觉观察侧车合同（追加写旁路，永不覆盖 OCR / 入排结论）。

本模块只描述已落盘页产物之上的**观察性**视觉核验结果：

- 成功观察必须保留 ``source_ref=`` 来源声明，并绑定页身份、输入图像哈希、
  模型、提示版本与风险理由集合；
- 失败关闭只能使用明确 ``closed`` 状态，不得写入模型伪输出冒充成功观察；
- 同一成功身份幂等复用；冲突拒绝；不触碰 OCR 原文、缓存、租约或方案语义。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain.publication import canonical_hash

from .common import ContractModel, VersionedModel
from .enums import StableEnum

__all__ = [
    "ALLOWED_SELECTIVE_VISION_RISK_REASONS",
    "SELECTIVE_VISION_OBSERVATION_CONTRACT",
    "SELECTIVE_VISION_PROMPT_VERSION",
    "SelectiveVisionObservationAttachment",
    "SelectiveVisionObservationRecord",
    "SelectiveVisionObservationStatus",
    "build_observation_identity_sha256",
    "build_prompt_sha256",
    "build_risk_reasons_sha256",
    "sanitize_observation_usage",
    "visual_observation_scope_sha256",
]

_SHA256 = r"^[0-9a-f]{64}$"

SELECTIVE_VISION_OBSERVATION_CONTRACT = "selective_vision_observation/v1"
# 提示正文未变；页级规划版本独立演进，观察身份同时绑定两者。
SELECTIVE_VISION_PROMPT_VERSION = "selective_vision_review/v1"

ALLOWED_SELECTIVE_VISION_RISK_REASONS: frozenset[str] = frozenset(
    {
        "scan_or_image_only",
        "complex_visual_or_table_layout",
        "native_extraction_anomaly",
        "ocr_evidence_risk",
    }
)

_SAFE_USAGE_KEYS = frozenset(
    {
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "reasoning_tokens",
        "cached_tokens",
    }
)


class SelectiveVisionObservationStatus(StableEnum):
    """观察侧车状态：成功观察或显式失败关闭（互斥）。"""

    SUCCEEDED = "succeeded"
    CLOSED = "closed"


def build_risk_reasons_sha256(reasons: list[str] | tuple[str, ...]) -> str:
    """对风险理由集合做顺序无关内容寻址。"""
    cleaned = sorted({str(item).strip() for item in reasons if str(item).strip()})
    return canonical_hash(cleaned)


def build_prompt_sha256(*, prompt_version: str, system_prompt: str, user_prompt: str) -> str:
    """对提示版本与系统/用户提示正文做内容寻址（不含密钥或图像）。"""
    return canonical_hash(
        {
            "contract": SELECTIVE_VISION_OBSERVATION_CONTRACT,
            "prompt_version": str(prompt_version).strip(),
            "system_prompt": str(system_prompt),
            "user_prompt": str(user_prompt),
        }
    )


def build_observation_identity_sha256(
    *,
    page_artifact_id: str,
    page_image_sha256: str,
    plan_version: str,
    model_id: str,
    prompt_sha256: str,
    risk_reasons_sha256: str,
) -> str:
    """成功观察幂等身份：页产物 + 输入图像 + 计划/模型/提示/理由。"""
    return canonical_hash(
        {
            "contract": SELECTIVE_VISION_OBSERVATION_CONTRACT,
            "page_artifact_id": str(page_artifact_id).strip(),
            "page_image_sha256": str(page_image_sha256).strip().lower(),
            "plan_version": str(plan_version).strip(),
            "model_id": str(model_id).strip(),
            "prompt_sha256": str(prompt_sha256).strip().lower(),
            "risk_reasons_sha256": str(risk_reasons_sha256).strip().lower(),
            "status": SelectiveVisionObservationStatus.SUCCEEDED.value,
        }
    )


def sanitize_observation_usage(usage: dict[str, Any] | None) -> dict[str, Any]:
    """只保留安全的用量计数；剔除密钥、路径、载荷等敏感字段。"""
    if not usage:
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in usage.items():
        name = str(key).strip()
        if name not in _SAFE_USAGE_KEYS:
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value >= 0:
            cleaned[name] = value
        elif isinstance(value, float) and value >= 0 and value.is_integer():
            cleaned[name] = int(value)
    return cleaned


class SelectiveVisionObservationRecord(VersionedModel):
    """不可变视觉观察侧车记录（追加写）。

    ``observation_identity_sha256`` 仅对 ``succeeded`` 行作为幂等键；``closed``
    行可追加多条审计失败，不得含模型伪输出正文。
    """

    schema_version: Literal["fixture/v1"] = "fixture/v1"
    observation_id: str = Field(min_length=1)
    page_artifact_id: str = Field(min_length=1)
    source_document_version_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    page_ordinal: int = Field(ge=1)
    page_image_sha256: str = Field(pattern=_SHA256)
    ocr_page_id: str | None = None
    ocr_raw_text_sha256: str | None = Field(default=None, pattern=_SHA256)
    plan_version: str = Field(min_length=1)
    risk_reasons: list[str] = Field(default_factory=list)
    risk_reasons_sha256: str = Field(pattern=_SHA256)
    model_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    prompt_sha256: str = Field(pattern=_SHA256)
    status: SelectiveVisionObservationStatus
    observation_text: str | None = None
    finish_reason: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    failure_kind: str | None = None
    observation_identity_sha256: str = Field(pattern=_SHA256)
    created_at: datetime

    @field_validator("source_ref", "model_id", "plan_version", "prompt_version")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError("必填文本字段不得为空")
        return cleaned

    @field_validator("risk_reasons")
    @classmethod
    def _normalize_reasons(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            reason = str(item).strip()
            if not reason or reason in seen:
                continue
            if reason not in ALLOWED_SELECTIVE_VISION_RISK_REASONS:
                raise ValueError(f"不支持的视觉风险理由: {reason}")
            seen.add(reason)
            cleaned.append(reason)
        return cleaned

    @field_validator("usage")
    @classmethod
    def _sanitize_usage(cls, value: dict[str, Any]) -> dict[str, Any]:
        return sanitize_observation_usage(value)

    @model_validator(mode="after")
    def validate_observation(self) -> SelectiveVisionObservationRecord:
        _require_utc(self.created_at, "SelectiveVisionObservationRecord.created_at")
        expected_reasons = build_risk_reasons_sha256(self.risk_reasons)
        if self.risk_reasons_sha256 != expected_reasons:
            raise ValueError("risk_reasons_sha256 与风险理由集合不一致")

        expected_identity = build_observation_identity_sha256(
            page_artifact_id=self.page_artifact_id,
            page_image_sha256=self.page_image_sha256,
            plan_version=self.plan_version,
            model_id=self.model_id,
            prompt_sha256=self.prompt_sha256,
            risk_reasons_sha256=self.risk_reasons_sha256,
        )
        if self.observation_identity_sha256 != expected_identity:
            raise ValueError("observation_identity_sha256 与成功观察身份不一致")

        if (self.ocr_page_id is None) != (self.ocr_raw_text_sha256 is None):
            raise ValueError("ocr_page_id 与 ocr_raw_text_sha256 必须同时存在或同时为空")

        if self.status == SelectiveVisionObservationStatus.SUCCEEDED:
            if self.failure_kind is not None:
                raise ValueError("成功观察不得携带 failure_kind")
            text = (self.observation_text or "").strip()
            if not text:
                raise ValueError("成功观察必须提供观察正文")
            marker = f"source_ref={self.source_ref}"
            if marker not in text:
                raise ValueError("成功观察正文必须保留 source_ref= 来源声明")
            if not self.risk_reasons:
                raise ValueError("成功观察必须记录至少一条风险理由")
            object.__setattr__(self, "observation_text", text)
            return self

        # closed
        if not self.failure_kind or not str(self.failure_kind).strip():
            raise ValueError("失败关闭观察必须提供 failure_kind")
        object.__setattr__(self, "failure_kind", str(self.failure_kind).strip())
        if self.observation_text not in (None, ""):
            raise ValueError("失败关闭观察不得写入模型伪输出正文")
        object.__setattr__(self, "observation_text", None)
        if self.finish_reason is not None:
            raise ValueError("失败关闭观察不得携带 finish_reason")
        if self.usage:
            raise ValueError("失败关闭观察不得携带 usage 用量字段")
        return self


def _require_utc(value: datetime, field_name: str) -> None:
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise ValueError(f"{field_name} 必须是带时区的 UTC 时间")
    if offset.total_seconds() != 0:
        raise ValueError(f"{field_name} 必须是 UTC（偏移为 0）")


class SelectiveVisionObservationAttachment(ContractModel):
    """成功观察进入事实规范化候选输入的唯一合法投影（最小通用合同）。

    硬边界（与 PRD/AGENTS 临床边界一致）：

    - 观察只能作为**来源绑定的补充候选材料或 OCR 风险提示**进入冻结的
      模型输入提示；不覆盖、不改写、不替代 OCR 原文或有效文本；
    - 观察没有 EvidenceLocator，任何仅由观察支撑的候选都无法通过
      ``LOCATOR_AND_TEXT_HASH`` 定位闭包门禁，因此观察本身永不发布为
      临床事实或入排结论；
    - 附件是自校验投影：身份哈希、来源声明与 OCR 成对绑定在构造时复核，
      篡改任一字段立即失败（不依赖下游复核）。
    """

    model_config = ConfigDict(extra="forbid")

    observation_id: str = Field(min_length=1)
    observation_identity_sha256: str = Field(pattern=_SHA256)
    page_artifact_id: str = Field(min_length=1)
    source_document_version_id: str = Field(min_length=1)
    page_ordinal: int = Field(ge=1)
    page_image_sha256: str = Field(pattern=_SHA256)
    ocr_page_id: str | None = None
    ocr_raw_text_sha256: str | None = Field(default=None, pattern=_SHA256)
    plan_version: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    prompt_sha256: str = Field(pattern=_SHA256)
    source_ref: str = Field(min_length=1)
    observation_text: str = Field(min_length=1)
    risk_reasons: list[str] = Field(default_factory=list)
    risk_reasons_sha256: str = Field(pattern=_SHA256)

    @field_validator("risk_reasons")
    @classmethod
    def _normalize_reasons(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            reason = str(item).strip()
            if not reason or reason in seen:
                continue
            if reason not in ALLOWED_SELECTIVE_VISION_RISK_REASONS:
                raise ValueError(f"不支持的视觉风险理由: {reason}")
            seen.add(reason)
            cleaned.append(reason)
        if not cleaned:
            raise ValueError("进入候选输入的观察必须至少携带一条风险理由")
        return cleaned

    @model_validator(mode="after")
    def validate_attachment(self) -> "SelectiveVisionObservationAttachment":
        text = self.observation_text.strip()
        if not text:
            raise ValueError("观察附件正文不得为空")
        if f"source_ref={self.source_ref}" not in text:
            raise ValueError("观察附件正文必须保留 source_ref= 来源声明")
        if (self.ocr_page_id is None) != (self.ocr_raw_text_sha256 is None):
            raise ValueError("ocr_page_id 与 ocr_raw_text_sha256 必须同时存在或同时为空")
        if self.risk_reasons_sha256 != build_risk_reasons_sha256(self.risk_reasons):
            raise ValueError("risk_reasons_sha256 与风险理由集合不一致")
        expected_identity = build_observation_identity_sha256(
            page_artifact_id=self.page_artifact_id,
            page_image_sha256=self.page_image_sha256,
            plan_version=self.plan_version,
            model_id=self.model_id,
            prompt_sha256=self.prompt_sha256,
            risk_reasons_sha256=self.risk_reasons_sha256,
        )
        if self.observation_identity_sha256 != expected_identity:
            raise ValueError("observation_identity_sha256 与观察附件身份不一致")
        object.__setattr__(self, "observation_text", text)
        return self


def visual_observation_scope_sha256(
    identity_hashes: Iterable[str],
) -> str | None:
    """对有序观察身份集合做内容寻址；空集合返回 ``None``（无视觉材料）。

    顺序无关、去重；任一身份格式非法即拒绝，防止把未定义材料混入冻结范围。
    """
    identities = sorted({str(item).strip().lower() for item in identity_hashes if str(item).strip()})
    if not identities:
        return None
    for item in identities:
        if len(item) != 64 or any(c not in "0123456789abcdef" for c in item):
            raise ValueError(f"视觉观察身份不是合法的 64 位十六进制: {item}")
    return canonical_hash({"visual_observation_scope/v1": identities})
