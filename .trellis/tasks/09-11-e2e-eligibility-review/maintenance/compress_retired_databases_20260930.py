"""One-off, byte-preserving cleanup of inactive W6 test databases on APFS."""

from __future__ import annotations

import argparse
import filecmp
import gzip
import hashlib
import json
import os
import sqlite3
import stat
import subprocess
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/Users/smkzw/tmp")
ACTIVE_STATES = {"queued", "running", "retry_wait", "cancel_requested"}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def assert_inactive(path: Path) -> None:
    files = [str(item) for item in (path, Path(str(path) + "-wal"),
                                    Path(str(path) + "-shm")) if item.exists()]
    opened = subprocess.run(["lsof", "-nP", "-F", "p", *files],
                            capture_output=True, text=True)
    if opened.returncode != 1 or opened.stdout.strip() or opened.stderr.strip():
        raise RuntimeError("Database or sidecar is open, or ownership check failed")
    wal = Path(str(path) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise RuntimeError("Nonempty WAL: preserve untouched, do not replace")


def archive_large(path: Path, before: os.stat_result, result: dict) -> dict:
    archive = Path(str(path) + ".retired-20260930.gz")
    if archive.exists():
        raise RuntimeError("Archive exists; do not overwrite")
    value = hashlib.sha256()
    with path.open("rb") as source, archive.open("xb") as destination:
        os.chmod(archive, stat.S_IMODE(before.st_mode))
        with gzip.GzipFile(filename="", fileobj=destination, mode="wb", compresslevel=1,
                           mtime=0) as compressed:
            for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
                value.update(chunk)
                compressed.write(chunk)
        destination.flush()
        os.fsync(destination.fileno())
    check = hashlib.sha256()
    with gzip.open(archive, "rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            check.update(chunk)
    if check.digest() != value.digest():
        raise RuntimeError("Archive readback differs; original retained")
    assert_inactive(path)
    current = path.stat()
    if (current.st_ino, current.st_size, current.st_mtime_ns) != (
            before.st_ino, before.st_size, before.st_mtime_ns):
        raise RuntimeError("Source changed during archiving; original retained")
    result.update(status="cold_archive_verified", archive=str(archive),
                  sha256=value.hexdigest(), allocated_after=archive.stat().st_blocks * 512,
                  original_mode=stat.S_IMODE(before.st_mode),
                  original_mtime_ns=before.st_mtime_ns,
                  restore_required=True)
    marker = Path(str(path) + ".archived-20260930.json")
    marker.write_text(json.dumps(result, indent=2) + "\n")
    path.unlink()
    result["reclaimed_bytes"] = result["allocated_before"] - result["allocated_after"]
    return result


def process(path: Path, *, apply: bool, archive: bool) -> dict:
    before = path.stat()
    result = {"path": str(path), "logical_bytes": before.st_size,
              "allocated_before": before.st_blocks * 512}
    assert_inactive(path)
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as connection:
        states = dict(connection.execute("SELECT state,COUNT(*) FROM jobs GROUP BY state"))
    result["job_states"] = states
    if ACTIVE_STATES.intersection(states):
        result["status"] = "skipped_pending_or_running"
        return result
    if not apply:
        result["status"] = "eligible_no_change"
        return result
    if archive and path.stat().st_size >= 2 * 1024**3:
        return archive_large(path, before, result)
    temporary = Path(str(path) + ".cleanup-compressed")
    if not temporary.exists():
        subprocess.run(["ditto", "--hfsCompression", "--noclone", str(path),
                        str(temporary)], check=True)
    if not filecmp.cmp(path, temporary, shallow=False):
        raise RuntimeError("Compressed copy differs; original retained")
    if temporary.stat().st_blocks >= before.st_blocks:
        temporary.unlink()
        result["status"] = "no_space_gain_original_retained"
        return result
    result["sha256"] = digest(path)
    with closing(sqlite3.connect(f"file:{temporary}?mode=ro", uri=True)) as connection:
        if dict(connection.execute("SELECT state,COUNT(*) FROM jobs GROUP BY state")) != states:
            raise RuntimeError("Job state verification failed; original retained")
    assert_inactive(path)
    assert_inactive(temporary)
    current = path.stat()
    if (current.st_ino, current.st_size, current.st_mtime_ns) != (
            before.st_ino, before.st_size, before.st_mtime_ns):
        raise RuntimeError("Source changed during cleanup; original retained")
    os.replace(temporary, path)
    result.update(status=("compressed_same_bytes_same_path" if path.stat().st_flags &
                          stat.UF_COMPRESSED else "allocation_reduced_same_bytes_same_path"),
                  allocated_after=path.stat().st_blocks * 512)
    result["reclaimed_bytes"] = result["allocated_before"] - result["allocated_after"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--archive-large", action="store_true")
    parser.add_argument("--scope", choices=("w6", "retired-artifacts"), default="w6")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Use a fresh report; do not overwrite previous cleanup evidence")
    if args.scope == "w6":
        paths = sorted(ROOT.glob("enrollment-review-w6-*/**/enrollment-review-v2.sqlite3"))
    else:
        paths = sorted(path for root in (Path("artifacts/phase55-takeover"),
                        Path("artifacts/review-20260912"),
                        Path("artifacts/mtplx-dual-basic-20260916"))
                       for path in root.glob("**/*.sqlite3"))
    report = {"created_at": datetime.now(timezone.utc).isoformat(),
              "method": "Byte-preserving APFS compression or verified gzip cold archive",
              "apply": args.apply, "results": []}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path.is_symlink() or path.stat().st_size < 100 * 1024 * 1024:
            continue
        try:
            item = process(path.resolve(), apply=args.apply, archive=args.archive_large)
        except Exception as exc:
            item = {"path": str(path), "status": "skipped_error",
                    "error_type": type(exc).__name__, "detail": str(exc)}
        report["results"].append(item)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(item), flush=True)


if __name__ == "__main__":
    main()
