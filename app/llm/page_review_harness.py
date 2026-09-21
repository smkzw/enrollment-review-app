"""Product-owned R3 page reader harness; no external agent harness dependency."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import io
import json
import os
import re
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Mapping

import httpx
from PIL import Image
from openai import AsyncOpenAI

from app.llm.generation_completion import local_early_length

from app.config import (
    GEMINI_ACCESS_TOKEN,
    GEMINI_BASE_URL,
    GEMINI_PROJECT_ID,
    PAGE_REVIEW_CLOUD_CONCURRENCY,
    PAGE_REVIEW_MAIN_A_API_KEY,
    PAGE_REVIEW_MAIN_A_BASE_URL,
    PAGE_REVIEW_MAIN_A_FALLBACK_BASE_URL,
    PAGE_REVIEW_MAIN_A_MODEL,
    PAGE_REVIEW_MAIN_A_REASONING_EFFORT,
    PAGE_REVIEW_MAIN_B_API_KEY,
    PAGE_REVIEW_MAIN_B_BASE_URL,
    PAGE_REVIEW_MAIN_B_FALLBACK_BASE_URL,
    PAGE_REVIEW_MAIN_B_MODEL,
    PAGE_REVIEW_MAIN_B_PROVIDER,
    PAGE_REVIEW_MAIN_B_REASONING_EFFORT,
    PAGE_REVIEW_MAX_TOKENS,
    PAGE_REVIEW_TIMEOUT_SECONDS,
)
from app.domain.contracts.clause_pack import ClausePack
from app.domain.contracts.page_review_context import PageReviewContext
from app.domain.contracts.page_review_focus import PageReviewFocus
from app.domain.contracts.page_review import (
    PageReviewLane,
    PageReviewPayload,
    PageReviewRecord,
    PAGE_REVIEW_CONTRACT_VERSION,
)
from app.domain.publication import canonical_hash
from app.evidence.reading_view import ReadingView
from app.domain.contracts.reading_view import ReadingViewBinding
from app.llm.independent_vlm import PageVisionInput, page_to_data_url
from app.llm.page_review_format_repair import (
    PAGE_REVIEW_FORMAT_REPAIR_VERSION,
    PageResponseFormatError,
    build_format_repair_messages,
    valid_observation_fingerprints,
    evaluate_page_review_response,
)
from app.projections.clause_pack import verify_clause_pack
from app.projections.page_review_prompt_pack import page_review_prompt_pack
from app.llm.page_review_transport_options import page_completion_options, page_transport_contract
from app.llm.page_reader_capabilities import (
    LOCAL_PAGE_PROVIDERS, MIN_SEMANTIC_OUTPUT_TOKENS, MAX_SEMANTIC_OUTPUT_TOKENS,
    validate_adapter_options, validate_published_limits,
)

PAGE_REVIEW_PROMPT_VERSION = "page-review-r3/v20"
TARGETED_REVIEW_PROMPT_VERSION = "page-targeted-review/v5"

_CONTENT_FILTER_MARKERS = ("content filter", "content_filter", "1301", "内容过滤")


class PageReviewHarnessError(RuntimeError):
    def __init__(self, message: str, *, failure_kind: str) -> None:
        super().__init__(message)
        self.failure_kind = failure_kind


class PageReviewConfigError(PageReviewHarnessError):
    def __init__(self, message: str) -> None:
        super().__init__(message, failure_kind="configuration")


@dataclass(frozen=True)
class PageReaderRoute:
    lane: PageReviewLane
    provider: str
    base_url: str
    api_key: str
    model: str
    reasoning_effort: str
    max_tokens: int
    max_concurrency: int
    fallback_base_url: str = ""
    project_id: str = ""


@dataclass(frozen=True)
class PageReviewInput:
    page_artifact_id: str
    source_document_version_id: str
    page_number: int
    page_image_sha256: str
    page: PageVisionInput
    review_context: PageReviewContext | None = None
    reading_view: ReadingView | None = None

    def __post_init__(self) -> None:
        if sum(value is not None for value in (
            self.page.image_bytes, self.page.image_path, self.page.data_url,
        )) != 1:
            raise ValueError("每页只能提供一种图像来源")
        if self.page_number != self.page.page_ordinal:
            raise ValueError("页码与图像页序不一致")
        actual = hashlib.sha256(_page_image_bytes(self.page)).hexdigest()
        expected = self.page_image_sha256
        if self.reading_view is not None:
            view = self.reading_view
            if (view.clockwise_degrees == 0 or view.source_page_artifact_id != self.page_artifact_id
                    or view.source_image_sha256 != self.page_image_sha256):
                raise ValueError("阅读视图与当前原始页面不一致")
            expected = view.image_sha256
        if expected != actual:
            raise ValueError("页图像哈希与实际输入不一致")


@dataclass(frozen=True)
class PageCompletion:
    text: str
    finish_reason: str | None
    usage: Mapping[str, Any]
    response_model: str | None = None
    response_id: str | None = None
    output_lengths: Mapping[str, int | None] | None = None
    transport_contract: str | None = None


Completion = Callable[
    [PageReaderRoute, list[dict[str, Any]], int], Awaitable[PageCompletion]
]


def _page_image_bytes(page: PageVisionInput) -> bytes:
    if page.image_bytes is not None:
        return page.image_bytes
    if page.image_path is not None:
        return Path(page.image_path).read_bytes()
    data_url = str(page.data_url or "")
    if not data_url.startswith("data:") or ";base64," not in data_url:
        raise ValueError("页图像 data_url 必须是 base64 内嵌数据")
    try:
        return base64.b64decode(data_url.split(",", 1)[1], validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("页图像 data_url 不是有效 base64 数据") from exc


def _value(environ: Mapping[str, str], name: str, default: str) -> str:
    return str(environ.get(name, default) or "").strip()


def require_page_reader_routes(
    environ: Mapping[str, str] | None = None,
    *, require_credentials: bool = True,
) -> dict[PageReviewLane, PageReaderRoute]:
    """Resolve only explicit project/process configuration and fail closed."""
    env = os.environ if environ is None else environ
    concurrency = int(
        _value(env, "PAGE_REVIEW_CLOUD_CONCURRENCY", str(PAGE_REVIEW_CLOUD_CONCURRENCY))
    )
    if concurrency not in {2, 3}:
        raise PageReviewConfigError("云端逐页判读并发必须为 2 或 3")
    try:
        max_tokens = int(_value(env, "PAGE_REVIEW_MAX_TOKENS", str(PAGE_REVIEW_MAX_TOKENS)))
    except ValueError as exc:
        raise PageReviewConfigError("逐页判读输出额度必须为整数") from exc
    if not MIN_SEMANTIC_OUTPUT_TOKENS <= max_tokens <= MAX_SEMANTIC_OUTPUT_TOKENS:
        raise PageReviewConfigError("新逐页判读输出额度必须在 65536 至 131072 之间")

    provider = _value(env, "PAGE_REVIEW_MAIN_A_PROVIDER", "") or _value(
        env, "INDEPENDENT_VLM_PROVIDER", "zhipu-coding-plan"
    )
    local_main_a = provider in LOCAL_PAGE_PROVIDERS
    main_a_key = (
        _value(env, "PAGE_REVIEW_LOCAL_API_KEY", "") or "local-product"
        if local_main_a
        else _value(env, "PAGE_REVIEW_MAIN_A_API_KEY", "")
    )
    if provider == "opencode-go":
        # OpenCode 凭据与 OMP 的 opencode-go provider 同源，只从专用环境变量
        # 读取（用户自行填写，不经任何会话/日志转手）；绝不回退到其他供应商
        # 的密钥，防止把 A 供应商的凭据发给 B 供应商。
        main_a_key = _value(env, "PAGE_REVIEW_MAIN_A_API_KEY", "") or _value(
            env, "OPENCODE_API_KEY", ""
        )
    elif not local_main_a and not main_a_key:
        main_a_key = _value(
            env, "INDEPENDENT_VLM_API_KEY", PAGE_REVIEW_MAIN_A_API_KEY
        )
    main_b_provider = _value(env, "PAGE_REVIEW_MAIN_B_PROVIDER", PAGE_REVIEW_MAIN_B_PROVIDER)
    local_main_b = main_b_provider in LOCAL_PAGE_PROVIDERS
    gemini_main_b = main_b_provider == "google-antigravity"
    if gemini_main_b:
        main_b_key = (
            _value(env, "PAGE_REVIEW_MAIN_B_API_KEY", PAGE_REVIEW_MAIN_B_API_KEY)
            or _value(env, "GEMINI_ACCESS_TOKEN", GEMINI_ACCESS_TOKEN)
        )
        main_b_project = _value(env, "GEMINI_PROJECT_ID", GEMINI_PROJECT_ID)
        main_b_base_url = (
            _value(env, "PAGE_REVIEW_MAIN_B_BASE_URL", PAGE_REVIEW_MAIN_B_BASE_URL)
            or _value(env, "GEMINI_BASE_URL", GEMINI_BASE_URL)
        )
    else:
        # Local credentials are intentionally separate from old cloud main-B keys.
        main_b_key = (_value(env, "PAGE_REVIEW_LOCAL_API_KEY", "") if local_main_b
                      else _value(env, "PAGE_REVIEW_MAIN_B_API_KEY", PAGE_REVIEW_MAIN_B_API_KEY))
        if local_main_b and not main_b_key:
            main_b_key = "local-product"
        elif not main_b_key:
            main_b_key = _value(env, "CMS_SMK_API_KEY", "")
        main_b_project = ""
        main_b_base_url = _value(env, "PAGE_REVIEW_MAIN_B_BASE_URL", PAGE_REVIEW_MAIN_B_BASE_URL)
    missing = []
    if not main_a_key:
        if provider == "opencode-go":
            missing.append("OPENCODE_API_KEY")
        else:
            missing.append("PAGE_REVIEW_MAIN_A_API_KEY（或 INDEPENDENT_VLM_API_KEY）")
    if gemini_main_b:
        if not main_b_key:
            missing.append("GEMINI_ACCESS_TOKEN（或 PAGE_REVIEW_MAIN_B_API_KEY）")
        if not main_b_project:
            missing.append("GEMINI_PROJECT_ID")
    elif not main_b_key:
        missing.append("PAGE_REVIEW_MAIN_B_API_KEY（或 CMS_SMK_API_KEY）")
    if missing and require_credentials:
        raise PageReviewConfigError("缺少逐页判读凭据：" + "、".join(missing))

    main_a_model = _value(env, "PAGE_REVIEW_MAIN_A_MODEL", PAGE_REVIEW_MAIN_A_MODEL)
    main_b_model = _value(env, "PAGE_REVIEW_MAIN_B_MODEL", PAGE_REVIEW_MAIN_B_MODEL)
    main_a_effort = _value(env, "PAGE_REVIEW_MAIN_A_REASONING_EFFORT", PAGE_REVIEW_MAIN_A_REASONING_EFFORT)
    main_b_effort = _value(env, "PAGE_REVIEW_MAIN_B_REASONING_EFFORT", PAGE_REVIEW_MAIN_B_REASONING_EFFORT)
    for lane, selected_provider, effort in (
        ("main-A", provider, main_a_effort), ("main-B", main_b_provider, main_b_effort),
    ):
        try:
            validate_adapter_options(selected_provider, effort)
        except ValueError as exc:
            raise PageReviewConfigError(f"{lane} {exc}") from exc

    routes = {
        PageReviewLane.MAIN_A: PageReaderRoute(
            lane=PageReviewLane.MAIN_A,
            provider=provider,
            base_url=_value(env, "PAGE_REVIEW_MAIN_A_BASE_URL", PAGE_REVIEW_MAIN_A_BASE_URL),
            api_key=main_a_key,
            model=main_a_model,
            reasoning_effort=main_a_effort,
            max_tokens=max_tokens,
            max_concurrency=1 if local_main_a else concurrency,
            fallback_base_url=_value(
                env,
                "PAGE_REVIEW_MAIN_A_FALLBACK_BASE_URL",
                PAGE_REVIEW_MAIN_A_FALLBACK_BASE_URL,
            ),
        ),
        PageReviewLane.MAIN_B: PageReaderRoute(
            lane=PageReviewLane.MAIN_B,
            provider=main_b_provider,
            base_url=main_b_base_url,
            api_key=main_b_key,
            model=main_b_model,
            reasoning_effort=main_b_effort,
            max_tokens=max_tokens,
            max_concurrency=1 if local_main_b else concurrency,
            fallback_base_url=_value(
                env,
                "PAGE_REVIEW_MAIN_B_FALLBACK_BASE_URL",
                PAGE_REVIEW_MAIN_B_FALLBACK_BASE_URL,
            ),
            project_id=main_b_project,
        ),
    }
    for route in routes.values():
        if not route.base_url.startswith(("http://", "https://")):
            raise PageReviewConfigError(f"{route.lane.value} 端点不是有效 HTTP 地址")
        if route.provider == "google-antigravity" and not route.base_url.startswith("https://"):
            raise PageReviewConfigError(f"{route.lane.value} Gemini 端点必须为 HTTPS")
        if not route.model:
            raise PageReviewConfigError(f"{route.lane.value} 未配置模型")
    return routes


async def resolve_route_model(route: PageReaderRoute) -> PageReaderRoute:
    from app.llm.mtplx_model_lifecycle import mtplx_model_session

    async with mtplx_model_session(route.provider, route.base_url, route.model, route.reasoning_effort) as health:
        return await _resolve_route_model(route, owned_health=health)


async def _external_shared_mtplx_health(base_url: str) -> Mapping | None:
    """读取外部共享 MTPLX 实例的启动声明；仅用于身份与能力核对，不做装卸。"""
    server_root = base_url.rstrip("/")
    if server_root.endswith("/v1"):
        server_root = server_root[: -len("/v1")]
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=5) as client:
            response = await client.get(f"{server_root}/health")
            response.raise_for_status()
            health = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not isinstance(health, Mapping) or health.get("ok") is not True:
        return None
    return health


def _external_health_matches_model(health: Mapping, model: str) -> bool:
    """配置模型名与实例声明的模型目录逐词绑定；``mtplx-`` 前缀视为产品别名。"""
    model_path = str(health.get("model_path", "")).replace("\\", "/")
    model_dir = model_path.rstrip("/").rsplit("/", 1)[-1].lower()
    if not model_dir:
        return False
    tokens = [t for t in model.strip().lower().split("-") if t and t != "mtplx"]
    return bool(tokens) and all(t in model_dir for t in tokens)


async def _resolve_route_model(route: PageReaderRoute, *, owned_health: Mapping | None = None) -> PageReaderRoute:
    """Verify the configured model identity against the lane's native transport."""
    if route.provider == "google-antigravity":
        # 原生 Gemini 传输没有 OpenAI /models 接口：身份由显式配置固定，
        # 缺凭据在此明确失败；每次响应的 modelVersion 回执由传输逐次核对。
        if not route.api_key or not route.project_id:
            raise PageReviewConfigError(
                f"{route.lane.value} 缺少 Gemini 访问凭据或项目标识"
            )
        if not route.base_url.startswith("https://"):
            raise PageReviewConfigError(f"{route.lane.value} Gemini 端点必须为 HTTPS")
        return route
    headers = {"Authorization": f"Bearer {route.api_key}"}
    listing_unavailable = False
    async with httpx.AsyncClient(trust_env=False, timeout=15) as client:
        try:
            response = await client.get(f"{route.base_url.rstrip('/')}/models", headers=headers)
            response.raise_for_status()
            data = response.json().get("data", [])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403, 404}:
                # 网关可能仅对对话端点放行业务密钥，模型目录另需管理凭据。
                # 显式配置的模型身份由每次对话回执核对，不因目录不可读而拒绝启动。
                listing_unavailable = True
                data = []
            else:
                raise
    ids = [str(item.get("id", "")) for item in data if isinstance(item, Mapping)]
    external_shared_health: Mapping | None = None
    if not listing_unavailable and route.model not in ids and route.provider == "mtplx" and owned_health is None:
        # 外部共享实例（2026-09-18 用户裁定）：端口上唯一在服务的模型即
        # 无歧义目标；身份由 /health 声明的模型目录与能力绑定。
        external_shared_health = await _external_shared_mtplx_health(route.base_url)
    if not listing_unavailable and route.model not in ids and external_shared_health is None:
        # 网关可能以带前缀的 id 发布模型（如 /v1/xxx），同时接受裸名调用；
        # root/name 与配置名一致时视为同一模型的已发布别名。
        if not any(
            isinstance(item, Mapping)
            and route.model in {str(item.get("root", "")), str(item.get("name", ""))}
            for item in data
        ):
            raise PageReviewConfigError(
                f"{route.lane.value} 端点未报告配置模型 {route.model}"
            )
    if external_shared_health is not None:
        if len(ids) != 1:
            raise PageReviewConfigError(
                f"{route.lane.value} 外部共享实例必须在服务唯一模型"
            )
        if not _external_health_matches_model(external_shared_health, route.model):
            raise PageReviewConfigError(
                f"{route.lane.value} 外部实例在服务的模型与配置 {route.model} 不一致"
            )
    def _match_model_info(candidates):
        for item in candidates:
            if isinstance(item, Mapping) and item.get("id") == route.model:
                return item
        for item in candidates:
            if (isinstance(item, Mapping)
                    and route.model in {str(item.get("root", "")), str(item.get("name", ""))}):
                return item
        return next((item for item in candidates if isinstance(item, Mapping)), {})

    model_info = _match_model_info(data)
    try:
        validate_adapter_options(route.provider, route.reasoning_effort)
        if not listing_unavailable:
            validate_published_limits(model_info, effort=route.reasoning_effort, max_tokens=route.max_tokens)
    except ValueError as exc:
        raise PageReviewConfigError(f"{route.lane.value} {exc}") from exc
    if route.provider == "mlx-serve":
        model_info = _match_model_info(data)
        if model_info.get("loaded") is not True or model_info.get("state") != "ready":
            raise PageReviewConfigError("本地资料判读模型尚未就绪，不自动加载或替换模型")
        if "vision" not in model_info.get("capabilities", []):
            raise PageReviewConfigError("本地资料判读模型未声明图像读取能力")
    if route.provider == "mtplx":
        model_info = _match_model_info(data)
        # New owned servers publish vision in PID/launch-bound health. An
        # explicit negative model declaration must still reject the route.
        vision = model_info.get("supports_vision")
        if "supports_vision" not in model_info and owned_health is not None:
            vision = (owned_health.get("model") == route.model
                      and isinstance(owned_health.get("vision"), Mapping)
                      and owned_health["vision"].get("enabled") is True)
        if vision is not True and external_shared_health is not None:
            vision = (_external_health_matches_model(external_shared_health, route.model)
                      and isinstance(external_shared_health.get("vision"), Mapping)
                      and external_shared_health["vision"].get("enabled") is True)
        if vision is not True:
            raise PageReviewConfigError("本地资料判读模型未声明图像读取能力")
    return route


