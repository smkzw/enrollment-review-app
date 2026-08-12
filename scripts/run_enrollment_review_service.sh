#!/bin/zsh
set -eu

APP_DIR="/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app"
PORT_FILE="$APP_DIR/output/runtime_state/port"
if [ -z "${PORT:-}" ] && [ -f "$PORT_FILE" ]; then
  PORT="$(tr -cd '0-9' < "$PORT_FILE")"
fi
PORT="${PORT:-8901}"
LOG_DIR="$APP_DIR/output/runtime_logs"
APP_LOG="$LOG_DIR/enrollment-review-uvicorn.log"

export HOME="/Users/smkzw"
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
