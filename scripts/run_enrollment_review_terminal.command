#!/bin/zsh
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/../app/main.py" ]; then
  APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  APP_DIR="${ENROLLMENT_REVIEW_APP_DIR:-/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app}"
fi
PORT_FILE="$APP_DIR/output/runtime_state/port"
if [ -z "${PORT:-}" ] && [ -f "$PORT_FILE" ]; then
  PORT="$(tr -cd '0-9' < "$PORT_FILE")"
fi
PORT="${PORT:-8901}"
export PORT
APP_URL="http://127.0.0.1:$PORT"

clear
echo "=========================================="
echo "  临床试验入排审核系统服务窗口"
echo "=========================================="
echo "服务启动后，请保留这个窗口。关闭窗口会停止入排审核服务。"
echo "系统页面: $APP_URL"
echo ""

exec "$APP_DIR/scripts/run_enrollment_review_service.sh"
