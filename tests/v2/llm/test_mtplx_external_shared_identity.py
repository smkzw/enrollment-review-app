"""外部共享 MTPLX 实例的部署身份与读取会话语义必须一致（2026-09-18 用户裁定）。

未配置产品装卸清单、但端口上已有外部实例在服务所需模型时：
- ``mtplx_deployment_identity`` 登记共享身份（external-shared/v1），不得抛错；
- ``mtplx_deployment_fingerprint`` 稳定派生指纹；
- 端口无实例时仍失败关闭。
"""

from __future__ import annotations

import hashlib
import json

import app.llm.mtplx_model_lifecycle as lifecycle
from app.llm.mtplx_model_lifecycle import (
    MtplxOwnershipError,
    mtplx_deployment_fingerprint,
    mtplx_deployment_identity,
)


def _patch_served_models(monkeypatch, served: list[dict] | None) -> None:
    if served is None:
        monkeypatch.setattr(
            lifecycle, "_external_shared_mtplx_available", lambda base_url, model: False
        )
        return

    def _available(base_url: str, model: str) -> bool:
        if any(item.get("id") == model for item in served):
            return True
        return len(served) == 1

    monkeypatch.setattr(lifecycle, "_external_shared_mtplx_available", _available)


def test_external_shared_instance_registers_shared_identity(monkeypatch):
    monkeypatch.setattr(lifecycle, "configured_mtplx_owner", lambda: None)
    _patch_served_models(monkeypatch, [{"id": "mtplx-qwen36-27b-native-mtp"}])

    identity = mtplx_deployment_identity(
        "mtplx", "http://127.0.0.1:8002/v1", "mtplx-flash-next-optimized-speed", "xhigh"
    )
    assert identity["lifecycle"] == "external-shared/v1"
    assert identity["model"] == "mtplx-flash-next-optimized-speed"
    assert identity["base_url"] == "http://127.0.0.1:8002/v1"
    assert "manifest_sha256" not in identity and "model_path" not in identity

    fingerprint = mtplx_deployment_fingerprint(
        "mtplx", "http://127.0.0.1:8002/v1", "mtplx-flash-next-optimized-speed", "xhigh"
    )
    assert fingerprint == hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_exact_model_match_on_multi_model_port_counts_as_shared(monkeypatch):
    monkeypatch.setattr(lifecycle, "configured_mtplx_owner", lambda: None)
    _patch_served_models(
        monkeypatch,
        [{"id": "mtplx-flash-next-optimized-speed"}, {"id": "other-model"}],
    )
    identity = mtplx_deployment_identity(
        "mtplx", "http://127.0.0.1:8002/v1", "mtplx-flash-next-optimized-speed", "xhigh"
    )
    assert identity["lifecycle"] == "external-shared/v1"


def test_no_external_instance_still_fails_closed(monkeypatch):
    monkeypatch.setattr(lifecycle, "configured_mtplx_owner", lambda: None)
    _patch_served_models(monkeypatch, None)
    try:
        mtplx_deployment_identity(
            "mtplx", "http://127.0.0.1:8002/v1", "mtplx-flash-next-optimized-speed", "xhigh"
        )
    except MtplxOwnershipError:
        pass
    else:
        raise AssertionError("端口无实例时必须失败关闭")


def test_non_mtplx_provider_keeps_empty_identity(monkeypatch):
    monkeypatch.setattr(lifecycle, "configured_mtplx_owner", lambda: None)
    _patch_served_models(monkeypatch, None)
    assert mtplx_deployment_identity("zhipu-coding-plan", "https://example/v1", "glm-5.3-flash", "high") == {}
