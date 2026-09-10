#!/bin/zsh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/../app/main.py" ]; then
  APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  APP_DIR="${ENROLLMENT_REVIEW_APP_DIR:-/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app}"
fi

# The double-click launcher records validated local-model and graded semantic
# routing keys. Import only the allowlisted keys; do not source arbitrary shell
# content from the runtime state file.
MODEL_RUNTIME_ENV_FILE="$APP_DIR/output/runtime_state/model-services.env"
if [ -f "$MODEL_RUNTIME_ENV_FILE" ]; then
  while IFS='=' read -r key value; do
    case "$key" in
      MTPLX_BASE_URL|MTPLX_PORT|MTPLX_MODEL|MTPLX_REASONING_EFFORT|DECONSTRUCT_ROUTE_MODE|DECONSTRUCT_BACKEND|DECONSTRUCT_MODEL|DECONSTRUCT_REASONING_EFFORT|DECONSTRUCT_GLM_PROVIDER|DECONSTRUCT_GLM_MODEL|DECONSTRUCT_GLM_REASONING_EFFORT|DECONSTRUCT_FALLBACK_DEEPSEEK_MODEL|DECONSTRUCT_FALLBACK_DEEPSEEK_REASONING_EFFORT|ENROLLMENT_ENV_FILE|ENROLLMENT_SEMANTIC_ROUTE_PREFLIGHT|ENROLLMENT_SEMANTIC_ROUTE_PREFLIGHT_MODE|ENROLLMENT_SEMANTIC_ENDPOINT_PREFLIGHT)
        export "$key=$value"
        ;;
    esac
  done < "$MODEL_RUNTIME_ENV_FILE"
fi

# Explicit worktree/dedicated env-file contract. Prefer an already-exported
# ENROLLMENT_ENV_FILE; otherwise point at this checkout's .env when present so
# uvicorn import-time config loading can resolve DECONSTRUCT_GLM_API_KEY.
if [ -z "${ENROLLMENT_ENV_FILE:-}" ] && [ -f "$APP_DIR/.env" ]; then
  export ENROLLMENT_ENV_FILE="$APP_DIR/.env"
fi
if [[ "$APP_DIR" == */.worktrees/* ]] && [ -z "${ENROLLMENT_ENV_FILE:-}" ]; then
  echo "【启动失败】worktree 必须通过 ENROLLMENT_ENV_FILE 显式指定环境文件。" >&2
  exit 1
fi

PORT_FILE="$APP_DIR/output/runtime_state/port"
if [ -z "${PORT:-}" ] && [ -f "$PORT_FILE" ]; then
  PORT="$(tr -cd '0-9' < "$PORT_FILE")"
fi
PORT="${PORT:-8901}"
LOG_DIR="$APP_DIR/output/runtime_logs"
APP_LOG="$LOG_DIR/enrollment-review-uvicorn.log"

export HOME="${HOME:-/Users/smkzw}"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONUNBUFFERED="1"

mkdir -p "$LOG_DIR"
cd "$APP_DIR"

{
  echo "----- $(date '+%Y-%m-%d %H:%M:%S') enrollment review service start -----"
  echo "pwd=$(pwd)"
  echo "python=$(/usr/bin/python3 --version 2>&1)"
  echo "port=$PORT"
} >> "$APP_LOG" 2>&1

exec /usr/bin/python3 -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --loop asyncio
