"""Offline tests must not implicitly load a developer's product credentials."""

import os
from pathlib import Path

os.environ.setdefault(
    "ENROLLMENT_ENV_FILE", str(Path(__file__).parent / "fixtures" / "isolated.env")
)
