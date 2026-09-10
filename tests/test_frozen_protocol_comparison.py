"""冻结方案解构横评入口的离线测试（无任何模型调用）。

覆盖：

- 输出预算守卫：低于 65536 tokens 必须在发送前显式拒绝；
- 传输配置：不支持的后端显式失败，不伪装成其他供应商；未配置凭据的
  受支持后端也显式失败；
- 准备/执行分离：真实产品链冻结原始 DOCX 后显式停止，执行阶段校验
  哈希并复用生产执行器继续至审阅边界；
- 边界守卫：拒绝已存在目录、来源/输出重叠、非 DOCX、未准备的运行目录；
- 回执导出：使用产品传输自带 ``history`` 钩子导出会话请求/响应正文。

离线路径通过脚本函数参数注入测试执行器覆盖（页面文本构造器 / 草稿
响应构造器）；CLI 路径从不注入。全程不访问网络、不调用模型。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

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


def _execute_prepared(run_dir: Path, **overrides) -> dict:
    kwargs: dict = {
        "run_dir": run_dir,
        "backend": "deepseek",
        "max_tokens": 65536,
        "transport": object(),
        "transport_factory": lambda: object(),
        "now": lambda: NAIVE_NOW,
        "executor_overrides": {"draft_response_builder": build_passing_draft_json},
    }
    kwargs.update(overrides)
    return comparison.execute(**kwargs)


def test_output_budget_guard_requires_65536() -> None:
    with pytest.raises(comparison.ComparisonGuardError, match="65536"):
        comparison.resolve_output_budget("deepseek", 60000)
    assert comparison.resolve_output_budget("deepseek", 65536) == 65536
    assert comparison.resolve_output_budget("deepseek", None) >= 65536

    cap = comparison.MTPLX_PROTOCOL_BATCH_MAX_TOKENS
    if cap < comparison.MIN_BENCHMARK_MAX_TOKENS:
        with pytest.raises(
            comparison.ComparisonGuardError, match="MTPLX_PROTOCOL_BATCH_MAX_TOKENS"
        ):
            comparison.resolve_output_budget("mtplx", 65536)
    else:
        assert comparison.resolve_output_budget("mtplx", 65536) == min(65536, cap)


def test_native_call_receipt_preserves_request_usage_and_failure(tmp_path: Path) -> None:
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise TimeoutError("offline")
        return SimpleNamespace(model_dump=lambda **_: {
            "model": "actual-model", "usage": {"completion_tokens": 7},
            "choices": [{"finish_reason": "stop"}],
        })

    transport = SimpleNamespace(_client=SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    comparison._record_calls(transport, tmp_path, [0])
    invoke = transport._client.chat.completions.create
    with pytest.raises(comparison.ComparisonGuardError):
        invoke(max_tokens=12000)
    assert calls == []
    request = {"max_tokens": 65536, "messages": [{"role": "user", "content": "fixture"}], "temperature": 0.1}
    invoke(**request)
    assert json.loads((tmp_path / "request-0000.json").read_text()) == request
    assert json.loads((tmp_path / "receipt-0000.json").read_text())["usage"] == {"completion_tokens": 7}
    with pytest.raises(TimeoutError):
        invoke(**request)
    assert json.loads((tmp_path / "receipt-0001.json").read_text())["failure_type"] == "TimeoutError"
    assert comparison._collect_session_ids([{"attempts": [{"session_id": "s"}]}]) == ["s"]


def test_unsupported_backend_fails_explicitly_without_masquerade() -> None:
    with pytest.raises(comparison.ComparisonGuardError, match="not-a-real-provider"):
        comparison.build_transport("not-a-real-provider", max_tokens=65536)


def test_unconfigured_supported_backend_fails_explicitly(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.agents.protocol_semantic_transport.DEEPSEEK_API_KEY", ""
    )
    with pytest.raises(comparison.ComparisonGuardError, match="尚未配置"):
        comparison.build_transport("deepseek", max_tokens=65536)


def test_prepare_rejects_non_docx(tmp_path: Path) -> None:
    pdf = tmp_path / "protocol.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    with pytest.raises(comparison.ComparisonGuardError, match="DOCX"):
        comparison.prepare(
            run_dir=tmp_path / "run",
            protocol_path=pdf,
            study_phase=StudyPhase.PHASE_II,
            now=lambda: NAIVE_NOW,
        )


def test_prepare_rejects_source_output_overlap(tmp_path: Path) -> None:
    source_root = tmp_path / "out" / "in"
    source_root.mkdir(parents=True)
    docx = source_root / "protocol.docx"
    build_pipeline_e2e_docx(docx)
    with pytest.raises(comparison.ComparisonGuardError, match="重叠"):
        comparison.prepare(
            run_dir=tmp_path / "out",
            protocol_path=docx,
            study_phase=StudyPhase.PHASE_II,
            now=lambda: NAIVE_NOW,
        )
    assert not (tmp_path / "out" / "data_v2").exists()


def test_execute_requires_prepared_run_dir(tmp_path: Path) -> None:
    with pytest.raises(comparison.ComparisonGuardError, match="prepare"):
        comparison.execute(
            run_dir=tmp_path / "missing",
            backend="deepseek",
            max_tokens=65536,
            now=lambda: NAIVE_NOW,
        )


def test_prepare_then_execute_offline_end_to_end(
    tmp_path: Path, protocol_docx: Path
) -> None:
    run_dir = tmp_path / "run"
    record = _prepare(run_dir, protocol_docx)

    assert record["job_state_after_prepare"] in {"failed", "failed_final"}
    assert record["stopped_after"] == "generate_draft"
    assert record["stop_error_code"] == comparison.STOP_ERROR_CODE
    assert record["snapshot_id"]
    assert record["content_sha256"]
    assert record["verification"]["source_file_unchanged"] is True
    assert record["confirmed"]["study_phase"] == StudyPhase.PHASE_II.value

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["protocol_job_id"] == record["protocol_job_id"]
    assert manifest["content_sha256"] == record["content_sha256"]
    assert manifest["claims_complete"] is False
    assert manifest["clinical_acceptance"] is False

    # 拒绝复用已存在的运行目录。
    with pytest.raises(comparison.ComparisonGuardError, match="已存在"):
        _prepare(run_dir, protocol_docx)

    # 预算不足必须在发送前拒绝，且不留下执行输出目录。
    with pytest.raises(comparison.ComparisonGuardError, match="65536"):
        comparison.execute(
            run_dir=run_dir,
            backend="deepseek",
            max_tokens=60000,
            now=lambda: NAIVE_NOW,
        )
    assert not (run_dir / "execute").exists()

    cap = comparison.MTPLX_PROTOCOL_BATCH_MAX_TOKENS
    if cap < comparison.MIN_BENCHMARK_MAX_TOKENS:
        with pytest.raises(
            comparison.ComparisonGuardError, match="MTPLX_PROTOCOL_BATCH_MAX_TOKENS"
        ):
            comparison.execute(
                run_dir=run_dir, backend="mtplx", now=lambda: NAIVE_NOW
            )
        assert not (run_dir / "execute").exists()

    executed = _execute_prepared(run_dir)
    assert executed["outcome"]["awaiting_user"] == "review"
    assert executed["outcome"]["job_state"] == "waiting_user"
    assert executed["outcome"]["draft_id"]
    assert executed["outcome"]["draft_revision_id"]
    assert executed["budget"]["effective"] == 65536
    assert executed["budget"]["enforced_before_send"] is True
    assert executed["verification"]["source_blob_sha256"] is True
    assert executed["verification"]["content_blob_sha256"] is True
    assert executed["verification"]["prompt_template_unchanged"] is True
    assert executed["executor_overrides_used"] is True
    # 草稿响应构造器是离线测试注入路径，不产生语义路由审计。
    assert executed["route_audit"] is None
    execute_record = json.loads(
        (run_dir / "execute" / "execute_record.json").read_text(encoding="utf-8")
    )
    assert execute_record["outcome"]["awaiting_user"] == "review"
    assert execute_record["claims_complete"] is False

    # 拒绝在既有运行目录上重复执行。
    with pytest.raises(comparison.ComparisonGuardError, match="已存在"):
        _execute_prepared(run_dir)


def test_history_receipt_dump_uses_product_history_hook(tmp_path: Path) -> None:
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace())
    )

    def create(**kwargs):
        client.chat.completions.last_kwargs = kwargs
        message = SimpleNamespace(content='{"ok": true}', reasoning_content="")
        choice = SimpleNamespace(message=message, finish_reason="stop")
        return SimpleNamespace(choices=[choice])

    client.chat.completions.create = create

    transport = DeepSeekProtocolAgentTransport(
        backend="omlx",
        client=client,
        max_tokens=max(65536, comparison.OMLX_PROTOCOL_BATCH_MAX_TOKENS),
    )
    response = transport.start(prompt='{"request": true}')

    receipts_dir = tmp_path / "receipts"
    written = comparison._dump_transport_histories(
        [transport],
        [response.session_id, "session-not-in-this-transport"],
        receipts_dir,
    )
    assert len(written) == 1
    # 返回路径相对 receipts_dir.parents[1]（执行流程中即 run_dir）。
    receipt_path = receipts_dir.parents[1] / written[0]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["session_id"] == response.session_id
    assert receipt["messages"][0] == {"role": "user", "content": '{"request": true}'}
    assert receipt["messages"][-1] == {
        "role": "assistant",
        "content": '{"ok": true}',
    }
    assert receipt["output_budget_enforced"] is True
