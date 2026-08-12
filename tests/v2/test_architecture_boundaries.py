import ast
import tempfile
import unittest
from pathlib import Path

from app.storage.boundaries import ProtectedPathError, WriteBoundary, snapshot_tree


REPO_ROOT = Path(__file__).resolve().parents[2]
V2_PACKAGES = (
    REPO_ROOT / "app" / "api" / "v2",
    REPO_ROOT / "app" / "domain",
    REPO_ROOT / "app" / "workflow",
    REPO_ROOT / "app" / "storage",
    REPO_ROOT / "app" / "agents",
    REPO_ROOT / "app" / "projections",
    REPO_ROOT / "app" / "services",
)
FORBIDDEN_LEGACY_IMPORTS = ("app.shared", "app.router", "app.pipeline")


class WriteBoundaryTests(unittest.TestCase):
    def test_only_v2_root_accepts_write_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            v2_root = workspace / "v2-data"
            legacy_root = workspace / "projects"
            v2_root.mkdir()
            legacy_root.mkdir()
            boundary = WriteBoundary.create(v2_root, [legacy_root])

            self.assertEqual(
                boundary.require_v2_target(v2_root / "review.db"),
                (v2_root / "review.db").resolve(),
            )
            with self.assertRaises(ProtectedPathError):
                boundary.require_v2_target(legacy_root / "project.json")
            with self.assertRaises(ProtectedPathError):
                boundary.require_v2_target(workspace / "unscoped.json")

    def test_snapshot_detects_legacy_content_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = root / "project.json"
            record.write_text('{"status":"legacy"}', encoding="utf-8")
            before = snapshot_tree(root)
            record.write_text('{"status":"changed"}', encoding="utf-8")
            self.assertNotEqual(before, snapshot_tree(root))

    def test_repository_legacy_roots_are_rejected_without_writing(self) -> None:
        boundary = WriteBoundary.create(
            REPO_ROOT / "v2-data",
            [REPO_ROOT / "projects", REPO_ROOT / "output"],
        )
        for protected_root in (REPO_ROOT / "projects", REPO_ROOT / "output"):
            with self.subTest(protected_root=protected_root):
                with self.assertRaises(ProtectedPathError):
                    boundary.require_v2_target(protected_root / "phase0-write-probe")


class DependencyDirectionTests(unittest.TestCase):
    def test_v2_packages_do_not_import_legacy_write_modules(self) -> None:
        violations: list[str] = []
        for package in V2_PACKAGES:
            for source_path in package.rglob("*.py"):
                tree = ast.parse(source_path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported = [node.module]
                    else:
                        continue
                    for name in imported:
                        if name.startswith(FORBIDDEN_LEGACY_IMPORTS):
                            violations.append(f"{source_path.relative_to(REPO_ROOT)} -> {name}")
        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
