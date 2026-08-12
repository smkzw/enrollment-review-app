from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class ProtectedPathError(ValueError):
    """Raised when a V2 write target crosses an allowed storage boundary."""


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class WriteBoundary:
    v2_root: Path
    protected_roots: tuple[Path, ...]

    @classmethod
    def create(cls, v2_root: Path, protected_roots: Iterable[Path]) -> "WriteBoundary":
        return cls(
            v2_root=v2_root.resolve(),
            protected_roots=tuple(root.resolve() for root in protected_roots),
        )

    def require_v2_target(self, target: Path) -> Path:
        resolved = target.resolve()
        if not _is_within(resolved, self.v2_root):
            raise ProtectedPathError("V2 写入目标不在 V2 数据目录内")
        if any(_is_within(resolved, root) for root in self.protected_roots):
            raise ProtectedPathError("V2 写入目标位于受保护的旧系统目录")
        return resolved


def snapshot_tree(root: Path) -> dict[str, str]:
    """Hash a bounded tree for pre/post write-protection checks."""
    resolved_root = root.resolve()
    snapshot: dict[str, str] = {}
    if not resolved_root.exists():
        return snapshot
    for path in sorted(item for item in resolved_root.rglob("*") if item.is_file()):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        snapshot[str(path.relative_to(resolved_root))] = digest.hexdigest()
    return snapshot
