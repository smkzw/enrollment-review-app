#!/bin/zsh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/../app/main.py" ]; then
  APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  APP_DIR="${ENROLLMENT_REVIEW_APP_DIR:-/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app}"
fi
# Finder/LaunchAgent 环境的 PATH 很精简；MTPLX 常安装在用户本地目录。
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

dotenv_value() {
  [ -f "$APP_DIR/.env" ] || return 0
  /usr/bin/python3 - "$APP_DIR/.env" "$1" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
wanted = sys.argv[2]
try:
    lines = path.read_text(encoding="utf-8").splitlines()
except OSError:
    raise SystemExit(0)
for raw in lines:
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    if key.strip() != wanted:
        continue
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    print(value)
    break
PY
}

url_port() {
  /usr/bin/python3 - "$1" <<'PY'
from urllib.parse import urlparse
import sys

try:
    port = urlparse(sys.argv[1]).port
except ValueError:
    port = None
if port:
    print(port)
PY
}

configured_url="${MTPLX_BASE_URL:-}"
if [ -z "$configured_url" ]; then
  configured_url="$(dotenv_value MTPLX_BASE_URL)"
fi
MTPLX_BASE_URL="${configured_url:-http://127.0.0.1:8002}"
MTPLX_PORT="${MTPLX_PORT:-}"
if [ -z "$MTPLX_PORT" ]; then
  MTPLX_PORT="$(dotenv_value MTPLX_PORT)"
fi
MTPLX_PORT="${MTPLX_PORT:-$(url_port "$MTPLX_BASE_URL")}"
MTPLX_PORT="${MTPLX_PORT:-8002}"
MTPLX_MODEL="${MTPLX_MODEL:-$(dotenv_value MTPLX_MODEL)}"
MTPLX_MODEL="${MTPLX_MODEL:-mtplx-flash-next-optimized-speed}"
MTPLX_REASONING_EFFORT="${MTPLX_REASONING_EFFORT:-$(dotenv_value MTPLX_REASONING_EFFORT)}"
MTPLX_REASONING_EFFORT="${MTPLX_REASONING_EFFORT:-medium}"
MTPLX_BIN="${MTPLX_BIN:-}"
if [ -z "$MTPLX_BIN" ]; then
  MTPLX_BIN="$(command -v mtplx || true)"
fi

case "$MTPLX_REASONING_EFFORT" in
  auto|low|medium|high|xhigh) ;;
  *)
    echo "【MTPLX启动失败】推理强度设置不正确：$MTPLX_REASONING_EFFORT" >&2
    exit 2
    ;;
esac

if [ -z "$MTPLX_BIN" ] || [ ! -x "$MTPLX_BIN" ]; then
  echo "【MTPLX启动失败】未找到可执行的 mtplx 命令。" >&2
  exit 127
fi

LOG_DIR="$APP_DIR/output/runtime_logs"
mkdir -p "$LOG_DIR"
cd "$APP_DIR"

{
  echo "----- $(date '+%Y-%m-%d %H:%M:%S') MTPLX semantic service start -----"
  echo "pwd=$(pwd)"
  echo "mtplx=$MTPLX_BIN"
  echo "base_url=$MTPLX_BASE_URL"
  echo "port=$MTPLX_PORT"
  echo "model=$MTPLX_MODEL"
  echo "reasoning_effort=$MTPLX_REASONING_EFFORT"
} >&2

exec "$MTPLX_BIN" quickstart \
  --host 127.0.0.1 \
  --port "$MTPLX_PORT" \
  --model "$MTPLX_MODEL" \
  --model-id "$MTPLX_MODEL" \
  --reasoning-effort "$MTPLX_REASONING_EFFORT" \
  --no-stats-footer
