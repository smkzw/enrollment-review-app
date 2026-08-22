"""Application configuration."""
import json
import os
from pathlib import Path

# Load .env file if it exists
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
PROJECTS_DIR = ROOT_DIR / "projects"
STATIC_DIR = ROOT_DIR / "static"

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

# OCR models (all local oMLX)
OCR_MODEL_LONG = os.getenv("OCR_MODEL_LONG", "models--PaddlePaddle--PaddleOCR-VL-1.6")
OCR_MODEL_SHORT = os.getenv("OCR_MODEL_SHORT", "models--PaddlePaddle--PaddleOCR-VL-1.6")
OCR_LONG_PAGE_THRESHOLD = int(os.getenv("OCR_LONG_PAGE_THRESHOLD", "5"))
OCR_DPI = int(os.getenv("OCR_DPI", "180"))
OCR_MAX_CONCURRENT = int(os.getenv("OCR_MAX_CONCURRENT", "8"))
OCR_BACKEND = os.getenv("OCR_BACKEND", "omlx")
OCR_NATIVE_HIGH_PRECISION_REVIEW = os.getenv("OCR_NATIVE_HIGH_PRECISION_REVIEW", "1").lower() not in {"0", "false", "no"}

# Review model (local oMLX)
REVIEW_MODEL = os.getenv("REVIEW_MODEL", "Qwen3.6-27B-oQ8-mtp")
REVIEW_BACKEND = os.getenv("REVIEW_BACKEND", "omlx")
REVIEW_REASONING_EFFORT = os.getenv("REVIEW_REASONING_EFFORT", "default").strip().lower()

# DeepSeek (remote fallback)
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# MiniMax (optional remote fallback)
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://mimimax.cn/v1")
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M3")

# Server
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8900"))

# Limits
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(100 * 1024 * 1024)))  # 100 MB default

# Deconstruction (uses same model family as review, but configurable separately)
DECONSTRUCT_BACKEND = os.getenv("DECONSTRUCT_BACKEND", REVIEW_BACKEND)
DECONSTRUCT_MODEL = os.getenv("DECONSTRUCT_MODEL", REVIEW_MODEL)
DECONSTRUCT_REASONING_EFFORT = os.getenv(
    "DECONSTRUCT_REASONING_EFFORT", REVIEW_REASONING_EFFORT
).strip().lower()
DECONSTRUCT_MAX_TOKENS = int(os.getenv("DECONSTRUCT_MAX_TOKENS", "60000"))
