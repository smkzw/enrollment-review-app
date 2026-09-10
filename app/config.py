"""Application configuration."""
import json
import os
from collections.abc import Mapping, MutableMapping
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
PROJECTS_DIR = ROOT_DIR / "projects"
STATIC_DIR = ROOT_DIR / "static"

ENROLLMENT_ENV_FILE_VAR = "ENROLLMENT_ENV_FILE"


def _strip_env_value(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def parse_env_file_values(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines from an env file. Never returns secret semantics."""

    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(
            f"无法读取环境文件（{ENROLLMENT_ENV_FILE_VAR}={path}）：{exc.strerror or exc}"
        ) from exc
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        name = key.strip()
        if not name:
            continue
        values[name] = _strip_env_value(value)
    return values


def resolve_enrollment_env_file(
    *,
    environ: Mapping[str, str] | None = None,
    default_env_path: Path | None = None,
) -> Path | None:
    """Resolve the explicit env-file contract for worktree / dedicated processes.

    - If ``ENROLLMENT_ENV_FILE`` is set, that path is required and authoritative
      for unset process variables.
    - Otherwise fall back to ``<repo>/.env`` when present (compatibility).
    """

    env = os.environ if environ is None else environ
    raw = str(env.get(ENROLLMENT_ENV_FILE_VAR, "") or "").strip()
    if raw:
        path = Path(_strip_env_value(raw)).expanduser()
        if not path.is_absolute():
            path = (ROOT_DIR / path).resolve()
        else:
            path = path.resolve()
        if not path.is_file():
            raise RuntimeError(
                "【启动失败】显式环境文件不存在或不是普通文件："
                f"{ENROLLMENT_ENV_FILE_VAR}={path}。"
                "请为 worktree / 专用 V2 进程设置可读的环境文件，"
                "或在启动前显式注入所需密钥变量。"
            )
        return path
    fallback = default_env_path if default_env_path is not None else ROOT_DIR / ".env"
    if fallback.is_file():
        return fallback.resolve()
    return None


def load_enrollment_env_file(
    *,
    environ: MutableMapping[str, str] | None = None,
    default_env_path: Path | None = None,
) -> Path | None:
    """Load env values with ``setdefault`` so process exports win.

    Returns the loaded path, or ``None`` when no file was loaded. Raises a
    Chinese ``RuntimeError`` when ``ENROLLMENT_ENV_FILE`` is set but unreadable.
    Secret values are never included in the exception text.
    """

    env: MutableMapping[str, str] = os.environ if environ is None else environ
    path = resolve_enrollment_env_file(
        environ=env,
        default_env_path=default_env_path,
    )
    if path is None:
        return None
    values = parse_env_file_values(path)
    for key, value in values.items():
        env.setdefault(key, value)
    # Record the resolved path for diagnostics without echoing secrets.
    env.setdefault(ENROLLMENT_ENV_FILE_VAR, str(path))
    return path


# Worktree / dedicated V2 contract: prefer ENROLLMENT_ENV_FILE, else repo .env.
ENROLLMENT_ENV_FILE_LOADED = load_enrollment_env_file()
ENROLLMENT_ENV_FILE = (
    str(ENROLLMENT_ENV_FILE_LOADED) if ENROLLMENT_ENV_FILE_LOADED is not None else ""
)

def _discover_omlx_base_url(config_path: Path | None = None) -> str:
    """Read the macOS oMLX app's configured port, with a stable local fallback."""
    path = config_path or (
        Path.home() / "Library" / "Application Support" / "oMLX" / "config.json"
    )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        port = int(payload["port"])
        if 1 <= port <= 65535:
            return f"http://127.0.0.1:{port}"
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return "http://127.0.0.1:8000"


# oMLX local model server. Explicit environment configuration remains authoritative;
# otherwise follow the port selected by the installed oMLX macOS application.
OMLX_BASE_URL = os.getenv("OMLX_BASE_URL", _discover_omlx_base_url())
OMLX_API_KEY = os.getenv("OMLX_API_KEY", "")

# MTPLX local OpenAI-compatible semantic model service.  Keep this connection
# profile separate from oMLX: oMLX remains the OCR backend below.
MTPLX_BASE_URL = os.getenv("MTPLX_BASE_URL", "http://127.0.0.1:8002")
MTPLX_API_KEY = os.getenv("MTPLX_API_KEY", "")
MTPLX_MODEL = os.getenv(
    "MTPLX_MODEL", "mtplx-flash-next-optimized-speed"
).strip()
MTPLX_REASONING_EFFORT = os.getenv("MTPLX_REASONING_EFFORT", "medium").strip().lower()

# OCR models (all local oMLX)
OCR_MODEL_LONG = os.getenv("OCR_MODEL_LONG", "models--PaddlePaddle--PaddleOCR-VL-1.6")
OCR_MODEL_SHORT = os.getenv("OCR_MODEL_SHORT", "models--PaddlePaddle--PaddleOCR-VL-1.6")
OCR_LONG_PAGE_THRESHOLD = int(os.getenv("OCR_LONG_PAGE_THRESHOLD", "5"))
OCR_DPI = int(os.getenv("OCR_DPI", "180"))
OCR_MAX_CONCURRENT = int(os.getenv("OCR_MAX_CONCURRENT", "8"))
OCR_BACKEND = os.getenv("OCR_BACKEND", "omlx")
OCR_NATIVE_HIGH_PRECISION_REVIEW = os.getenv("OCR_NATIVE_HIGH_PRECISION_REVIEW", "1").lower() not in {"0", "false", "no"}

# Review model.  Semantic review is routed to MTPLX by default; OCR is still
# independently controlled by OCR_BACKEND and the oMLX settings above.
REVIEW_MODEL = os.getenv("REVIEW_MODEL", MTPLX_MODEL).strip()
REVIEW_BACKEND = os.getenv("REVIEW_BACKEND", "mtplx").strip().lower()
REVIEW_REASONING_EFFORT = os.getenv(
    "REVIEW_REASONING_EFFORT", MTPLX_REASONING_EFFORT
).strip().lower()

# DeepSeek (remote fallback)
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# MiniMax (optional remote fallback)
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://mimimax.cn/v1")
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M3")

# Independent VLM (智谱 BigModel). Used only for raw DOCX/PDF page vision
# verification and source-locator fidelity checks. Semantic review / OCR /
# protocol-control routes remain task-isolated and do not inherit this profile.
INDEPENDENT_VLM_PROVIDER = os.getenv(
    "INDEPENDENT_VLM_PROVIDER", "zhipu-coding-plan"
).strip().lower()
INDEPENDENT_VLM_BASE_URL = os.getenv(
    "INDEPENDENT_VLM_BASE_URL",
    # Product-owned direct Coding Plan endpoint; no external harness proxy.
    "https://open.bigmodel.cn/api/coding/paas/v4",
).strip()
INDEPENDENT_VLM_API_KEY = os.getenv("INDEPENDENT_VLM_API_KEY", "")
INDEPENDENT_VLM_MODEL = os.getenv("INDEPENDENT_VLM_MODEL", "glm-5.3-flash").strip()
INDEPENDENT_VLM_REASONING_EFFORT = os.getenv(
    "INDEPENDENT_VLM_REASONING_EFFORT", "high"
).strip().lower()
INDEPENDENT_VLM_MAX_TOKENS = int(os.getenv("INDEPENDENT_VLM_MAX_TOKENS", "8192"))
INDEPENDENT_VLM_TIMEOUT_SECONDS = float(
    os.getenv("INDEPENDENT_VLM_TIMEOUT_SECONDS", "180")
)

# Gemini (google-antigravity native vision transport) main-B. The access
# token and project ID are main-thread explicit env credentials: no runtime
# discovery, no home-config reads, never logged. The endpoint default is the
# verified antigravity host and stays env-overridable.
GEMINI_ACCESS_TOKEN = os.getenv("GEMINI_ACCESS_TOKEN", "").strip()
GEMINI_PROJECT_ID = os.getenv("GEMINI_PROJECT_ID", "").strip()
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL", "https://daily-cloudcode-pa.googleapis.com"
).strip()

# Phase 5.5 single-stage page review. These are product-owned direct routes;
# external agent harnesses are reviewers only and never supply runtime config.
PAGE_REVIEW_MAIN_A_BASE_URL = os.getenv(
    "PAGE_REVIEW_MAIN_A_BASE_URL", INDEPENDENT_VLM_BASE_URL
).strip()
PAGE_REVIEW_MAIN_A_API_KEY = (
    os.getenv("PAGE_REVIEW_MAIN_A_API_KEY", "").strip() or INDEPENDENT_VLM_API_KEY
)
PAGE_REVIEW_MAIN_A_MODEL = os.getenv(
    "PAGE_REVIEW_MAIN_A_MODEL", "glm-5.3-flash"
).strip()
PAGE_REVIEW_MAIN_A_FALLBACK_BASE_URL = os.getenv(
    "PAGE_REVIEW_MAIN_A_FALLBACK_BASE_URL", ""
).strip()
PAGE_REVIEW_MAIN_B_PROVIDER = os.getenv(
    "PAGE_REVIEW_MAIN_B_PROVIDER", "google-antigravity"
).strip()
PAGE_REVIEW_MAIN_B_BASE_URL = os.getenv(
    "PAGE_REVIEW_MAIN_B_BASE_URL",
    GEMINI_BASE_URL if PAGE_REVIEW_MAIN_B_PROVIDER == "google-antigravity"
    else ("http://127.0.0.1:8002/v1" if PAGE_REVIEW_MAIN_B_PROVIDER in {"mlx-serve", "mtplx"} else ""),
).strip()
PAGE_REVIEW_MAIN_B_API_KEY = (
    os.getenv("PAGE_REVIEW_MAIN_B_API_KEY", "").strip()
    or (os.getenv("CMS_SMK_API_KEY", "").strip() if PAGE_REVIEW_MAIN_B_PROVIDER == "cms-smk" else "")
)
PAGE_REVIEW_MAIN_B_MODEL = os.getenv(
    "PAGE_REVIEW_MAIN_B_MODEL", "gemini-3.7-flash"
).strip()
PAGE_REVIEW_MAIN_B_FALLBACK_BASE_URL = os.getenv(
    "PAGE_REVIEW_MAIN_B_FALLBACK_BASE_URL", ""
).strip()
PAGE_REVIEW_MAX_TOKENS = int(os.getenv("PAGE_REVIEW_MAX_TOKENS", "65536"))
PAGE_REVIEW_CLOUD_CONCURRENCY = int(
    os.getenv("PAGE_REVIEW_CLOUD_CONCURRENCY", "3")
)
PAGE_REVIEW_TIMEOUT_SECONDS = float(
    os.getenv("PAGE_REVIEW_TIMEOUT_SECONDS", "900")
)

# Selective page-risk vision review (Independent VLM). Native text remains
# primary; only scan/table/anomaly/low-confidence pages may call vision.
SELECTIVE_VISION_ENABLED = os.getenv(
    "SELECTIVE_VISION_ENABLED", "true"
).strip().lower() in {"1", "true", "yes", "on"}
SELECTIVE_VISION_OCR_CONFIDENCE_THRESHOLD = float(
    os.getenv("SELECTIVE_VISION_OCR_CONFIDENCE_THRESHOLD", "0.80")
)
SELECTIVE_VISION_MAX_PAGES_PER_CALL = int(
    os.getenv("SELECTIVE_VISION_MAX_PAGES_PER_CALL", "1")
)

# Server
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8900"))

# Limits
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(100 * 1024 * 1024)))  # 100 MB default

