#!/bin/zsh
# start_v2_uat.command — 双击运行：V2 正式界面试用一键启动
# 面向不会使用终端的中文医学监查人员；本文件只负责调用核心逻辑并停留窗口。
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

zsh "$APP_DIR/scripts/start_v2_uat.sh"
STATUS=$?

echo ""
if [ "$STATUS" -eq 0 ]; then
  echo "试用服务已就绪，浏览器已为您打开。关闭本窗口后，服务仍会继续运行。"
else
  echo "本次启动未能完成，请按上方提示操作。"
fi
echo "按回车键关闭本窗口…"
read -r
exit "$STATUS"
