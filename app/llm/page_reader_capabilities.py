"""Wire-adapter capabilities, independent of clinical prompts and model names.

These vocabularies describe what the adapter can send, not proof that a loaded
weight supports every option. Published server limits narrow them at preflight;
missing metadata still requires a real probe before deployment acceptance.
"""

from collections.abc import Mapping

MIN_SEMANTIC_OUTPUT_TOKENS = 65536
MAX_SEMANTIC_OUTPUT_TOKENS = 262144
LOCAL_PAGE_PROVIDERS = frozenset({"omlx", "mlx-serve", "mtplx"})


def shared_reader_parallelism(routes) -> int:
    """Local readers share one hardware slot; remote pools remain independent."""
    local = any(route.provider in LOCAL_PAGE_PROVIDERS for route in routes)
    return int(local) + sum(
        route.max_concurrency for route in routes
        if route.provider not in LOCAL_PAGE_PROVIDERS
    )


_EFFORTS = {
    "zhipu-coding-plan": frozenset({"low", "high", "max"}),
    "google-antigravity": frozenset({"low", "high"}),
    "cms-smk": frozenset({"low", "medium", "high", "xhigh"}),
    "omlx": frozenset({"low", "medium", "high", "xhigh"}),
    "mlx-serve": frozenset({"low", "medium", "high", "xhigh"}),
    "mtplx": frozenset({"low", "medium", "high", "xhigh"}),
}


def validate_adapter_options(provider: str, effort: str) -> None:
    if provider not in _EFFORTS:
        raise ValueError("配置的资料判读服务尚无已实现的接入方式")
    if effort not in _EFFORTS[provider]:
        raise ValueError("配置的思考档位无法由该接入方式原样发送，不自动降档")


def validate_published_limits(model_info: Mapping, *, effort: str, max_tokens: int) -> None:
    efforts = model_info.get("supported_reasoning_efforts")
    if efforts is not None:
        if not isinstance(efforts, list) or effort not in efforts:
            raise ValueError("模型服务未声明支持配置的思考档位，不自动降档")
    for field in ("max_output_tokens", "context_length"):
        limit = model_info.get(field)
        if limit is None:
            continue
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("模型服务返回的输出或上下文额度无效")
        if max_tokens > limit:
            raise ValueError("配置的输出额度超过模型服务声明上限，不自动缩减")
