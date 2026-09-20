"""冻结方案解构横评入口的横评默认设置离线回归（无模型调用）。

覆盖：

- mlx-serve 输出预算守卫：本地批次上限不足时在发送前显式拒绝并指认
  ``MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS``；上限足够时不静默压低请求；
- ``build_transport`` 的 mlx-serve 显式支持与 ``provider_defaults`` 透传；
  模型未显式配置时拒绝，绝不回退到其他供应商默认模型；
- 执行记录持久化 ``provider_defaults`` 与传输身份；
- CLI ``--provider-defaults`` 开关缺省关闭，显式传入时到达 execute。

离线 e2e 通过函数参数注入测试执行器覆盖（页面文本构造器 / 草稿响应
构造器）与注入传输完成；CLI 路径从不注入。全程不访问网络、不调用模型。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.agents import protocol_semantic_transport as transport_module
from app.agents.protocol_semantic_transport import DeepSeekProtocolAgentTransport
from app.domain.contracts.enums import StudyPhase
from scripts import run_frozen_protocol_comparison as comparison
from tests.v2.api.protocol_e2e_helpers import (
    build_passing_draft_json,
    build_pipeline_e2e_docx,
    page_texts_from_blocks,
)

# JobStore 持久化列使用 UTC naive；测试服务时间必须与运行时一致。
NAIVE_NOW = datetime(2026, 9, 8, tzinfo=timezone.utc).replace(tzinfo=None)

IDENTITY_OVERRIDES = {
    "protocol_code": "E2E-001",
    "project_name": "E2E 测试研究",
    "official_version": "V1.0",
    "official_date_value": "2026-08-17",
    "official_date_precision": "day",
}


@pytest.fixture
def protocol_docx(tmp_path: Path) -> Path:
    docx = tmp_path / "source" / "protocol.docx"
    docx.parent.mkdir(parents=True, exist_ok=True)
    build_pipeline_e2e_docx(docx)
    return docx


def _prepare(run_dir: Path, protocol_docx: Path) -> dict:
    return comparison.prepare(
        run_dir=run_dir,
        protocol_path=protocol_docx,
        study_phase=StudyPhase.PHASE_II,
        identity_overrides=IDENTITY_OVERRIDES,
        now=lambda: NAIVE_NOW,
        executor_overrides={"page_texts_builder": page_texts_from_blocks},
    )


def test_mlx_serve_budget_guard_rejects_insufficient_local_cap(monkeypatch):
    monkeypatch.setattr(comparison, "MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS", 16384)
    with pytest.raises(
        comparison.ComparisonGuardError, match="MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS"
    ):
        comparison.resolve_output_budget("mlx-serve", 131072)


def test_mlx_serve_budget_is_not_silently_capped_below_request(monkeypatch):
    monkeypatch.setattr(comparison, "MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS", 131072)
    assert comparison.resolve_output_budget("mlx-serve", 131072) == 131072
    assert (
        comparison.effective_output_budget("mlx-serve", 131072) == 131072
    )
    monkeypatch.setattr(comparison, "MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS", 100000)
    assert comparison.resolve_output_budget("mlx-serve", 131072) == 100000
    # 上限充足时预算按产品传输同一规则生效，不抬高也不压低请求。
    monkeypatch.setattr(comparison, "MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS", 65536)
    assert comparison.resolve_output_budget("mlx-serve", 131072) == 65536


def test_build_transport_keeps_mlx_serve_identity_and_flag(monkeypatch):
    monkeypatch.setattr(
        transport_module, "MLX_SERVE_MODEL", "hub/qwen3-xhigh-test"
    )
    # 显式预算 131072 必须在产品传输的本地批次上限内原样生效；超限将显式
    # 拒绝而不是静默 min() 压缩。
    monkeypatch.setattr(
        transport_module, "MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS", 131072
    )
    transport = comparison.build_transport(
        "mlx-serve",
        reasoning_effort="xhigh",
        max_tokens=131072,
        provider_defaults=True,
    )
    assert transport._backend == "mlx-serve"
    assert transport._provider_defaults is True
    assert transport._reasoning_effort == "xhigh"
    identity = comparison._transport_identity(transport)
    assert identity["backend"] == "mlx-serve"
    assert identity["provider_defaults"] is True

    legacy = comparison.build_transport("mlx-serve", max_tokens=131072)
    assert legacy._provider_defaults is False
    assert comparison._transport_identity(legacy)["provider_defaults"] is False


def test_build_transport_mlx_serve_requires_explicit_model(monkeypatch):
    monkeypatch.setattr(transport_module, "MLX_SERVE_MODEL", "")
    with pytest.raises(comparison.ComparisonGuardError, match="MLX_SERVE_MODEL"):
        comparison.build_transport("mlx-serve", max_tokens=131072)


def test_cli_provider_defaults_defaults_off_and_reaches_execute(monkeypatch):
    captured: dict = {}

    def _fake_execute(**kwargs):
        captured.update(kwargs)
        return {
            "outcome": {
                "job_state": "waiting_user",
                "awaiting_user": "review",
                "publishable": True,
            }
        }

    monkeypatch.setattr(comparison, "execute", _fake_execute)

    assert comparison.main(["execute", "--run-dir", "unused"]) == comparison.EXIT_OK
    assert captured["provider_defaults"] is False

    assert (
        comparison.main(
            [
                "execute",
                "--run-dir",
                "unused",
                "--backend",
                "mlx-serve",
                "--reasoning-effort",
                "xhigh",
                "--max-tokens",
                "131072",
                "--provider-defaults",
            ]
        )
        == comparison.EXIT_OK
    )
    assert captured["provider_defaults"] is True
    assert captured["backend"] == "mlx-serve"
    assert captured["reasoning_effort"] == "xhigh"
    assert captured["max_tokens"] == 131072


def test_prepare_then_execute_persists_provider_defaults(
    tmp_path: Path, protocol_docx: Path, monkeypatch
) -> None:
    # 横评要求输出预算 >= 65536；本地上限由操作者显式调高，缺省不放宽。
    monkeypatch.setattr(comparison, "MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS", 131072)
    # 产品传输读取自身模块常量作为显式预算校验上限，同样需要显式调高。
    monkeypatch.setattr(
        transport_module, "MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS", 131072
    )
    run_dir = tmp_path / "run"
    _prepare(run_dir, protocol_docx)

    injected = DeepSeekProtocolAgentTransport(
        client=object(),
        backend="mlx-serve",
        model="hub/qwen3-xhigh-test",
        reasoning_effort="xhigh",
        provider_defaults=True,
    )
    executed = comparison.execute(
        run_dir=run_dir,
        backend="mlx-serve",
        reasoning_effort="xhigh",
        max_tokens=131072,
        provider_defaults=True,
        transport=injected,
        transport_factory=lambda: injected,
        now=lambda: NAIVE_NOW,
        executor_overrides={"draft_response_builder": build_passing_draft_json},
    )

    assert executed["outcome"]["awaiting_user"] == "review"
    assert executed["provider_defaults"] is True
    assert executed["budget"]["effective"] == 131072
    assert executed["transport"]["backend"] == "mlx-serve"
    assert executed["transport"]["provider_defaults"] is True
    assert executed["transport"]["reasoning_effort"] == "xhigh"
    # 真实产品链身份保留：执行器与回执仍来自生产入口。
    assert executed["runner"] == "scripts/run_frozen_protocol_comparison.py"
    assert executed["claims_complete"] is False

    execute_record = json.loads(
        (run_dir / "execute" / "execute_record.json").read_text(encoding="utf-8")
    )
    assert execute_record["provider_defaults"] is True
    assert execute_record["transport"]["backend"] == "mlx-serve"