# Protocol deconstruction has its own provider/model contract.  Do not inherit
# the legacy review defaults: the two tasks have different prompts, output
# budgets, and model availability.  Every value remains explicitly overridable
# for isolated runs or a deliberately selected remote backend.
DECONSTRUCT_BACKEND = os.getenv("DECONSTRUCT_BACKEND", "mtplx").strip().lower()
DECONSTRUCT_MODEL = os.getenv(
    "DECONSTRUCT_MODEL", MTPLX_MODEL
).strip()
DECONSTRUCT_REASONING_EFFORT = os.getenv(
    "DECONSTRUCT_REASONING_EFFORT", MTPLX_REASONING_EFFORT
).strip().lower()
DECONSTRUCT_MAX_TOKENS = int(os.getenv("DECONSTRUCT_MAX_TOKENS", "60000"))
# Strict local batches contain only 1-3 parent rules; keep constrained decoding
# from inheriting the legacy 60k-token budget. DeepSeek keeps DECONSTRUCT_MAX_TOKENS.
OMLX_PROTOCOL_BATCH_MAX_TOKENS = int(
    os.getenv("OMLX_PROTOCOL_BATCH_MAX_TOKENS", "8192")
)
MTPLX_PROTOCOL_BATCH_MAX_TOKENS = int(
    os.getenv("MTPLX_PROTOCOL_BATCH_MAX_TOKENS", "16384")
)

