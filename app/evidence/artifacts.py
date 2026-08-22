"""不可变内容寻址工件存储（Slice 4.3，worker_02）。

页图、原生文本、原生坐标、原始 OCR 请求与原始 OCR 响应必须分开保存且不可变：
本存储以 ``artifacts/<kind>/<sha256>`` 的可移植存储引用落盘，同一字节内容只写
一次（幂等去重），读取时按哈希复核内容。存储引用不暴露本机绝对路径，
与 ``SourceBlob`` 的 ``blobs/<sha256>`` 约定一致（见 ``evidence_upload_service``）。

写入走 ``WriteBoundary.atomic_write_bytes``（同目录临时文件 + 原子替换），
任何目标不在 V2 数据根内或触碰受保护旧目录都会抛 ``ProtectedPathError``。
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from app.storage.boundaries import WriteBoundary
from app.storage.config import DataPaths

#: 工件类别与契约字段一一对应（分开保存、互不混淆）。
ARTIFACT_KINDS = frozenset(
    {"page_image", "native_text", "native_coordinates", "raw_request", "raw_response"}
)

#: 工件目录相对 V2 数据根；与 blobs/、staging/ 平级，互不重叠。
ARTIFACTS_DIRNAME = "artifacts"


class ArtifactStoreError(RuntimeError):
    """工件存储领域错误基类。"""


class UnknownArtifactKindError(ArtifactStoreError):
    """未知工件类别，拒绝写入/读取。"""


class ArtifactIntegrityError(ArtifactStoreError):
    """已存工件内容与引用哈希不一致（读取复核失败）。"""


@dataclass(frozen=True)
class StoredArtifact:
    """一次内容寻址写入的结果引用。"""

    kind: str
    sha256: str
    byte_size: int
    storage_ref: str


class ArtifactStore:
    """V2 数据根内的不可变内容寻址工件库。"""

    def __init__(self, data_paths: DataPaths) -> None:
        self.data_paths = data_paths
        self.boundary: WriteBoundary = data_paths.boundary

    def _require_kind(self, kind: str) -> None:
        if kind not in ARTIFACT_KINDS:
            raise UnknownArtifactKindError(
                f"未知工件类别 {kind!r}，允许类别：{sorted(ARTIFACT_KINDS)}"
            )

    def put(self, kind: str, payload: bytes) -> StoredArtifact:
        """内容寻址写入：同内容幂等去重，不同内容不覆盖既有字节。

        以内容 SHA-256 为身份；先写字节再复核（写失败不留下半成品，原子替换）。
        """
        self._require_kind(kind)
        digest = sha256(payload).hexdigest()
        target = self.data_paths.root / ARTIFACTS_DIRNAME / kind / digest
        self.boundary.atomic_write_bytes(target, payload)
        return StoredArtifact(
            kind=kind,
            sha256=digest,
            byte_size=len(payload),
            storage_ref=f"{ARTIFACTS_DIRNAME}/{kind}/{digest}",
        )

    def read(self, storage_ref: str) -> bytes:
        """按存储引用读取并复核内容哈希；缺失或漂移抛确定性错误。"""
        parts = storage_ref.split("/")
        if len(parts) != 3 or parts[0] != ARTIFACTS_DIRNAME:
            raise ArtifactStoreError(
                f"非法工件存储引用 {storage_ref!r}（应为 "
                f"{ARTIFACTS_DIRNAME}/<kind>/<sha256>）"
            )
        kind, digest = parts[1], parts[2]
        self._require_kind(kind)
        return self._read_resolved(kind, digest)

    def read_by_sha(self, kind: str, sha256: str) -> bytes:
        """按 ``(类别, 内容哈希)`` 读取并复核内容（构造内容寻址引用后读取）。"""
        self._require_kind(kind)
        return self._read_resolved(kind, sha256)

    def _read_resolved(self, kind: str, digest: str) -> bytes:
        target = self.data_paths.root / ARTIFACTS_DIRNAME / kind / digest
        try:
            resolved = self.boundary.require_v2_target(target)
        except Exception as exc:
            raise ArtifactStoreError(
                f"工件 {kind}/{digest} 不在 V2 数据根内，拒绝读取"
            ) from exc
        if not resolved.is_file():
            raise ArtifactStoreError(f"工件 {kind}/{digest} 不存在")
        payload = resolved.read_bytes()
        actual = sha256(payload).hexdigest()
        if actual != digest:
            raise ArtifactIntegrityError(
                f"工件 {kind}/{digest} 内容与引用哈希不一致"
                f"（存储 {digest}，实际 {actual}）"
            )
        return payload
