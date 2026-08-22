"""Shared oMLX workload gate client（跨进程真实推理额度，Slice 4.3，worker_03）。

全局 8 路 OCR 额度的唯一来源是外部共享门禁脚本
``~/.codex/tools/omlx_workload_gate.py``（SQLite WAL + 租约心跳，跨进程生效）。
本模块把它封装为进程内客户端：

- ``OmlxGateClient`` 加载门禁脚本的 ``WorkloadGate`` 类并按需实例化；
  ``db_path`` 可注入（测试用临时门禁库），生产默认使用门禁自身默认库；
- ``acquire``/``release``/``heartbeat``/``status``/``config`` 对应门禁命令；
- ``acquire_ocr_lease`` 返回可释放的租约句柄；``run_under_lease`` 在
  ``finally`` 释放并心跳（长推理续租），绝不让调用方绕过门禁；
- 门禁不可用（脚本缺失/加载失败）抛 :class:`OmlxGateUnavailableError`，
  执行器按可重试失败处理，绝不绕过门禁直连模型。

模型选择由门禁拥有：调用方不得传模型参数；传入非权威模型会被门禁拒绝。
本模块只做准入协调，不实现任何进程内推理信号量 —— 门禁是唯一并发额度。
"""
from __future__ import annotations

import importlib.util
import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.evidence.ocr_adapter import InferenceResult

#: 门禁脚本默认位置（与实现计划命令一致）。
DEFAULT_GATE_SCRIPT = Path.home() / ".codex" / "tools" / "omlx_workload_gate.py"
#: 证据处理固定 owner；审计时区分来源。
GATE_OWNER = "phase4-evidence-ocr-v2"

GATE_KIND_OCR = "ocr"
DEFAULT_GATE_LEASE_TTL = 180.0
DEFAULT_GATE_ACQUIRE_TIMEOUT = 7200.0


class OmlxGateError(RuntimeError):
    """共享门禁协调错误基类。"""


class OmlxGateUnavailableError(OmlxGateError):
    """门禁脚本缺失或加载失败；执行器必须按可重试失败处理，不得绕过。"""


class OmlxGateCapacityError(OmlxGateError):
    """等待超时仍未取得 OCR 租约（全局额度已满或排队超时）。"""


class OmlxLeaseLostError(OmlxGateError):
    """门禁租约心跳失败（已过期/被回收），本次推理结果不得提交。"""


class OmlxInferenceResponseError(OmlxGateError):
    """oMLX 响应无法证明由门禁指定模型产生，或缺少可用识别文本。"""

    def __init__(self, message: str, *, raw_response: bytes | None = None) -> None:
        super().__init__(message)
        # 即使响应无法被采用，也保留 provider 已返回的原始字节，供上层
        # 以不可变内容寻址工件保存；网络未收到响应时保持 None。
        self.raw_response = raw_response


class OmlxOutputTruncatedError(OmlxInferenceResponseError):
    """识别服务达到输出上限，返回内容不完整。"""