# Graded semantic-model routing for protocol deconstruction.  ``graded`` picks
# an ordered candidate chain by task size; ``pinned`` keeps the historical
# single DECONSTRUCT_BACKEND/MODEL identity with no auto provider chain.
# This profile owns its model, endpoint, and effort. It may reuse the same
# BigModel account credential as Independent VLM so a local single-user setup
# does not require the user to paste the same secret twice.
DECONSTRUCT_ROUTE_MODE = os.getenv("DECONSTRUCT_ROUTE_MODE", "graded").strip().lower()
DECONSTRUCT_SHORT_PROMPT_MAX_INPUT_TOKENS = int(
    os.getenv("DECONSTRUCT_SHORT_PROMPT_MAX_INPUT_TOKENS", "4096")
)
DECONSTRUCT_ROUTE_COMPLEX = os.getenv("DECONSTRUCT_ROUTE_COMPLEX", "").strip()
DECONSTRUCT_ROUTE_SHORT = os.getenv("DECONSTRUCT_ROUTE_SHORT", "").strip()
DECONSTRUCT_GLM_PROVIDER = os.getenv(
    "DECONSTRUCT_GLM_PROVIDER", "zhipu-coding-plan"
).strip().lower()
DECONSTRUCT_GLM_BASE_URL = os.getenv(
    "DECONSTRUCT_GLM_BASE_URL",
    "https://open.bigmodel.cn/api/coding/paas/v4",
).strip()
DECONSTRUCT_GLM_API_KEY = (
    os.getenv("DECONSTRUCT_GLM_API_KEY", "").strip() or INDEPENDENT_VLM_API_KEY
)
DECONSTRUCT_GLM_MODEL = os.getenv("DECONSTRUCT_GLM_MODEL", "glm-5.3-flash").strip()
DECONSTRUCT_GLM_REASONING_EFFORT = os.getenv(
    "DECONSTRUCT_GLM_REASONING_EFFORT", "high"
).strip().lower()
DECONSTRUCT_FALLBACK_DEEPSEEK_MODEL = os.getenv(
    "DECONSTRUCT_FALLBACK_DEEPSEEK_MODEL", "deepseek-v4-flash"
).strip()
DECONSTRUCT_FALLBACK_DEEPSEEK_REASONING_EFFORT = os.getenv(
    "DECONSTRUCT_FALLBACK_DEEPSEEK_REASONING_EFFORT", "high"
).strip().lower()