async def preflight_page_reader_routes(
    routes: Mapping[PageReviewLane, PageReaderRoute],
) -> dict[PageReviewLane, PageReaderRoute]:
    """Require and resolve exactly the two main reader identities."""
    main_lanes = (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)
    if not set(main_lanes).issubset(routes) or not set(routes).issubset(set(PageReviewLane)):
        raise PageReviewConfigError("逐页判读必须同时声明两个主读道")
    if all(routes[lane].provider == "mtplx" for lane in main_lanes):
        # Finish preflight on A, the first reading lane, avoiding a third load.
        checked = {}
        for lane in reversed(main_lanes):
            checked[lane] = await resolve_route_model(routes[lane])
        return {lane: checked[lane] for lane in main_lanes}
    resolved = await asyncio.gather(*(resolve_route_model(routes[lane]) for lane in main_lanes))
    return dict(zip(main_lanes, resolved, strict=True))


def repair_json_quotes(text: str) -> str:
    """Migrate the benchmark's repair for unescaped quotes inside JSON strings."""
    output: list[str] = []
    in_string = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and in_string:
            output.append(text[index : index + 2])
            index += 2
            continue
        if char == '"':
            if not in_string:
                in_string = True
            else:
                next_index = index + 1
                while next_index < len(text) and text[next_index] in " \t\r\n":
                    next_index += 1
                if next_index >= len(text) or text[next_index] in ",:}]":
                    in_string = False
                else:
                    output.append("\\\"")
                    index += 1
                    continue
        output.append(char)
        index += 1
    return "".join(output)


