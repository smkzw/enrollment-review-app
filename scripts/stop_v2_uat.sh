#!/bin/zsh
# ============================================================
# stop_v2_uat.sh — V2 正式界面试用停止（核心逻辑）
# 只结束「能确认归属」的试用服务，四重确认缺一不可：
#   PID 记录存在且为数字 + 进程仍存在 + 端口监听程序正是该 PID
#   + 版本标记确认为 V2。
# 任一条件不满足都不结束任何程序。
# ============================================================
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
STATE_DIR="${V2_UAT_STATE_DIR:-$APP_DIR/output/v2_uat_runtime}"
PID_FILE="$STATE_DIR/server.pid"
V2_SERVICE_ID="enrollment-review-v2"

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

marker_service() {
  /usr/bin/curl -fsS --connect-timeout 2 --max-time 3 "$1" 2>/dev/null \
    | /usr/bin/python3 -c 'import sys, json
try:
    print(json.load(sys.stdin).get("service", ""))
except Exception:
    pass' 2>/dev/null
}

is_v2_at() {
  [ "$(marker_service "http://127.0.0.1:$1/uat-status.json")" = "$V2_SERVICE_ID" ]
}

port_in_use() {
  /usr/sbin/lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

if [ ! -f "$PID_FILE" ]; then
  echo "当前没有正在运行的试用服务，无需再次停止。"
  exit 0
fi

PID="$(awk 'NR==1{print $1}' "$PID_FILE" 2>/dev/null)"
PORT="$(awk 'NR==2{print $1}' "$PID_FILE" 2>/dev/null)"

if [[ ! "$PID" =~ ^[0-9]+$ || ! "$PORT" =~ ^[0-9]+$ ]]; then
  echo "启动记录已损坏，无法确认试用服务归属；未结束任何程序。"
  echo "请联系管理员处理。"
  exit 1
fi

if ! kill -0 "$PID" 2>/dev/null; then
  echo "试用服务此前已停止（记录中的进程已不存在）。"
  rm -f "$PID_FILE"
  exit 0
fi

if ! port_in_use "$PORT"; then
  echo "试用服务此前已停止（端口 $PORT 已无监听程序）。"
  rm -f "$PID_FILE"
  exit 0
fi

LISTENER_PID="$(/usr/sbin/lsof -t -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -1)"
if [ "$LISTENER_PID" != "$PID" ]; then
  echo "端口 $PORT 上的监听程序与启动记录不一致，无法确认归属；未结束任何程序。"
  echo "请联系管理员处理。"
  exit 1
fi

if ! is_v2_at "$PORT"; then
  echo "端口 $PORT 上的程序无法确认属于本试用系统；为安全起见未结束任何程序。"
  echo "请联系管理员处理。"
  exit 1
fi

echo "正在停止试用服务（端口 $PORT）…"
kill "$PID" 2>/dev/null
for ((i = 0; i < 8; i++)); do
  kill -0 "$PID" 2>/dev/null || break
  sleep 1
done
if kill -0 "$PID" 2>/dev/null; then
  kill -9 "$PID" 2>/dev/null
fi
rm -f "$PID_FILE"
echo "试用服务已停止，现在可以重新开始试用。"
exit 0