# Oversized official-parent structural segmentation (project-agnostic).
# Enabled only when the planner can emit >=2 parallel-safe segments; token size
# alone never forces an unsafe cut. Default concurrency is 2 with hard cap 3.
DECONSTRUCT_PARENT_SEGMENTATION_ENABLED = os.getenv(
    "DECONSTRUCT_PARENT_SEGMENTATION_ENABLED", "true"
).strip().lower() in {"1", "true", "yes", "on"}
DECONSTRUCT_PARENT_SEGMENT_MAX_CONCURRENCY = int(
    os.getenv("DECONSTRUCT_PARENT_SEGMENT_MAX_CONCURRENCY", "2")
)
DECONSTRUCT_PARENT_SEGMENT_SOFT_INPUT_TOKENS = int(
    os.getenv("DECONSTRUCT_PARENT_SEGMENT_SOFT_INPUT_TOKENS", "8000")
)
DECONSTRUCT_PARENT_SEGMENT_MIN_SOURCE_SPANS = int(
    os.getenv("DECONSTRUCT_PARENT_SEGMENT_MIN_SOURCE_SPANS", "4")
)
DECONSTRUCT_PARENT_SEGMENT_MIN_OBLIGATIONS = int(
    os.getenv("DECONSTRUCT_PARENT_SEGMENT_MIN_OBLIGATIONS", "3")
)
DECONSTRUCT_PARENT_SEGMENT_SOFT_TOKENS = int(
    os.getenv("DECONSTRUCT_PARENT_SEGMENT_SOFT_TOKENS", "3500")
)
DECONSTRUCT_PARENT_SEGMENT_MAX_UNITS_PER_SEGMENT = int(
    os.getenv("DECONSTRUCT_PARENT_SEGMENT_MAX_UNITS_PER_SEGMENT", "3")
)

