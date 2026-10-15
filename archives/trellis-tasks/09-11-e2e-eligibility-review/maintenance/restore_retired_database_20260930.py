"""Restore one verified cold archive without overwriting any existing database."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("marker", type=Path)
    args = parser.parse_args()
    record = json.loads(args.marker.read_text())
    destination = Path(record["path"])
    archive = Path(record["archive"])
    if record["status"] != "cold_archive_verified":
        parser.error("Not a verified cold archive")
    if (destination.parent.resolve() != args.marker.resolve().parent
            or archive.parent.resolve() != destination.parent.resolve()):
        parser.error("Paths must remain in the archived database directory")
    if destination.exists():
        parser.error("Database exists; preserve it, do not overwrite")
    temporary = Path(str(destination) + ".restoring-20260930")
    value = hashlib.sha256()
    with gzip.open(archive, "rb") as source, temporary.open("xb") as output:
        os.chmod(temporary, record["original_mode"])
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            value.update(chunk)
            output.write(chunk)
        output.flush()
        os.fsync(output.fileno())
    if value.hexdigest() != record["sha256"] or temporary.stat().st_size != record["logical_bytes"]:
        raise RuntimeError("Restore verification failed; database was not activated")
    os.utime(temporary, ns=(record["original_mtime_ns"], record["original_mtime_ns"]))
    os.link(temporary, destination)
    temporary.unlink()
    print(json.dumps({"restored": str(destination), "sha256": value.hexdigest(),
                      "archive_retained": True, "jobs_not_resumed": True}))


if __name__ == "__main__":
    main()
