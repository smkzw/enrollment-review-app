"""Product-owned serial MTPLX residency, shared by synchronous and async callers.

Only an explicit product manifest enables process management. This is a mutex
around the existing transports, not another job queue or an OCR service gate.
Unowned services are never stopped. Other applications remain outside this lock.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
import hashlib
import json
import os
from pathlib import Path
import threading

from app.llm.mtplx_owned_server import MtplxOwnershipError, MtplxServerSpec, OwnedMtplxServer


def _explicitly_rejected(exc: BaseException) -> bool:
    # An explicit rejection can retry warm. Unknown transport outcomes may
    # still be generating; stop those before another request takes ownership.
    return getattr(exc, "status_code", None) in {400, 401, 403, 404, 422, 429}


class MtplxModelOwner:
    def __init__(self, specs: dict[str, MtplxServerSpec], *, manifest_sha256: str = ""):
        if not specs:
            raise MtplxOwnershipError("未配置本产品可以加载的模型")
        if len({spec.base_url.rstrip('/') for spec in specs.values()}) != 1:
            raise MtplxOwnershipError("串行模型必须共用同一个明确的本机地址")
        self.specs = dict(specs)
        self.manifest_sha256 = manifest_sha256
        self.lock = threading.Lock()
        self.current: OwnedMtplxServer | None = None
        self.closing = False

    def spec(self, base_url: str, model: str, effort: str) -> MtplxServerSpec:
        spec = self.specs.get(model)
        if spec is None or (spec.base_url.rstrip('/'), spec.effort) != (base_url.rstrip('/'), effort):
            raise MtplxOwnershipError("本次模型、地址或思考档位与产品加载配置不一致")
        return spec

    async def _release(self):
        if self.current is not None:
            # Retain the handle on failed shutdown; never start a replacement then.
            await self.current.stop()
            self.current = None

    async def _prepare(self, spec):
        if self.closing:
            raise MtplxOwnershipError("模型服务正在释放，本次未开始新的读取")
        if self.current is not None and self.current.spec != spec:
            await self._release()
        if self.current is not None and self.current.process.poll() is not None:
            await self._release()
        if self.current is None:
            self.current = OwnedMtplxServer.start(spec)
        return await self.current.ready()

    @asynccontextmanager
    async def session(self, base_url: str, model: str, effort: str):
        spec = self.spec(base_url, model, effort)
        while not self.lock.acquire(blocking=False):
            await asyncio.sleep(0.05)
        try:
            health = await self._prepare(spec)
            yield health
        except BaseException as exc:
            if not _explicitly_rejected(exc):
                await self._release()
            raise
        finally:
            self.lock.release()

    @contextmanager
    def sync_session(self, base_url: str, model: str, effort: str):
        spec = self.spec(base_url, model, effort)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise MtplxOwnershipError("同步模型任务须在后台工作线程执行")
        with self.lock:
            try:
                health = asyncio.run(self._prepare(spec))
                yield health
            except BaseException as exc:
                if not _explicitly_rejected(exc):
                    asyncio.run(self._release())
                raise

    async def close(self):
        self.closing = True
        while not self.lock.acquire(blocking=False):
            await asyncio.sleep(0.05)
        try:
            await self._release()
        finally:
            self.lock.release()


_configuration_lock = threading.Lock()
_owner: MtplxModelOwner | None = None
_identity: tuple[str, str] | None = None


def configured_mtplx_owner() -> MtplxModelOwner | None:
    global _owner, _identity
    configured = os.environ.get("ENROLLMENT_MTPLX_MODELS_FILE", "").strip()
    with _configuration_lock:
        if not configured:
            if _owner is not None:
                raise MtplxOwnershipError("模型加载设置在运行中被移除，请先正常关闭应用")
            return None
        path = Path(configured)
        if not path.is_absolute():
            raise MtplxOwnershipError("产品模型加载配置必须使用完整路径")
        raw = path.read_bytes()
        identity = (str(path.resolve()), hashlib.sha256(raw).hexdigest())
        if _owner is not None:
            if identity != _identity:
                raise MtplxOwnershipError("模型加载设置已改变，请先正常关闭应用再重新启动")
            return _owner
        data = json.loads(raw)
        if (not isinstance(data, dict) or data.get("version") != 1
                or not isinstance(data.get("models"), list)):
            raise MtplxOwnershipError("产品模型加载配置格式不完整")
        specs = {}
        for item in data["models"]:
            spec = MtplxServerSpec(
                executable=Path(data["executable"]), model_path=Path(item["path"]),
                model_id=item["model"], base_url=data["base_url"], effort=item["effort"],
                log_directory=Path(data["log_directory"]),
                max_tokens=data.get("max_tokens", 131072),
            )
            spec.command("configuration-check")
            if not spec.log_directory.is_absolute() or spec.model_id in specs:
                raise MtplxOwnershipError("模型配置重复或记录目录不是完整路径")
            specs[spec.model_id] = spec
        _owner = MtplxModelOwner(specs, manifest_sha256=identity[1])
        _identity = identity
        return _owner



def _external_shared_mtplx_available(base_url: str, model: str) -> bool:
    """端口上已有同模型的外部 MTPLX 实例时，允许直接多路复用（不做装卸声明）。

    MTPLX 是 OpenAI 兼容服务，天然支持多客户端；属主串行模式只为产品自己
    启动/卸载模型时防并发加载。外部实例存在且在服务所需模型时，消费它比
    要求用户关闭它更符合“本地共享资源”的现实（2026-09-18 用户裁定）。
    """
    import urllib.request

    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/models", timeout=5) as r:
            served = json.load(r).get("data", [])
        if any(item.get("id") == model for item in served):
            return True
        # 专用本地运行时通常只装一个模型：唯一在服务的模型即无歧义目标。
        return len(served) == 1
    except (OSError, ValueError):
        return False


@asynccontextmanager
async def mtplx_model_session(provider: str, base_url: str, model: str, effort: str):
    if provider in {"mtplx", "mtplx-api"}:
        try:
            owner = configured_mtplx_owner()
        except MtplxOwnershipError:
            owner = None
        if owner is not None:
            try:
                async with owner.session(base_url, model, effort) as health:
                    yield health
                return
            except MtplxOwnershipError:
                pass
        if _external_shared_mtplx_available(base_url, model):
            import logging

            logging.getLogger(__name__).info(
                "MTPLX 端口已有同模型外部实例，按多路调用直接复用（不做装卸声明）"
            )
            yield None
            return
        raise MtplxOwnershipError(
            "尚未配置本系统的模型装卸清单，且端口上没有在服务所需模型的实例，暂未开始读取"
        )
    yield None


@contextmanager
def sync_mtplx_model_session(provider: str, base_url: str, model: str, effort: str):
    if provider in {"mtplx", "mtplx-api"}:
        try:
            owner = configured_mtplx_owner()
        except MtplxOwnershipError:
            owner = None
        if owner is not None:
            try:
                with owner.sync_session(base_url, model, effort) as health:
                    yield health
                return
            except MtplxOwnershipError:
                pass
        if _external_shared_mtplx_available(base_url, model):
            import logging

            logging.getLogger(__name__).info(
                "MTPLX 端口已有同模型外部实例，按多路调用直接复用（不做装卸声明）"
            )
            yield None
            return
        raise MtplxOwnershipError(
            "尚未配置本系统的模型装卸清单，且端口上没有在服务所需模型的实例，暂未开始读取"
        )
    yield None


async def close_owned_mtplx_models():
    global _owner, _identity
    with _configuration_lock:
        owner = _owner
    if owner is not None:
        await owner.close()
        with _configuration_lock:
            if _owner is owner:
                _owner = None
                _identity = None


def mtplx_deployment_identity(provider: str, base_url: str, model: str, effort: str) -> dict:
    """Public deployment identity; never loads a model or reads credentials."""
    owner = configured_mtplx_owner() if provider in {"mtplx", "mtplx-api"} else None
    if provider in {"mtplx", "mtplx-api"} and owner is None:
        # 与 mtplx_model_session 一致：端口上已有外部实例在服务所需模型时，
        # 按多路调用登记共享身份（2026-09-18 用户裁定），不做装卸声明。
        if _external_shared_mtplx_available(base_url, model):
            return {
                "lifecycle": "external-shared/v1",
                "base_url": base_url.rstrip("/"),
                "model": model,
            }
        raise MtplxOwnershipError(
            "尚未配置本系统的模型装卸清单，且端口上没有在服务所需模型的实例，暂未开始读取"
        )
    if owner is None:
        return {}
    spec = owner.spec(base_url, model, effort)
    return {"manifest_sha256": owner.manifest_sha256, "model_path": str(spec.model_path.resolve()),
            "lifecycle": "owned-serial/v1"}


def mtplx_deployment_fingerprint(provider: str, base_url: str, model: str, effort: str) -> str | None:
    identity = mtplx_deployment_identity(provider, base_url, model, effort)
    if not identity:
        return None
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def local_deployment_job_fields() -> dict[str, str]:
    owner = configured_mtplx_owner()
    return {} if owner is None else {"local_model_manifest_sha256": owner.manifest_sha256}


def require_local_deployment_job(payload) -> None:
    expected = local_deployment_job_fields().get("local_model_manifest_sha256")
    if payload.get("local_model_manifest_sha256") != expected:
        raise MtplxOwnershipError("模型加载配置与任务建立时不同，请新建任务，历史结果仍保留")