# Evidence Normalizer 使用独立运行配置；不得继承方案解构配置后误选其他任务模型。
EVIDENCE_NORMALIZER_PROVIDER = os.getenv(
    "EVIDENCE_NORMALIZER_PROVIDER", "zhipu-coding-plan"
).strip().lower()
EVIDENCE_NORMALIZER_MODEL = os.getenv(
    "EVIDENCE_NORMALIZER_MODEL", "glm-5.3-flash"
).strip()
EVIDENCE_NORMALIZER_REASONING_EFFORT = os.getenv(
    "EVIDENCE_NORMALIZER_REASONING_EFFORT", "high"
).strip().lower()
EVIDENCE_NORMALIZER_MAX_TOKENS = int(
    os.getenv("EVIDENCE_NORMALIZER_MAX_TOKENS", "65536")
)
EVIDENCE_NORMALIZER_MAX_PAGES_PER_CALL = int(
    os.getenv("EVIDENCE_NORMALIZER_MAX_PAGES_PER_CALL", "2")
)
_evidence_normalizer_temperature = os.getenv(
    "EVIDENCE_NORMALIZER_TEMPERATURE", ""
).strip()
EVIDENCE_NORMALIZER_TEMPERATURE = (
    float(_evidence_normalizer_temperature)
    if _evidence_normalizer_temperature
    else None
)
# Evidence Normalizer 默认直连 zhipu-coding-plan GLM；显式配置才可切换路由。
# 产品运行和真实测试都不得从 Hermes、OMP 或其他 harness 读取凭据或代理请求。
# 密钥留空时按 DECONSTRUCT_GLM_API_KEY（其自身回退 INDEPENDENT_VLM_API_KEY）
# 复用同一 BigModel 账号凭据，单机单用户无需重复粘贴同一个密钥。
EVIDENCE_NORMALIZER_GLM_BASE_URL = os.getenv(
    "EVIDENCE_NORMALIZER_GLM_BASE_URL",
    "https://open.bigmodel.cn/api/coding/paas/v4",
).strip()
EVIDENCE_NORMALIZER_GLM_API_KEY = (
    os.getenv("EVIDENCE_NORMALIZER_GLM_API_KEY", "").strip()
    or DECONSTRUCT_GLM_API_KEY
)
EVIDENCE_NORMALIZER_GLM_MODEL = os.getenv(
    "EVIDENCE_NORMALIZER_GLM_MODEL", "glm-5.3-flash"
).strip()
EVIDENCE_NORMALIZER_GLM_REASONING_EFFORT = os.getenv(
    "EVIDENCE_NORMALIZER_GLM_REASONING_EFFORT", "high"
).strip().lower()

# Other-protocol control Agent uses an independent connection profile so it
# cannot silently inherit the official IN/EX deconstruction Schema or route.
PROTOCOL_CONTROL_BACKEND = os.getenv(
    "PROTOCOL_CONTROL_BACKEND", "mtplx"
).strip().lower()
PROTOCOL_CONTROL_MODEL = os.getenv(
    "PROTOCOL_CONTROL_MODEL", MTPLX_MODEL
).strip()
PROTOCOL_CONTROL_REASONING_EFFORT = os.getenv(
    "PROTOCOL_CONTROL_REASONING_EFFORT", MTPLX_REASONING_EFFORT
).strip().lower()
PROTOCOL_CONTROL_MAX_TOKENS = int(
    os.getenv("PROTOCOL_CONTROL_MAX_TOKENS", str(DECONSTRUCT_MAX_TOKENS))
)

# Adaptive discovery packing / limited concurrency (project-agnostic).
# Default on for new jobs so fixed 48-unit serial packs are not the product path.
PROTOCOL_CONTROL_ADAPTIVE_BATCHING = os.getenv(
    "PROTOCOL_CONTROL_ADAPTIVE_BATCHING", "true"
).strip().lower() in {"1", "true", "yes", "on"}
PROTOCOL_CONTROL_DISCOVERY_MAX_INPUT_TOKENS = int(
    os.getenv("PROTOCOL_CONTROL_DISCOVERY_MAX_INPUT_TOKENS", "16000")
)
PROTOCOL_CONTROL_DISCOVERY_MAX_OUTPUT_TOKENS = int(
    os.getenv(
        "PROTOCOL_CONTROL_DISCOVERY_MAX_OUTPUT_TOKENS",
        str(min(8192, PROTOCOL_CONTROL_MAX_TOKENS)),
    )
)
PROTOCOL_CONTROL_DISCOVERY_OUTPUT_TOKENS_PER_UNIT = int(
    os.getenv("PROTOCOL_CONTROL_DISCOVERY_OUTPUT_TOKENS_PER_UNIT", "280")
)
PROTOCOL_CONTROL_DISCOVERY_TEMPLATE_OVERHEAD_TOKENS = int(
    os.getenv("PROTOCOL_CONTROL_DISCOVERY_TEMPLATE_OVERHEAD_TOKENS", "3500")
)
PROTOCOL_CONTROL_DISCOVERY_CHARS_PER_TOKEN = float(
    os.getenv("PROTOCOL_CONTROL_DISCOVERY_CHARS_PER_TOKEN", "1.2")
)
PROTOCOL_CONTROL_DISCOVERY_ADAPTIVE_UNIT_CAP = int(
    os.getenv("PROTOCOL_CONTROL_DISCOVERY_ADAPTIVE_UNIT_CAP", "24")
)
# Independent discovery batches only; 1 keeps the historical serial runner path.
PROTOCOL_CONTROL_DISCOVERY_MAX_PARALLEL = int(
    os.getenv("PROTOCOL_CONTROL_DISCOVERY_MAX_PARALLEL", "4")
)