def extract_json_object(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        raise PageReviewHarnessError("模型未返回 JSON 对象", failure_kind="invalid_json")
    decoder = json.JSONDecoder(strict=False)
    body = match.group(0)
    for candidate in (body, repair_json_quotes(body)):
        try:
            value = decoder.raw_decode(candidate)[0]
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise PageReviewHarnessError("模型 JSON 无法修复", failure_kind="invalid_json")


def build_page_review_messages(
    route: PageReaderRoute,
    page_input: PageReviewInput,
    clause_pack: ClausePack,
) -> list[dict[str, Any]]:
    if route.lane not in {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}:
        raise PageReviewConfigError("资料判读只允许两个主读模型")
    image_url = page_to_data_url(page_input.page)
    if not image_url.startswith("data:") or ";base64," not in image_url:
        raise ValueError("发送图像必须为已校验的内嵌数据")
    image_bytes = base64.b64decode(image_url.split(",", 1)[1], validate=True)
    expected_image = (page_input.reading_view.image_sha256 if page_input.reading_view
                      else page_input.page_image_sha256)
    if hashlib.sha256(image_bytes).hexdigest() != expected_image:
        raise ValueError("发送图像与冻结原件不一致")
    with Image.open(io.BytesIO(image_bytes)) as image:
        image_width, image_height = image.size
    output_schema = PageReviewPayload.model_json_schema()
    for axis, maximum in (("x0", image_width), ("x1", image_width),
                          ("y0", image_height), ("y1", image_height)):
        output_schema["$defs"]["BoundingBox"]["properties"][axis]["maximum"] = maximum
    # Make the conditional evidence requirement visible to constrained decoders.
    signal_schema = output_schema["$defs"]["ClauseEvidenceSignal"]
    if "region" not in signal_schema["required"]:
        signal_schema["required"].append("region")
    for definition, fields in (
        ("PageFactObservation", ("normalized_value", "normalized_unit", "normalization_key")),
        ("HandwritingObservation", ("normalized_text", "normalization_key")),
    ):
        schema = output_schema.get("$defs", {}).get(definition)
        if schema is not None:
            for field in fields:
                schema["properties"].pop(field, None)
            schema["required"] = [field for field in schema["required"] if field not in fields]
            if "context" not in schema["required"]:
                schema["required"].append("context")
    system_prompt = (
        "你是入排审核系统的逐页医学资料读片员。"
        "只报告本页可见事实、手写批注及条款证据信号，不作入排结论，"
        "不得自行给出满足、不满足、触发或未触发等判定；忠实摘录原文不受此限制。"
    )
    system_prompt += (
        "每条观察用 context 保留本页可见的关联：target_text 为所指项目或对象原文，"
        "time_text 为该观察日期原文，location_text 为表格行列标题或位置原文，"
        "polarity 只表达原文肯定、否定、不确定或未说明，不作临床判断。"
        "手写判断必须关联所指项目，不能将一个项目的 NCS 扩展到整份报告。"
        "同一值在不同日期或位置出现须分别记录；看不清所指对象时 context 为 null，不猜测。"
        "location_text 只抄录原件明确印出的、用于区分观察的行列标题；没有则为 null。"
        "不得自行编造页首、文档标识区、检查结果行等位置描述；图像位置另由 region 表达。"
        "日期字段本身的 time_text 为 null；结果的 time_text 仅引用明确适用于它的原文日期。"
        "handwriting 只记录图像中实际手写的笔迹，打印文字即使提及批注、签字或无手写也不属于手写。"
        "没有实际手写时必须返回 handwriting=[]，不得为说明没有手写而新增一条记录。"
        "只输出符合 output_schema 的一个 JSON 对象，不输出解释、Markdown 或其他文字。"
        "raw_text、raw_value、region.excerpt 必须忠实抄录可辨原文，不能用医学同义改写代替原文。"
        "看不清的字标为〔无法辨认〕，不得凭常见报告格式补齐机构、项目、结果、日期或签名。"
        "region.bbox 如填写，使用当前图片的像素边界坐标，原点在左上，x向右、y向下，"
        "不得使用0到1的比例坐标或PDF点数；不能可靠定位时填写null，不估造位置。"
    )
    system_prompt += (
        "先按原件顺序完整读取本页临床资料，再列出与条款相关的证据关系；"
        "facts 不按条款相关性或结果是否异常筛选。检验表逐项记录所有可辨结果，"
        "正常结果也保留；同页有多张报告时分别读取，不遗漏后面的报告。"
        "逐项核对项目、结果、单位和可见日期后再结束；不可把参考范围当作结果。"
        "每条 facts 只记录一个对象的一项事实；并列的不同药物、检查项目或事件分别记录，"
        "数值结果的 raw_value 必须同时抄录该结果明确对应且可见的单位，保留比较符号和异常箭头；"
        "单位在同一行单位列或明确适用的表头时也须保留，并在 region.excerpt 中保留对应依据。"
        "单位被遮挡、无法辨认或对应关系不明时不得按常识、参考范围或其他项目补写。"
        "同一药物的原文剂量、频次、途径可保留在该药物记录中，不合并不同药物。"
        "field_name 优先使用原件该项标签，不加章节前缀，不自行创造同义标题；"
        "叙述中无单项标签时使用最短资料类别名称，不把整段现病史作为一条事实。"
        "context.target_text 填该事实实际指向的项目或对象；标签本身唯一指明对象时抄录标签，"
        "药物观察抄录对应药物名称，不用既往用药等类别名替代对象。"
        "原件明确给出对象时必须填写 context；只有对象确实无法辨认时才为 null。"
        "就诊日期、处方日期和实际用药起止日期不可互相替代；原文未明确将日期关联到该观察时，"
        "time_text 为 null，不加入起点、之后等自行解释。"
        "has_eligibility_value 仅表示本页是否返回了待核对资料，不表示受试者符合入选条件。"
        "facts、clause_signals、handwriting 任一非空时必须为 true；"
        "仅三者均为空时为 false。原文、摘录及字段名保持忠实，规范值和归一化键由系统计算，无需输出。"
        "条款包只帮助识别相关内容，不是受试者事实来源；不能把方案要求、项目名称或阈值当成本页结果。"
        "review_context 仅提供当前审核节点及已登记锚定日期，不是本页事实；缺失日期不得推测，不能覆盖原件日期。"
        "只报告本页实际涉及条款的证据关系，不必逐条输出无关条款；不计算阈值、洗脱期或跨页判断。"
        "每条 clause_signals 必须填写 region：evidence_for、evidence_against、mentions 均须在"
        "region.excerpt 抄录本页支持该关联的原文；none 的 region 为 null。"
        "不能只填条款编号和关系而省略原文摘录，也不能以方案条款原文代替本页摘录。"
    )
    prompt = {
        # Keep unchanged requirements before page-specific text and image tokens.
        # Backends without prefix reuse receive the same complete clinical input.
        "clause_pack": page_review_prompt_pack(clause_pack),
        "output_schema": output_schema,
        "page_artifact_id": page_input.page_artifact_id,
        "page_number": page_input.page_number,
        "image_coordinates": {"space": "page_image_pixels", "origin": "top_left",
                              "width": image_width, "height": image_height},
        **({"reading_view": page_input.reading_view.identity()} if page_input.reading_view else {}),
        **({"review_context": page_input.review_context.model_dump(mode="json")}
           if page_input.review_context is not None else {}),
    }
    system_prompt += "条款 source_text_ref 指向 source_texts 中的完整原文，须结合该原文理解；省略的空字段不新增要求。"
    if clause_pack.control_publication is not None:
        system_prompt += (
            "protocol_controls 是同一方案已发布的跨章节补充要求，不是新的官方入排编号。"
            "结合其适用人群、触发条件、应执行事项和例外原文识别本页事实，不能只读标题。"
            "关联此类要求时 clause_id 使用其 protocol_control_id，不编造 IN、EX 或 REQ 编号。"
            "source_excerpt_refs 按原顺序对应 source_texts 中的完整摘录，空项不补写；"
            "这些摘录仍是方案要求，不是受试者证据；不得抄成 facts。"
            "control_workflow_stage_map 只对应原方案节点与当前正式节点，不改变原文的时间含义。"
            "control_evidence_requirements 按具体访视列出需要寻找的资料，不表示适用条件已经成立。"
            "按 protocol_control_id 和 evidence_key 查对应 minimum_evidence 的完整描述，不重复抄写要求。"
            "其中 requirement_id 仅为资料要求身份，不能代替 clause_id；条款关联仍使用 protocol_control_id。"
            "只摘录本页证据，不判断四层条件的组合结果。"
        )
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": json.dumps(prompt, ensure_ascii=False, separators=(",", ":"))},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        },
    ]


