"""共享 oMLX 门禁客户端与多进程峰值测试（Slice 4.3，worker_03）。

- 真实门禁代码（``omlx_workload_gate.py``）配临时 SQLite 库，不绕过；
- 8 槽容量：第 9 个 wait=False 请求被拒绝；
- 多进程峰值：12 个独立进程同时经门禁执行合成 OCR 请求，实测活跃峰值 == 8，
  证明跨进程真实推理并发不超过 8；
- ``run_under_lease`` 在异常时仍释放租约（finally）。

明确记录本组测试证明与不证明的范围：只证明门禁的跨进程准入上限；不证明
模型身份（无独立服务清单/启动日志）或 provider 准确率/坐标能力。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.evidence.ocr_adapter import InferenceResult
from app.services.omlx_gate import (
    OmlxGateClient,
    OmlxInferenceResponseError,
    omlx_http_inference,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def gate(tmp_path) -> OmlxGateClient:
    return OmlxGateClient(db_path=tmp_path / "gate.sqlite3", owner="test-gate")


def test_acquire_release_and_status(gate) -> None:
    assert gate.status()["active"]["ocr"] == 0
    lease = gate.acquire()
    assert lease.get("lease_id")
    assert gate.status()["active"]["ocr"] == 1
    assert gate.release(lease["lease_id"]) is True
    assert gate.status()["active"]["ocr"] == 0
    # 重复释放返回 False（幂等安全）。
    assert gate.release(lease["lease_id"]) is False


def test_gate_capacity_limited_to_eight(gate) -> None:
    held = []
    for _ in range(8):
        result = gate.acquire(wait=False)
        assert result.get("lease_id"), "前 8 个请求应全部获准"
        held.append(result)
    ninth = gate.acquire(wait=False)
    assert ninth.get("granted") is False
    for lease in held:
        assert gate.release(lease["lease_id"]) is True


def test_run_under_lease_releases_on_inference_failure(gate) -> None:
    def failing_inference(_payload, _image):
        raise RuntimeError("provider down")

    with pytest.raises(RuntimeError):
        gate.run_under_lease(
            failing_inference, request_payload={}, image_bytes=b""
        )
    assert gate.status()["active"]["ocr"] == 0


def test_run_under_lease_returns_result_and_model(gate) -> None:
    def ok_inference(_payload, _image):
        return InferenceResult(
            raw_response='{"choices":[{"message":{"content":"文本"}}]}'.encode(),
            recognized_text="文本",
            verified_coordinates=False,
        )

    result, lease = gate.run_under_lease(
        ok_inference, request_payload={"image": {}}, image_bytes=b""
    )
    assert result.recognized_text == "文本"
    assert lease.get("lease_id")
    assert gate.status()["active"]["ocr"] == 0


def test_run_under_lease_rejects_loss_during_context_exit(gate, monkeypatch) -> None:
    """推理返回后到上下文退出之间丢租约时，结果仍不得泄漏为成功。"""
    from app.services import omlx_gate as gate_module

    original_stop = gate_module._GateHeartbeat.stop

    def stop_and_mark_lost(heartbeat) -> None:
        original_stop(heartbeat)
        heartbeat.lost = True

    monkeypatch.setattr(gate_module._GateHeartbeat, "stop", stop_and_mark_lost)
    with pytest.raises(gate_module.OmlxLeaseLostError):
        gate.run_under_lease(
            lambda _payload, _image: InferenceResult(
                raw_response=b'{"choices":[{"message":{"content":"x"}}]}',
                recognized_text="x",
                verified_coordinates=False,
            ),
            request_payload={},
            image_bytes=b"",
        )
    assert gate.status()["active"]["ocr"] == 0


def test_run_under_lease_fails_when_lease_lost_during_inference(tmp_path) -> None:
    """门禁租约在推理期间被回收：心跳丢失，结果不得返回/接受。"""
    import sqlite3
    import threading
    import time

    from app.services.omlx_gate import OmlxLeaseLostError

    gate = OmlxGateClient(
        db_path=tmp_path / "g3.sqlite3", owner="holder", lease_ttl=3.0
    )
    started = threading.Event()
    release = threading.Event()
    outcome: dict[str, str] = {}

    def blocking_inference(_payload, _image):
        started.set()
        release.wait(timeout=15)
        return InferenceResult(
            raw_response=b'{"choices":[{"message":{"content":"x"}}]}',
            recognized_text="x",
            verified_coordinates=False,
        )

    def run():
        try:
            gate.run_under_lease(
                blocking_inference, request_payload={}, image_bytes=b""
            )
            outcome["returned"] = "unexpected success"
        except OmlxLeaseLostError as exc:
            outcome["lost"] = str(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert started.wait(timeout=10), "推理应已开始"
    # 外部直接删除门禁库租约行，模拟租约被回收/丢失（真实门禁代码的库）。
    conn = sqlite3.connect(tmp_path / "g3.sqlite3")
    conn.execute("DELETE FROM leases")
    conn.commit()
    conn.close()
    time.sleep(1.5)  # 等下一个心跳节拍（ttl/3 = 1s）检测丢失
    release.set()
    thread.join(timeout=15)

    assert "lost" in outcome, f"结果不应被返回/接受：{outcome}"
    assert "returned" not in outcome
    # 租约仍在 finally 释放（行已被外部删除，释放为幂等 no-op，无残留）。
    assert gate.status()["active"]["ocr"] == 0


def test_run_under_lease_rejects_heartbeat_exception(tmp_path, monkeypatch) -> None:
    """门禁心跳本身异常时，后台线程必须把租约标记为不可证明。"""
    import time

    from app.services import omlx_gate as gate_module

    gate = OmlxGateClient(
        db_path=tmp_path / "g-heartbeat-error.sqlite3",
        owner="heartbeat-error",
        lease_ttl=1.0,
    )
    original_heartbeat = gate.heartbeat
    called = {"count": 0}

    def fail_once(lease_id: str, lease_ttl: float | None = None) -> bool:
        called["count"] += 1
        if called["count"] == 1:
            raise RuntimeError("temporary gate database error")
        return original_heartbeat(lease_id, lease_ttl)

    monkeypatch.setattr(gate, "heartbeat", fail_once)

    def inference(_payload, _image):
        time.sleep(1.5)
        return InferenceResult(
            raw_response=b'{"choices":[{"message":{"content":"x"}}]}',
            recognized_text="x",
            verified_coordinates=False,
        )

    with pytest.raises(gate_module.OmlxLeaseLostError):
        gate.run_under_lease(inference, request_payload={}, image_bytes=b"")
    assert called["count"] >= 1
    assert gate.status()["active"]["ocr"] == 0


def test_config_exposes_authoritative_selection(gate) -> None:
    config = gate.config()
    assert config["models"]["ocr"] == "GLM-OCR-bf16"
    assert config["limits"]["ocr"] == 8
    assert config["schema"] == "omlx_gate_selection_v1"


def test_multi_process_peak_probe_le_8(tmp_path) -> None:
    """12 个独立进程同时经真实门禁执行合成 OCR 请求：活跃峰值必须为 8。

    证明门禁跨进程强制 8 路上限（P4-AC05）。每个进程持有租约期间轮询
    ``status()`` 记录最大活跃数；汇总后最大值即峰值。合成请求无 PHI，
    不证明模型身份或 provider 行为。
    """
    gate_db = tmp_path / "gate.sqlite3"
    OmlxGateClient(db_path=gate_db).status()  # 初始化库

    child = (
        "import json, os, sys, time\n"
        f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
        "from app.services.omlx_gate import OmlxGateClient\n"
        "gate_db = sys.argv[1]\n"
        "client = OmlxGateClient(db_path=gate_db, owner='probe-' + str(os.getpid()),\n"
        "                        lease_ttl=30, acquire_timeout=120)\n"
        "result = client.acquire()\n"
        "if not result.get('lease_id'):\n"
        "    print(json.dumps({'granted': False, 'max_active': 0}))\n"
        "    sys.exit(0)\n"
        "lease_id = result['lease_id']\n"
        "max_active = 0\n"
        "deadline = time.monotonic() + 4.0\n"
        "while time.monotonic() < deadline:\n"
        "    status = client.status()\n"
        "    max_active = max(max_active, status['active']['ocr'])\n"
        "    time.sleep(0.05)\n"
        "client.release(lease_id)\n"
        "print(json.dumps({'granted': True, 'max_active': max_active}))\n"
    )

    processes = [
        subprocess.Popen(
            [sys.executable, "-c", child, str(gate_db)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(12)
    ]
    results = []
    for process in processes:
        out, err = process.communicate(timeout=150)
        assert process.returncode == 0, err
        results.append(json.loads(out.strip().splitlines()[-1]))

    granted = [row for row in results if row["granted"]]
    assert len(granted) == 12, f"12 个进程应全部最终获得租约：{results}"
    peaks = [int(row["max_active"]) for row in granted]
    peak = max(peaks)
    # 跨进程实测峰值：必须不超过 8（门禁上限），且达到 8 证明竞争真实存在。
    assert peak <= 8
    assert peak == 8
    assert all(item <= 8 for item in peaks)


def test_omlx_http_inference_builds_request_and_parses(tmp_path, monkeypatch) -> None:
    """最小合成真实调用：经本地假服务器验证请求装配与响应解析。"""
    import base64
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    captured: dict = {}
    # 模拟用户终端存在全局代理、且未配置本机例外。oMLX 调用仍必须直连。
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            captured["body"] = self.rfile.read(length)
            captured["path"] = self.path
            payload = json.loads(captured["body"])
            captured["model"] = payload.get("model")
            captured["max_tokens"] = payload.get("max_tokens")
            captured["temperature"] = payload.get("temperature")
            captured["repetition_penalty"] = payload.get("repetition_penalty")
            content = payload["messages"][0]["content"]
            captured["image_url_prefix"] = content[1]["image_url"]["url"][:22]
            response = json.dumps(
                {
                    "model": "GLM-OCR-bf16",
                    "choices": [{"message": {"content": "识别文本结果"}}],
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format, *args):  # 关闭 HTTP 访问日志
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        gate_client = OmlxGateClient(db_path=tmp_path / "g2.sqlite3")
        inference = omlx_http_inference(url, gate=gate_client)
        request_payload = {
            "prompt": "请逐字识别",
            "request_params": {
                "max_tokens": 3072,
                "temperature": 0,
                "repetition_penalty": 1.15,
            },
            "image": {"mime": "image/png", "data_base64": base64.b64encode(b"\x89PNG").decode("ascii")},
            "page": {"page_number": 1},
        }
        # 最小合成真实 OCR 调用：经共享门禁租约执行（准入/释放由门禁负责）。
        result, _lease = gate_client.run_under_lease(
            inference, request_payload=request_payload, image_bytes=b"\x89PNG"
        )
        assert result.recognized_text == "识别文本结果"
        assert result.verified_coordinates is False
        assert gate_client.status()["active"]["ocr"] == 0  # 调用后已释放
        assert captured["model"] == "GLM-OCR-bf16"
        assert captured["max_tokens"] == 3072
        assert captured["temperature"] == 0
        assert captured["repetition_penalty"] == 1.15
        assert captured["path"].endswith("/v1/chat/completions")
        assert captured["image_url_prefix"].startswith("data:image/png;base64,")
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_omlx_http_inference_uses_shared_runtime_url_by_default(monkeypatch) -> None:
    """应用默认地址必须来自统一配置，不能回落到隔离探针端口。"""
    import app.config as runtime_config
    from app.services import omlx_gate as gate_module

    captured: dict[str, str] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return b'{"model":"GLM-OCR-bf16","choices":[{"message":{"content":"ok"}}]}'

    def fake_direct_open(request, *, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = str(timeout)
        return Response()

    monkeypatch.setattr(runtime_config, "OMLX_BASE_URL", "http://127.0.0.1:8999")
    monkeypatch.setattr(gate_module, "_open_local_service_direct", fake_direct_open)

    inference = omlx_http_inference()
    result = inference({"prompt": "识别", "image": {}}, b"image")

    assert result.recognized_text == "ok"
    assert captured["url"] == "http://127.0.0.1:8999/v1/chat/completions"


def test_omlx_http_inference_rejects_profile_model_drift(monkeypatch) -> None:
    """共享门禁切换模型时，旧 OCRProfile 不得把结果写入旧缓存键。"""
    from app.services import omlx_gate as gate_module

    def unexpected_direct_open(_request, *, timeout):
        raise AssertionError("模型身份漂移应在 HTTP 请求前被拒绝")

    monkeypatch.setattr(
        gate_module, "_open_local_service_direct", unexpected_direct_open
    )
    inference = omlx_http_inference("http://127.0.0.1:8999")
    with pytest.raises(OmlxInferenceResponseError):
        inference(
            {"model_id": "different-model", "prompt": "识别", "image": {}},
            b"image",
        )


@pytest.mark.parametrize(
    "response_body",
    [
        b'{"model":"another-model","choices":[{"message":{"content":"ok"}}]}',
        b'{"model":"GLM-OCR-bf16","choices":[{"message":{"content":""}}]}',
        b'{"model":"GLM-OCR-bf16","choices":[]}',
        b'{"model":"GLM-OCR-bf16","choices":[{"finish_reason":"length","message":{"content":"incomplete"}}]}',
    ],
)
def test_omlx_http_inference_rejects_unverifiable_response(
    monkeypatch, response_body: bytes
) -> None:
    """错模型、空文本和缺失结果均不得进入成功缓存。"""
    from app.services import omlx_gate as gate_module

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return response_body

    monkeypatch.setattr(
        gate_module,
        "_open_local_service_direct",
        lambda _request, *, timeout: Response(),
    )

    inference = omlx_http_inference("http://127.0.0.1:8999")
    with pytest.raises(OmlxInferenceResponseError) as error:
        inference({"prompt": "识别", "image": {}}, b"image")
    assert error.value.raw_response == response_body


def test_omlx_http_inference_classifies_output_truncation(monkeypatch) -> None:
    from app.services import omlx_gate as gate_module
    from app.services.omlx_gate import OmlxOutputTruncatedError

    response_body = (
        b'{"model":"GLM-OCR-bf16","choices":[{"finish_reason":"length",'
        b'"message":{"content":"incomplete"}}]}'
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return response_body

    monkeypatch.setattr(
        gate_module,
        "_open_local_service_direct",
        lambda _request, *, timeout: Response(),
    )

    inference = omlx_http_inference("http://127.0.0.1:8999")
    with pytest.raises(OmlxOutputTruncatedError) as error:
        inference({"prompt": "识别", "image": {}}, b"image")
    assert error.value.raw_response == response_body


def test_runtime_url_discovery_reads_omlx_app_port(tmp_path) -> None:
    from app.config import _discover_omlx_base_url

    config = tmp_path / "config.json"
    config.write_text('{"port": 8123}', encoding="utf-8")
    assert _discover_omlx_base_url(config) == "http://127.0.0.1:8123"

    config.write_text('{"port": 70000}', encoding="utf-8")
    assert _discover_omlx_base_url(config) == "http://127.0.0.1:8000"
