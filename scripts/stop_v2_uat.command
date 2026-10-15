#!/bin/zsh
# stop_v2_uat.command — 双击运行：停止 V2 正式界面试用服务
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

zsh "$APP_DIR/scripts/stop_v2_uat.sh"
STATUS=$?

echo ""
echo "按回车键关闭本窗口…"
read -r
exit "$STATUS"
