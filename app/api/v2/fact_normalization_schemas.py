"""事实规范化 HTTP 契约（薄 DTO，无存储、无权威字段）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FactNormalizationRequest(_StrictModel):
    """客户端仅可声明稳定意图；不得携带权威元组或配置编号。"""

    idempotency_intent: str | None = Field(
        default=None,
        description="可选的稳定意图标记；不参与权威派生或配置选择",
    )


class FactNormalizationSubmitDTO(_StrictModel):
    job_id: str
    run_id: str
    created: bool
    state: str
    state_label: str
    recovery_action: str
