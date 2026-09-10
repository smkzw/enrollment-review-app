"""Reject ambiguous diagnostic sources before any model call or output write."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from scripts.r3_page_diagnostic import run


def arguments(tmp_path, **overrides):
    source = tmp_path / "input.json"
    source.write_text(json.dumps({"pages": [{}]}))
    values = dict(frozen_input=source, page_index=0, targets=["品名"],
                  image=None, sha256=None, page_number=None, clause_pack=None,
                  without_clause_context=False, image_detail=None,
                  output=tmp_path / "output")
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize("index", [-1, 1, 100])
def test_frozen_page_index_must_exist(tmp_path, index):
    args = arguments(tmp_path, page_index=index)
    with pytest.raises(ValueError, match="outside"):
        asyncio.run(run(args))
    assert not args.output.exists()


def test_frozen_source_cannot_mix_standalone_identity(tmp_path):
    args = arguments(tmp_path, sha256="a" * 64)
    with pytest.raises(ValueError, match="mix"):
        asyncio.run(run(args))
    assert not args.output.exists()


@pytest.mark.parametrize("override", [{"targets": []}, {"image_detail": "low"},
                                     {"without_clause_context": True}])
def test_focus_requires_targets_without_ablation(tmp_path, override):
    args = arguments(tmp_path, **override)
    with pytest.raises(ValueError, match="requires"):
        asyncio.run(run(args))
    assert not args.output.exists()
