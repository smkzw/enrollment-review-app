#!/bin/zsh
set -eu

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
PYTHON="$APP_DIR/.venv/bin/python"
ENV_FILE="${ENROLLMENT_ENV_FILE:-$APP_DIR/.env}"
if [[ ! -x "$PYTHON" || ! -f "$ENV_FILE" ]]; then
  echo "工作台运行文件或产品配置尚未准备完整，请联系维护人员处理。"
  exit 1
fi

MODE=$(/usr/bin/osascript -e 'choose from list {"开始工作", "仅查看已有资料"} with title "入排审核工作台" with prompt "请选择本次打开方式" default items {"开始工作"}') || exit 0
[[ "$MODE" == "false" ]] && exit 0
ARGS=(--env-file "$ENV_FILE")
[[ "$MODE" == "仅查看已有资料" ]] && ARGS+=(--browse-only)
echo "正在打开工作台。请保留此窗口；关闭窗口将结束本次服务。"
exec "$PYTHON" -m scripts.run_v2_desktop "${ARGS[@]}"
