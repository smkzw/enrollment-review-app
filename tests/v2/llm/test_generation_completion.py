from types import SimpleNamespace

import pytest

from app.llm.generation_completion import local_early_length


@pytest.mark.parametrize("count,expected", [(18010, True), (131072, False), (0, False), (None, False), (True, False)])
def test_local_usage_evidence(count, expected):
    assert local_early_length("mlx-serve", {"completion_tokens": count}, 131072) is expected
    assert local_early_length("omlx", SimpleNamespace(completion_tokens=count), 131072) is expected
    assert not local_early_length("zhipu-coding-plan", {"completion_tokens": count}, 131072)