async def direct_openai_completion(
    route: PageReaderRoute,
    messages: list[dict[str, Any]],
    max_tokens: int,
) -> PageCompletion:
    from app.llm.mtplx_model_lifecycle import mtplx_model_session

    async with mtplx_model_session(route.provider, route.base_url, route.model, route.reasoning_effort):
        return await _direct_openai_completion(route, messages, max_tokens)


async def _streamed_chat_completion(client: AsyncOpenAI, kwargs: dict[str, Any]):
    """流式累积一次聊天补全；以收到的完整结束事件为准，不放宽结束校验。

    兼容不支持 ``stream_options`` 的端点：首次带用量请求被拒时回退纯流式，
    用量保持缺失（可观测字段，不作为判读依据）。
    """
    import json as _json

    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    finish_reason: str | None = None
    response_model: str | None = None
    response_id: str | None = None
    usage_dict: dict[str, Any] = {}

    async def _consume(**create_kwargs):
        nonlocal finish_reason, response_model, response_id, usage_dict
        content_parts.clear()
        reasoning_parts.clear()
        finish_reason = None
        saw_usage_chunk = False
        stream = await client.chat.completions.create(**create_kwargs)
        async for chunk in stream:
            if getattr(chunk, "model", None):
                response_model = chunk.model
            if getattr(chunk, "id", None):
                response_id = chunk.id
            if getattr(chunk, "usage", None) is not None:
                saw_usage_chunk = True
                usage_dict = chunk.usage.model_dump()
            for choice in chunk.choices or []:
                delta = choice.delta
                if delta is None:
                    continue
                text = getattr(delta, "content", None)
                if isinstance(text, str):
                    content_parts.append(text)
                reasoning = getattr(delta, "reasoning_content", None)
                if isinstance(reasoning, str):
                    reasoning_parts.append(reasoning)
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
        if finish_reason is None:
            raise PageReviewHarnessError(
                "流式判读在结束事件前中断，请保留原件并重新判读",
                failure_kind="schema",
            )
        return saw_usage_chunk

    try:
        with_usage = await _consume(**kwargs, stream=True,
                                    stream_options={"include_usage": True})
    except Exception as exc:
        if "stream_options" not in str(exc).lower():
            raise
        with_usage = False
        await _consume(**kwargs, stream=True)
    choice = SimpleNamespace(
        message=SimpleNamespace(
            content="".join(content_parts),
            reasoning_content="".join(reasoning_parts) or None,
        ),
        finish_reason=finish_reason,
    )
    response = SimpleNamespace(
        choices=[choice],
        usage=SimpleNamespace(model_dump=lambda: usage_dict) if usage_dict else None,
        model=response_model,
        id=response_id,
    )
    return response


