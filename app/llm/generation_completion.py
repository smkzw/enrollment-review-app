"""Distinguish reported local early termination from budget exhaustion."""

from collections.abc import Mapping


def local_early_length(provider: str, usage: object, budget: int) -> bool:
    if provider not in {"mlx-serve", "omlx", "mtplx"}:
        return False
    count = (usage.get("completion_tokens") if isinstance(usage, Mapping)
             else getattr(usage, "completion_tokens", None))
    # Unknown usage is not evidence of an early stop or a reasoning loop.
    return type(count) is int and 0 < count < budget