def _load_gate_module(script_path: Path):
    """从脚本路径加载门禁模块（不执行其 ``main``）。"""
    if not script_path.is_file():
        raise OmlxGateUnavailableError(
            f"共享门禁脚本 {script_path} 不存在，无法执行真实识别"
        )
    spec = importlib.util.spec_from_file_location("omlx_workload_gate", script_path)
    if spec is None or spec.loader is None:
        raise OmlxGateUnavailableError(
            f"共享门禁脚本 {script_path} 无法加载"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _GateHeartbeat(threading.Thread):
    """门禁租约心跳线程：每 ``ttl/3`` 秒续租一次；丢失时置位。"""

    def __init__(
        self,
        *,
        heartbeat: Callable[[str, float], bool],
        lease_id: str,
        ttl: float,
    ) -> None:
        super().__init__(daemon=True)
        self._heartbeat = heartbeat
        self._lease_id = lease_id
        self._ttl = ttl
        self._stop_event = threading.Event()
        self.lost = False

    def run(self) -> None:
        interval = min(30.0, max(1.0, self._ttl / 3.0))
        while not self._stop_event.wait(interval):
            try:
                alive = self._heartbeat(self._lease_id, self._ttl)
            except Exception:  # noqa: BLE001 - 心跳异常等价于租约不可证明
                self.lost = True
                return
            if not alive:
                self.lost = True
                return

    def stop(self) -> None:
        self._stop_event.set()
        self.join(timeout=2.0)
        if self.is_alive():
            self.lost = True


@dataclass(frozen=True)
class _HeldOcrLease:
    """门禁租约持有句柄：租约结果 + 心跳线程（``lost`` 供提交前核对）。"""

    result: dict[str, Any]
    heartbeat: _GateHeartbeat


class OmlxGateClient:
    """共享门禁的进程内客户端（跨进程 SQLite 租约，无进程内信号量）。"""

    def __init__(
        self,
        *,
        script_path: Path | str | None = None,
        db_path: Path | str | None = None,
        owner: str = GATE_OWNER,
        lease_ttl: float = DEFAULT_GATE_LEASE_TTL,
        acquire_timeout: float = DEFAULT_GATE_ACQUIRE_TIMEOUT,
    ) -> None:
        self.script_path = Path(script_path) if script_path else DEFAULT_GATE_SCRIPT
        self.db_path = Path(db_path) if db_path is not None else None
        self.owner = owner
        self.lease_ttl = lease_ttl
        self.acquire_timeout = acquire_timeout
        self._module: Any = None

    def _gate(self):
        """按需加载门禁模块并实例化 ``WorkloadGate``（同一进程内复用模块）。"""
        if self._module is None:
            self._module = _load_gate_module(self.script_path)
        gate_cls = getattr(self._module, "WorkloadGate", None)
        if gate_cls is None:
            raise OmlxGateUnavailableError(
                f"门禁脚本 {self.script_path} 缺少 WorkloadGate 类"
            )
        if self.db_path is not None:
            return gate_cls(str(self.db_path))
        return gate_cls()

    # ------------------------------------------------------------- 基础命令

    def acquire(self, *, kind: str = GATE_KIND_OCR, wait: bool = True) -> dict[str, Any]:
        """等待并获取一个门禁租约；超时返回 ``granted=False`` 结果。

        调用方负责在 ``finally`` 释放；模型选择由门禁拥有，调用方不得传入。
        """
        return self._gate().acquire(
            kind,
            self.owner,
            timeout=self.acquire_timeout,
            lease_ttl=self.lease_ttl,
            wait=wait,
        )

    def release(self, lease_id: str) -> bool:
        return self._gate().release(lease_id)

    def heartbeat(self, lease_id: str, lease_ttl: float | None = None) -> bool:
        return self._gate().heartbeat(lease_id, lease_ttl or self.lease_ttl)

    def status(self) -> dict[str, Any]:
        return self._gate().status()

    def config(self) -> dict[str, Any]:
        return self._gate().config()

    # ----------------------------------------------------------- 租约上下文

    @contextmanager
    def ocr_lease(self, *, wait: bool = True) -> Iterator[_HeldOcrLease]:
        """取得一个 OCR 门禁租约并在 ``finally`` 释放（含心跳线程）。

        产出 :class:`_HeldOcrLease`：携带租约结果与心跳线程，调用方在推理后
        必须检查 ``held.heartbeat.lost`` —— 租约在推理期间被回收时结果不得提交。
        """
        result = self.acquire(kind=GATE_KIND_OCR, wait=wait)
        if not result.get("lease_id"):
            raise OmlxGateCapacityError(
                "共享识别通道当前已满或排队超时，本次识别未开始，请稍后重试"
            )
        lease_id = str(result["lease_id"])
        heartbeat = _GateHeartbeat(
            heartbeat=self.heartbeat,
            lease_id=lease_id,
            ttl=self.lease_ttl,
        )
        heartbeat.start()
        body_failed = False
        try:
            yield _HeldOcrLease(result=result, heartbeat=heartbeat)
        except BaseException:
            body_failed = True
            raise
        finally:
            heartbeat.stop()
            self.release(lease_id)
            # ``run_under_lease`` checks immediately after inference, but the
            # heartbeat can lose the lease while the context is unwinding. Do
            # not return a result that became invalid during that last window.
            if heartbeat.lost and not body_failed:
                raise OmlxLeaseLostError(
                    "共享识别租约在推理完成时已丢失，本次结果不得提交"
                )

    def run_under_lease(
        self,
        inference: Callable[[dict[str, Any], bytes], InferenceResult],
        *,
        request_payload: dict[str, Any],
        image_bytes: bytes,
        wait: bool = True,
    ) -> tuple[InferenceResult, dict[str, Any]]:
        """在门禁租约下执行一次真实推理：获取 -> 心跳 -> 推理 -> 释放。

        ``wait=False`` 用于并发/容量测试：满槽时立即抛 :class:`OmlxGateCapacityError`。
        推理前后都核对心跳：租约在等待或推理期间被回收（心跳丢失）时抛
        :class:`OmlxLeaseLostError`，本次结果绝不返回给调用方提交；租约仍在
        ``finally`` 释放。
        """
        with self.ocr_lease(wait=wait) as held:
            if held.heartbeat.lost:
                raise OmlxLeaseLostError(
                    "共享识别租约在排队等待期间已丢失，本次推理未开始，结果不得提交"
                )
            if held.result.get("model") is None:
                held.result["model"] = self.config().get("models", {}).get("ocr")
            result = inference(request_payload, image_bytes)
            if held.heartbeat.lost:
                raise OmlxLeaseLostError(
                    "共享识别租约在推理期间丢失，本次结果不得提交"
                )
            return result, held.result


def gate_config_summary(client: OmlxGateClient | None) -> dict[str, Any]:
    """只读门禁契约摘要（模型选择/额度/库路径），供审计与测试断言。"""
    if client is None:
        return {}
    try:
        return client.config()
    except OmlxGateError:
        return {}


def _open_local_service_direct(request: Any, *, timeout: float) -> Any:
    """打开本机模型服务请求，不继承系统或终端代理。

    oMLX 是同一台 Mac 上的受控本机服务。若沿用 ``HTTP_PROXY``，请求可能被
    错送到外部代理并长期悬挂；显式空代理也避免依赖各终端对 ``NO_PROXY`` 的
    不一致解释。
    """
    import urllib.request

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(request, timeout=timeout)


def omlx_http_inference(
    server_url: str | None = None,
    *,
    gate: OmlxGateClient | None = None,
    timeout: float = 600.0,
    max_tokens: int = 4096,
) -> Callable[[dict[str, Any], bytes], InferenceResult]:
    """生产推理函数工厂：把适配器的请求载荷投递到 oMLX chat 端点。

    返回的推理函数 ``(request_payload, image_bytes) -> InferenceResult`` 供
    执行器在共享门禁租约下调用。模型选择以门禁权威配置为准（调用方不得传参），
    响应原文完整保留为 ``raw_response``；text-only 路线 ``verified_coordinates``
    恒为 False（无真实坐标不画红框）。网络/HTTP 异常向上抛，由执行器按可重试
    失败处理。
    """
    import base64
    import urllib.error
    import urllib.request

    if server_url is None:
        # 生产请求必须与桌面启动器和既有 LLM 客户端共用同一个地址来源。
        # 8002 仅用于 Slice 4.0 的隔离能力探针，不能成为应用运行时默认值。
        from app.config import OMLX_BASE_URL

        server_url = OMLX_BASE_URL
    url = f"{server_url.rstrip('/')}/v1/chat/completions"
    def inference(request_payload: dict[str, Any], image_bytes: bytes) -> InferenceResult:
        authoritative_model = "GLM-OCR-bf16"
        if gate is not None:
            models = gate.config().get("models", {})
            configured_model = models.get("ocr")
            if isinstance(configured_model, str) and configured_model.strip():
                authoritative_model = configured_model
        request_model = request_payload.get("model_id")
        if request_model is not None and request_model != authoritative_model:
            raise OmlxInferenceResponseError(
                "识别配置与共享门禁模型不一致，本次结果未采用"
            )
        prompt = request_payload.get("prompt") or ""
        request_params = request_payload.get("request_params") or {}
        if not isinstance(request_params, dict):
            raise OmlxInferenceResponseError(
                "识别请求参数格式不正确，本次结果未采用"
            )
        effective_max_tokens = int(request_params.get("max_tokens", max_tokens))
        temperature = float(request_params.get("temperature", 0))
        repetition_penalty = float(request_params.get("repetition_penalty", 1.15))
        image = request_payload.get("image") or {}
        mime = image.get("mime") or "image/png"
        data_base64 = image.get("data_base64")
        if data_base64 is None:
            data_base64 = base64.b64encode(image_bytes).decode("ascii")
        body = json.dumps(
            {
                "model": authoritative_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{data_base64}"
                                },
                            },
                        ],
                    }
                ],
                "max_tokens": effective_max_tokens,
                "temperature": temperature,
                "repetition_penalty": repetition_penalty,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer local",
            },
            method="POST",
        )
        try:
            with _open_local_service_direct(request, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            try:
                raw_error = exc.read()
            except Exception:  # noqa: BLE001 - 响应体读取失败仍需稳定失败
                raw_error = None
            raise OmlxInferenceResponseError(
                "识别服务返回错误，本次结果未采用",
                raw_response=raw_error,
            ) from exc
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OmlxInferenceResponseError(
                "识别服务返回格式异常，本次结果未采用",
                raw_response=raw,
            ) from exc
        if not isinstance(parsed, dict):
            raise OmlxInferenceResponseError(
                "识别服务返回格式异常，本次结果未采用",
                raw_response=raw,
            )
        response_model = parsed.get("model")
        if response_model != authoritative_model:
            raise OmlxInferenceResponseError(
                "识别服务返回的模型身份与本次识别配置不一致，本次结果未采用",
                raw_response=raw,
            )
        choices = parsed.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise OmlxInferenceResponseError(
                "识别服务返回内容不完整，本次结果未采用",
                raw_response=raw,
            )
        if choices[0].get("finish_reason") == "length":
            raise OmlxOutputTruncatedError(
                "本页识别内容未完整返回，请重新识别",
                raw_response=raw,
            )
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise OmlxInferenceResponseError(
                "识别服务返回内容不完整，本次结果未采用",
                raw_response=raw,
            )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise OmlxInferenceResponseError(
                "识别服务未返回可用文字，本次结果未采用",
                raw_response=raw,
            )
        return InferenceResult(
            raw_response=raw,
            recognized_text=content,
            verified_coordinates=False,
        )

    return inference