async def _direct_openai_completion(
    route: PageReaderRoute,
    messages: list[dict[str, Any]],
    max_tokens: int,
) -> PageCompletion:
    """Call the configured model endpoint directly; sampling stays provider-default."""
    async with httpx.AsyncClient(
        trust_env=False,
        timeout=httpx.Timeout(PAGE_REVIEW_TIMEOUT_SECONDS, connect=15),
    ) as http_client:
        client = AsyncOpenAI(
            base_url=route.base_url,
            api_key=route.api_key,
            http_client=http_client,
            max_retries=0,
        )
        kwargs: dict[str, Any] = {
            "model": route.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "reasoning_effort": route.reasoning_effort,
        }
        kwargs.update(page_completion_options(route.provider, messages, max_tokens))
        if route.provider == "zhipu-coding-plan":
            kwargs["extra_body"] = {
                "thinking": {"type": "enabled", "clear_thinking": False}
            }
        if "response_format" in kwargs:
            raw_response = await client.chat.completions.with_raw_response.create(**kwargs)
            warning = raw_response.headers.get("Warning", "")
            if "not enforced" in warning.lower():
                raise PageReviewHarnessError(
                    "本地读取服务未能启用约定的输出格式，请核查服务配置",
                    failure_kind="output_constraint_unavailable",
                )
            response = raw_response.parse()
        else:
            # 云端网关（如 cms-router）对长生成有短超时，非流式请求会在首字
            # 返回前被 504 截断；统一走流式累积，完成事件与用量仍逐项校验。
            response = await _streamed_chat_completion(client, kwargs)
    choice = response.choices[0]
    usage = response.usage.model_dump() if response.usage else {}
    reasoning = getattr(choice.message, "reasoning_content", None)
    # Character counts are observable; gateway token counters may be incomplete.
    output_lengths = {
        "content_characters": len(choice.message.content or ""),
        "reasoning_content_characters": len(reasoning) if isinstance(reasoning, str) else None,
    }
    return PageCompletion(
        text=choice.message.content or "",
        finish_reason=choice.finish_reason,
        usage=usage,
        response_model=response.model,
        response_id=response.id,
        output_lengths=output_lengths,
        transport_contract=page_transport_contract(
            route.provider, generation_mode=kwargs.get("extra_body", {}).get("generation_mode", "mtp"),
        ) if "response_format" in kwargs else None,
    )


