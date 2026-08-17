"""Generate the synthetic DOCX used by real-HTTP browser acceptance."""
from __future__ import annotations

import argparse
from pathlib import Path

from tests.v2.api.protocol_e2e_helpers import build_pipeline_e2e_docx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    build_pipeline_e2e_docx(args.output)


if __name__ == "__main__":
    main()
