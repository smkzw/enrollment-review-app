"""证据写命令的不可变内容身份存储。

幂等表只保存命令哈希和结果指针；当同一幂等键携带不同命令时，
用户还需要看到真实的首次命令与本次命令差异。本存储以规范化命令的
SHA-256 为身份，在 V2 数据根内原子写入。数据库事务若回滚，可能留下
无引用的内容寻址文件，但它不能被任何幂等记录读取，也不会改写已有命令。
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from app.storage.config import DataPaths

COMMAND_IDENTITIES_DIRNAME = "command-identities"


class CommandIdentityIntegrityError(RuntimeError):
    """命令身份文件缺失或内容漂移。"""


def canonical_command_bytes(command: dict[str, Any]) -> bytes:
    return json.dumps(
        command,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


class EvidenceCommandIdentityStore:
    """在 V2 数据根中按命令哈希保存可复核的首次提交。"""

    def __init__(self, data_paths: DataPaths) -> None:
        self.data_paths = data_paths
        self.boundary = data_paths.boundary

    def put(self, command: dict[str, Any]) -> str:
        payload = canonical_command_bytes(command)
        digest = sha256(payload).hexdigest()
        target = self.data_paths.root / COMMAND_IDENTITIES_DIRNAME / f"{digest}.json"
        if target.exists():
            existing = self.boundary.require_v2_target(target).read_bytes()
            if existing != payload:
                raise CommandIdentityIntegrityError("已有命令身份内容与其哈希不一致")
            return digest
        self.boundary.atomic_write_bytes(target, payload)
        return digest

    def get(self, digest: str) -> dict[str, Any]:
        target = self.data_paths.root / COMMAND_IDENTITIES_DIRNAME / f"{digest}.json"
        resolved = self.boundary.require_v2_target(target)
        if not resolved.is_file():
            raise CommandIdentityIntegrityError("幂等记录引用的命令身份不存在")
        payload = resolved.read_bytes()
        if sha256(payload).hexdigest() != digest:
            raise CommandIdentityIntegrityError("命令身份文件与其哈希不一致")
        value = json.loads(payload)
        if not isinstance(value, dict):
            raise CommandIdentityIntegrityError("命令身份不是完整的字段集")
        return value