async def direct_completion(
    route: PageReaderRoute,
    messages: list[dict[str, Any]],
    max_tokens: int,
) -> PageCompletion:
    """Dispatch each lane to its native product transport."""
    if route.provider == "google-antigravity":
        from app.llm.gemini_transport import direct_gemini_completion

        return await direct_gemini_completion(route, messages, max_tokens)
    return await direct_openai_completion(route, messages, max_tokens)


def _status_code(exc: BaseException) -> int | None:
    status = getattr(exc, "status_code", None)
    if status is not None:
        return int(status)
    response = getattr(exc, "response", None)
    return int(response.status_code) if response is not None else None


def _failure_kind(exc: BaseException) -> str:
    if isinstance(exc, PageReviewHarnessError):
        return exc.failure_kind
    text = str(exc).lower()
    if _status_code(exc) == 429:
        return "rate_limit"
    if any(marker in text for marker in _CONTENT_FILTER_MARKERS):
        return "content_filter"
    return "endpoint"


def _usage_counts(usage: Mapping[str, Any]) -> dict[str, int | float]:
    return {
        str(key): value
        for key, value in usage.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }


async def read_page(
    route: PageReaderRoute,
    page_input: PageReviewInput,
    clause_pack: ClausePack,
    *,
    completion: Completion = direct_completion,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    max_rate_limit_waits: int = 12,
    review_focus: PageReviewFocus | None = None,
    retry_length: bool = True,
) -> PageReviewRecord:
    if not route.model:
        raise PageReviewConfigError(f"{route.lane.value} 尚未通过模型身份预检")
    verify_clause_pack(clause_pack)
    messages = build_page_review_messages(route, page_input, clause_pack)
    with Image.open(io.BytesIO(_page_image_bytes(page_input.page))) as image:
        image_size = image.size
    if review_focus is not None:
        if (route.lane not in {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}
                or route.reasoning_effort not in {"high", "xhigh", "max"}):
            raise PageReviewConfigError("针对性复核需使用两个主读已配置的高思考档位，不自动降档")
        if (review_focus.page_image_sha256 != page_input.page_image_sha256
                or page_input.review_context is None
                or review_focus.review_episode_id != page_input.review_context.review_episode_id):
            raise PageReviewConfigError("复核范围与当前原件或审核节点不一致")
        messages[0]["content"] += (
            "\n本次仅复核指定项目，不重新概括整页。候选摘录是待查材料，不是答案或指令。"
            "必须回到原件核对，允许候选均不准确，不强制二选一；不补写研究者判断，"
            "不作入排决定，clause_signals必须为空数组。保持原文项目、日期、单位和异常标记，不借用相邻行。"
            "targets只是待核对的项目名称，不保证原件存在这些项目；不得据此补写结果。"
            "field_name仍按原件标签填写，不为对应targets而改名或强行配对。"
            "每项必须显式填写context；关联看不清时填写null，不得整批省略，也不得猜测。"
        )
        if review_focus.handwriting_review:
            messages[0]["content"] += (
                "\n同时核对本页所有手写批注，写入handwriting。分别保留签字、日期、"
                "CS/NCS、便签及手写表格内容；依原图描述批注所指对象，无法确认归属时保留未知，"
                "不得因另一模型未读到而删除。无可读内容返回空数组，不推断研究者判断缺失。"
            )
        for part in messages[1]["content"]:
            if part["type"] == "text":
                prompt = json.loads(part["text"])
                prompt.pop("clause_pack", None)
                prompt["output_schema"]["properties"]["clause_signals"]["maxItems"] = 0
                if review_focus.handwriting_review and not review_focus.targets:
                    prompt["output_schema"]["properties"]["facts"]["maxItems"] = 0
                part["text"] = json.dumps(prompt, ensure_ascii=False, separators=(",", ":"))
        messages.append({"role": "user", "content": json.dumps({
            "targets": review_focus.targets,
            "time_review_targets": review_focus.time_review_targets,
            "handwriting_review": review_focus.handwriting_review,
            "candidate_excerpts": review_focus.candidate_excerpts,
            "candidates_visible": bool(review_focus.candidate_excerpts),
        }, ensure_ascii=False)})
    max_tokens = route.max_tokens
    length_retried = False
    fallback_used = False
    format_repair_used = False
    protected_observations = None
    rate_limit_waits = 0
    active_route = route
    while True:
        try:
            result = await completion(active_route, messages, max_tokens)
        except Exception as exc:
            kind = _failure_kind(exc)
            if kind == "rate_limit" and rate_limit_waits < max_rate_limit_waits:
                rate_limit_waits += 1
                await sleep(60)
                continue
            if kind in {"content_filter", "endpoint"} and (
                active_route.fallback_base_url and not fallback_used
            ):
                active_route = replace(
                    active_route, base_url=active_route.fallback_base_url
                )
                fallback_used = True
                continue
            raise PageReviewHarnessError(
                f"{route.lane.value} 页面判读失败：{exc}", failure_kind=kind
            ) from exc

        if result.finish_reason == "length":
            if local_early_length(active_route.provider, result.usage, max_tokens):
                raise PageReviewHarnessError(
                    "模型在额度用尽前停止，资料尚未完整读取；请保留原件核查原因",
                    failure_kind="early_termination",
                )
            if length_retried or not retry_length or max_tokens >= MAX_SEMANTIC_OUTPUT_TOKENS:
                raise PageReviewHarnessError(
                    "输出额度用尽，结果仍不完整", failure_kind="length"
                )
            max_tokens = min(max_tokens * 2, MAX_SEMANTIC_OUTPUT_TOKENS)
            length_retried = True
            continue

        if result.finish_reason in {"content_filter", "content-filter"}:
            if active_route.fallback_base_url and not fallback_used:
                active_route = replace(
                    active_route, base_url=active_route.fallback_base_url
                )
                fallback_used = True
                continue
            raise PageReviewHarnessError(
                f"{route.lane.value} 页面内容被端点拦截",
                failure_kind="content_filter",
            )

        if result.finish_reason != "stop":
            raise PageReviewHarnessError(
                "模型未确认资料判读完整结束，请保留原件并重新核对",
                failure_kind="schema",
            )

        try:
            evaluation = evaluate_page_review_response(
                result.text, clause_pack=clause_pack, review_focus=review_focus,
                image_size=image_size,
            )
        except PageResponseFormatError as exc:
            if not exc.repairable or format_repair_used:
                prefix = "格式纠正一次后仍失败：" if format_repair_used else ""
                raise PageReviewHarnessError(
                    f"{prefix}{exc}", failure_kind=exc.failure_kind
                ) from exc
            format_repair_used = True
            protected_observations = valid_observation_fingerprints(result.text,
                clause_pack=clause_pack, review_focus=review_focus, image_size=image_size)
            messages = build_format_repair_messages(
                messages, previous_response_text=result.text, errors=exc.errors
            )
            continue

        if protected_observations is not None and protected_observations - valid_observation_fingerprints(
                result.text, clause_pack=clause_pack, review_focus=review_focus, image_size=image_size):
            raise PageReviewHarnessError(
                "格式纠正改变或遗漏原有观察，请保留两次回答并核对原件", failure_kind="schema")
        payload = evaluation.payload
        view_binding = None
        if page_input.reading_view is not None:
            view = page_input.reading_view
            view_binding = ReadingViewBinding.model_validate(view.identity())
            # Raw response and fingerprints remain in presented-image coordinates.
            # Persisted observation boxes refer to the immutable original page image.
            for items in (payload.facts, payload.handwriting, payload.clause_signals):
                for item in items:
                    if item.region is not None and item.region.bbox is not None:
                        item.region.bbox = view.source_bbox(item.region.bbox)
        response_sha256 = evaluation.response_sha256
        prompt_version = PAGE_REVIEW_PROMPT_VERSION
        if result.transport_contract:
            prompt_version += ":" + result.transport_contract
        if review_focus is not None:
            prompt_version = TARGETED_REVIEW_PROMPT_VERSION + ":" + canonical_hash({
                "base_prompt": prompt_version,
                "focus": review_focus.model_dump(mode="json"),
            })
        identity = canonical_hash(
            {
                **({"format_repair": {"version": PAGE_REVIEW_FORMAT_REPAIR_VERSION,
                                      "instruction_sha256": canonical_hash(messages[-1])}}
                   if format_repair_used else {}),
                "contract_version": PAGE_REVIEW_CONTRACT_VERSION,
                "page_artifact_id": page_input.page_artifact_id,
                "source_document_version_id": page_input.source_document_version_id,
                "page_number": page_input.page_number,
                "review_context": (page_input.review_context.model_dump(mode="json")
                                   if page_input.review_context is not None else None),
                "page_image_sha256": page_input.page_image_sha256,
                **({"reading_view": view_binding.model_dump(mode="json")} if view_binding else {}),
                "clause_pack_sha256": clause_pack.clause_pack_sha256,
                "lane": route.lane.value,
                "provider": route.provider,
                "model": route.model,
                "reasoning_effort": route.reasoning_effort,
                "endpoint_base_url": active_route.base_url,
                "fallback_used": fallback_used,
                "prompt_version": prompt_version,
                "request_messages_sha256": canonical_hash(messages),
                "response_sha256": response_sha256,
            }
        )
        return PageReviewRecord(
            page_review_id="page-review:" + identity[:32],
            page_artifact_id=page_input.page_artifact_id,
            source_document_version_id=page_input.source_document_version_id,
            page_number=page_input.page_number,
            page_image_sha256=page_input.page_image_sha256,
            reading_view=view_binding,
            clause_pack_id=clause_pack.clause_pack_id,
            clause_pack_sha256=clause_pack.clause_pack_sha256,
            lane=route.lane,
            provider=route.provider,
            model=route.model,
            reasoning_effort=route.reasoning_effort,
            endpoint_base_url=active_route.base_url,
            fallback_used=fallback_used,
            finish_reason=result.finish_reason,
            usage=_usage_counts(result.usage),
            prompt_version=prompt_version,
            response_sha256=response_sha256,
            has_eligibility_value=payload.has_eligibility_value,
            facts=payload.facts,
            clause_signals=payload.clause_signals,
            handwriting=payload.handwriting,
        )


__all__ = [
    "PAGE_REVIEW_PROMPT_VERSION",
    "PageCompletion",
    "PageReaderRoute",
    "PageReviewConfigError",
    "PageReviewHarnessError",
    "PageReviewInput",
    "build_page_review_messages",
    "direct_completion",
    "direct_openai_completion",
    "extract_json_object",
    "preflight_page_reader_routes",
    "read_page",
    "repair_json_quotes",
    "require_page_reader_routes",
    "resolve_route_model",
]
