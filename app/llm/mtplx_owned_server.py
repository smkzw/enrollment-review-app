"""Explicit MTPLX ownership with per-user product-process admission.

This driver does not discover models, stop existing servers, or allocate a
second workload queue. The product lock excludes other participating product
processes, not unrelated applications or delayed GPU resource reclamation.
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import re
import socket
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
from uuid import uuid4

import httpx


class MtplxOwnershipError(RuntimeError):
    pass


class MtplxShutdownIncomplete(MtplxOwnershipError):
    """Keep admission held until process, port and resource release checks pass."""

    def __init__(self, pid: int):
        self.pid = pid
        super().__init__("模型服务尚未确认退出，不能加载下一个模型")


class MtplxMemoryReleaseIncomplete(MtplxShutdownIncomplete):
    def __init__(self, pid: int):
        super().__init__(pid)
        self.args = ("前一模型退出后内存尚未恢复，暂不加载下一模型；其他应用不会被关闭",)


@dataclass(frozen=True)
class MtplxServerSpec:
    executable: Path
    model_path: Path
    model_id: str
    base_url: str
    effort: str
    log_directory: Path
    max_tokens: int = 131072
    startup_seconds: float = 600
    shutdown_seconds: float = 30

    def endpoint(self) -> tuple[str, int]:
        parsed = urlsplit(self.base_url)
        if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
                or parsed.path.rstrip("/") != "/v1" or parsed.query
                or parsed.fragment or parsed.username or parsed.password
                or parsed.port is None):
            raise MtplxOwnershipError("自动启动仅支持明确配置的本机 MTPLX 地址")
        return parsed.hostname, parsed.port

    def command(self, launch_id: str) -> list[str]:
        host, port = self.endpoint()
        if (not self.executable.is_absolute() or not self.executable.is_file()
                or not self.model_path.is_absolute() or not self.model_path.is_dir()
                or not self.model_id.strip()):
            raise MtplxOwnershipError("请明确配置已安装的 MTPLX 程序和模型目录")
        if self.effort not in {"low", "medium", "high", "xhigh"}:
            raise MtplxOwnershipError("配置的思考档位不能原样传给 MTPLX")
        if not 65536 <= self.max_tokens <= 131072:
            raise MtplxOwnershipError("模型输出额度不符合当前配置要求")
        if self.startup_seconds <= 0 or self.shutdown_seconds <= 0:
            raise MtplxOwnershipError("模型启动和释放等待时间必须大于零")
        return [str(self.executable), "serve", "--model", str(self.model_path),
                "--model-id", self.model_id, "--host", host, "--port", str(port),
                "--scheduler-mode", "serial", "--max-active-requests", "1",
                "--reasoning-effort", self.effort, "--max-tokens", str(self.max_tokens),
                "--no-stats-footer", "--app-launch-id", launch_id]


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.2)
        return probe.connect_ex((host, port)) == 0


def _system_memory_snapshot() -> dict:
    """Best-effort system counters, not model attribution or an admission rule."""
    if sys.platform != "darwin":
        return {"status": "unavailable"}
    try:
        result = subprocess.run(["/usr/bin/vm_stat"], capture_output=True,
                                text=True, check=True, timeout=1)
        page_size = re.search(r"page size of (\d+) bytes", result.stdout)
        if page_size is None:
            return {"status": "unavailable"}
        counters = {}
        names = {"Pages free": "free_bytes", "Pages wired down": "wired_bytes",
                 "Pages occupied by compressor": "compressor_bytes"}
        for line in result.stdout.splitlines():
            key, separator, value = line.partition(":")
            if separator and key in names:
                counters[names[key]] = int(value.strip().rstrip(".")) * int(page_size[1])
        return {"status": "observed" if counters else "unavailable",
                "scope": "whole_system", "unix_time": time.time(), **counters}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"status": "unavailable"}


def _group_alive(process: subprocess.Popen) -> bool:
    process.poll()
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Darwin may deny the probe during teardown; confirm with process inventory.
        result = subprocess.run(["/bin/ps", "-axo", "pgid="],
                                capture_output=True, text=True, check=True, timeout=5)
        return process.pid in {int(line.strip()) for line in result.stdout.splitlines()
                               if line.strip()}
    return True


async def _stop_owned(process: subprocess.Popen, timeout: float) -> None:
    # The Popen handle, never a PID discovered from a port, establishes ownership.
    if _group_alive(process):
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + timeout
    while _group_alive(process) and time.monotonic() < deadline:
        await asyncio.sleep(0.1)
    if _group_alive(process):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + timeout
        while _group_alive(process) and time.monotonic() < deadline:
            await asyncio.sleep(0.1)
        if _group_alive(process):
            raise MtplxShutdownIncomplete(process.pid)


async def _finish_cleanup(process: subprocess.Popen, timeout: float) -> None:
    cleanup = asyncio.create_task(_stop_owned(process, timeout))
    cancelled = False
    while not cleanup.done():
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            cancelled = True
    cleanup.result()
    if cancelled:
        raise asyncio.CancelledError


@dataclass
class OwnedMtplxServer:
    """A process handle, not an event-loop-owned context or a hardware lease.

    A single caller must serialize access and retain this handle until stop has
    confirmed exit. It can outlive an asyncio.run call without being closed by
    that loop's asynchronous-generator shutdown.
    """

    spec: MtplxServerSpec
    launch_id: str
    process: subprocess.Popen
    admission_fd: int | None = None
    wired_before_start: int | None = None
    released: bool = False

    def _record_lifecycle(self, event: str) -> None:
        record = {"event": event, "unix_time": time.time(),
                  "monotonic": time.monotonic(), "pid": self.process.pid,
                  "launch_id": self.launch_id, "model": self.spec.model_id,
                  "returncode": self.process.poll(),
                  "release_policy": "memory-settle/v1",
                  "wired_before_start": self.wired_before_start,
                  "system_memory": _system_memory_snapshot()}
        try:
            with (self.spec.log_directory / f"{self.launch_id}.lifecycle.jsonl").open("a") as stream:
                stream.write(json.dumps(record) + "\n")
        except OSError:
            # Diagnostics must never prevent releasing the owned process.
            logging.getLogger(__name__).warning("Unable to record model lifecycle pid=%s", self.process.pid)

    @classmethod
    def start(cls, spec: MtplxServerSpec) -> OwnedMtplxServer:
        launch_id = f"enrollment-{uuid4().hex}"
        command = spec.command(launch_id)
        host, port = spec.endpoint()
        lock_path = Path(tempfile.gettempdir()) / f"enrollment-mtplx-{os.getuid()}.lock"
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise MtplxOwnershipError("另一个入排审核进程正在使用本地模型，请等待其释放") from exc
            if _port_in_use(host, port):
                raise MtplxOwnershipError("模型端口已被其他服务使用，未替换或关闭已有服务")
            before = _system_memory_snapshot()
            baseline = before.get("wired_bytes")
            if sys.platform == "darwin" and baseline is None:
                raise MtplxOwnershipError("暂时无法核对本机内存，未加载模型，请稍后重试")
            spec.log_directory.mkdir(parents=True, exist_ok=True)
            with (spec.log_directory / f"{launch_id}.log").open("xb") as log:
                # Inheritance protects parent exit only while the CLI keeps this fd.
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                           stdout=log, stderr=subprocess.STDOUT,
                                           start_new_session=True, pass_fds=(fd,))
        except BaseException:
            os.close(fd)
            raise
        server = cls(spec=spec, launch_id=launch_id, process=process, admission_fd=fd,
                     wired_before_start=baseline)
        server._record_lifecycle("started")
        return server

    def _verify_health(self, health) -> dict:
        if self.process.poll() is not None:
            raise MtplxOwnershipError("模型服务已退出，未发送资料")
        startup = health.get("startup", {}) if isinstance(health, dict) else {}
        if (not isinstance(startup, dict) or startup.get("pid") != self.process.pid
                or startup.get("launch_id") != self.launch_id):
            raise MtplxOwnershipError("服务身份与本次启动不一致，未发送资料")
        if (health.get("ok") is not True or health.get("model") != self.spec.model_id
                or Path(str(health.get("model_path", ""))).resolve() != self.spec.model_path.resolve()
                or not isinstance(health.get("vision"), dict)
                or health["vision"].get("enabled") is not True):
            raise MtplxOwnershipError("实际模型或图像读取能力与配置不一致")
        return health

    async def ready(self) -> dict:
        """Verify readiness; failed/cancelled startup still owns its process."""
        host, port = self.spec.endpoint()
        try:
            deadline = time.monotonic() + self.spec.startup_seconds
            api_key = os.environ.get("MTPLX_API_KEY", "").strip()
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            async with httpx.AsyncClient(trust_env=False, timeout=3, headers=headers) as client:
                while True:
                    if self.process.poll() is not None:
                        raise MtplxOwnershipError("模型服务启动失败，已保留启动记录")
                    if time.monotonic() >= deadline:
                        raise MtplxOwnershipError("模型未在配置的等待时间内就绪")
                    try:
                        response = await client.get(f"http://{host}:{port}/health")
                        if response.status_code in {401, 403}:
                            raise MtplxOwnershipError("模型服务拒绝产品配置的凭据，未发送资料")
                        response.raise_for_status()
                        health = response.json()
                    except (httpx.HTTPError, ValueError):
                        await asyncio.sleep(0.5)
                        continue
                    return self._verify_health(health)
        except BaseException:
            await self.stop()
            raise

    async def stop(self) -> None:
        if self.released:
            return
        port_released = False
        self._record_lifecycle("stop_requested")
        try:
            await _finish_cleanup(self.process, self.spec.shutdown_seconds)
            host, port = self.spec.endpoint()
            deadline = time.monotonic() + self.spec.shutdown_seconds
            while _port_in_use(host, port):
                if time.monotonic() >= deadline:
                    raise MtplxShutdownIncomplete(self.process.pid)
                await asyncio.sleep(0.1)
            self._record_lifecycle("process_and_port_exited")
            if self.wired_before_start is not None:
                # Process exit can precede Metal memory reclamation. This is a
                # conservative system-level check, not attribution to a model.
                deadline = time.monotonic() + self.spec.shutdown_seconds
                stable = 0
                while stable < 2:
                    memory = await asyncio.to_thread(_system_memory_snapshot)
                    wired = memory.get("wired_bytes")
                    stable = (stable + 1 if wired is not None
                              and wired <= self.wired_before_start + 1024 ** 3 else 0)
                    if stable == 2:
                        break
                    if time.monotonic() >= deadline:
                        raise MtplxMemoryReleaseIncomplete(self.process.pid)
                    await asyncio.sleep(0.25)
            port_released = True
            self._record_lifecycle("process_group_and_port_released")
        except MtplxMemoryReleaseIncomplete:
            self._record_lifecycle("memory_settle_incomplete")
            raise
        except MtplxShutdownIncomplete:
            self._record_lifecycle("shutdown_incomplete")
            raise
        finally:
            if port_released and not _group_alive(self.process):
                if self.admission_fd is not None:
                    os.close(self.admission_fd)
                    self.admission_fd = None
                self.released = True


@asynccontextmanager
async def owned_mtplx_server(spec: MtplxServerSpec):
    """Bounded-use wrapper; persistent callers retain OwnedMtplxServer instead."""
    server = OwnedMtplxServer.start(spec)
    try:
        yield await server.ready()
    finally:
        await server.stop()
