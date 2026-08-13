#!/bin/zsh
# ============================================================
# start_v2_uat.sh — V2 正式界面试用一键启动（核心逻辑）
#
# 面向不会使用终端的中文医学监查人员：所有输出为自然中文。
# - 只服务已构建的 frontend/dist，不在启动路径运行 npm 或构建；
# - 用 /uat-status.json 的版本标记确认服务确实是 V2 试用服务，
#   不能只用「端口能访问」判断；与旧版 FastAPI 服务明确区分；
# - 从不复用或结束无法确认归属的进程（只管理本启动器留下完整记录的进程）；
# - 供 scripts/start_v2_uat.command 双击入口与自动化测试调用。
#
# 测试可覆盖的运行参数（环境变量）：
#   V2_UAT_DIST_DIR          前端构建产物目录（默认 frontend/dist）
#   V2_UAT_STATE_DIR         运行状态目录（默认 output/v2_uat_runtime）
#   V2_UAT_PORT              起始端口（默认 4173）
#   V2_UAT_PORT_SCAN_COUNT   顺延尝试的端口数量（默认 7）
#   V2_UAT_NO_BROWSER=1      不自动打开浏览器
#   V2_UAT_HEALTH_TIMEOUT_SEC 健康检查等待秒数（默认 15）
# ============================================================
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

DIST_DIR="${V2_UAT_DIST_DIR:-$APP_DIR/frontend/dist}"
STATE_DIR="${V2_UAT_STATE_DIR:-$APP_DIR/output/v2_uat_runtime}"
BASE_PORT="${V2_UAT_PORT:-4173}"
NO_BROWSER="${V2_UAT_NO_BROWSER:-0}"
PORT_SCAN_COUNT="${V2_UAT_PORT_SCAN_COUNT:-7}"
HEALTH_TIMEOUT_SEC="${V2_UAT_HEALTH_TIMEOUT_SEC:-15}"
V2_SERVICE_ID="enrollment-review-v2"

PID_FILE="$STATE_DIR/server.pid"
LOG_FILE="$STATE_DIR/server.log"

# Finder 双击启动的 PATH 较精简，补上本机常用安装位置
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

is_number() { [[ "$1" =~ ^[0-9]+$ ]]; }

is_number "$BASE_PORT" || { echo "【启动失败】端口设置不正确，请联系管理员。" >&2; exit 1; }
is_number "$PORT_SCAN_COUNT" || { echo "【启动失败】端口数量设置不正确，请联系管理员。" >&2; exit 1; }
is_number "$HEALTH_TIMEOUT_SEC" || { echo "【启动失败】等待时间设置不正确，请联系管理员。" >&2; exit 1; }

fail() {
  echo "" >&2
  echo "【启动失败】$1" >&2
  echo "请记录上方提示并联系系统管理员；无需自行安装或修改任何程序。" >&2
  exit 1
}

# ---- 使用 macOS 自带 Python 提供预构建页面，参与者无需 Node 或 npm ----
PYTHON_BIN="/usr/bin/python3"
[ -x "$PYTHON_BIN" ] || fail "未找到系统自带的页面运行组件。请联系管理员处理。"
[ -f "$DIST_DIR/index.html" ] || fail "缺少界面试用程序文件（frontend/dist 尚未构建或已被移动）。请由管理员完成构建后再开始试用。"
[ -f "$DIST_DIR/uat-status.json" ] || fail "界面试用程序文件版本不完整（缺少试用品版本标记）。请由管理员重新构建后再开始试用。"

# ---- 版本标记健康检查：只有标记为 V2 的服务才算数 ----
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

listener_pid_on() {
  /usr/sbin/lsof -t -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -1
}

# ---- 已在运行（含上次启动遗留）则直接复用，不再启动第二个服务 ----
PORT=""
OLD_PID=""
OLD_PORT=""
if [ -f "$PID_FILE" ]; then
  OLD_PID="$(awk 'NR==1{print $1}' "$PID_FILE" 2>/dev/null)"
  OLD_PORT="$(awk 'NR==2{print $1}' "$PID_FILE" 2>/dev/null)"
  if is_number "$OLD_PID" && is_number "$OLD_PORT" \
     && kill -0 "$OLD_PID" 2>/dev/null \
     && [ "$(listener_pid_on "$OLD_PORT")" = "$OLD_PID" ] \
     && is_v2_at "$OLD_PORT"; then
    PORT="$OLD_PORT"
    echo "入排审核工作台（界面试用）已经在运行：http://127.0.0.1:$PORT/"
    echo "不再重复启动，直接为您打开浏览器。"
    if [ "$NO_BROWSER" != "1" ]; then
      /usr/bin/open "http://127.0.0.1:$PORT/" 2>/dev/null
    fi
    exit 0
  fi
fi

# ---- 选择端口：非本启动器确认管理的占用一律顺延，不误用开发服务 ----
if [ -z "$PORT" ]; then
  for ((i = 0; i < PORT_SCAN_COUNT; i++)); do
    cand=$((BASE_PORT + i))
    if ! port_in_use "$cand"; then
      PORT="$cand"
      break
    fi
  done
  [ -n "$PORT" ] || fail "端口 ${BASE_PORT} 至 $((BASE_PORT + PORT_SCAN_COUNT - 1)) 均被其他程序占用。请关闭占用这些端口的程序后，再重新双击启动。"
fi

# ---- 启动本地只读页面服务（只服务已构建产物，不执行构建）----
mkdir -p "$STATE_DIR"
: > "$LOG_FILE"
cd "$DIST_DIR" || fail "无法进入界面试用程序目录。"
nohup "$PYTHON_BIN" -m http.server "$PORT" --bind 127.0.0.1 --directory "$DIST_DIR" >>"$LOG_FILE" 2>&1 &
SERVER_PID=$!
printf '%s\n%s\n' "$SERVER_PID" "$PORT" > "$PID_FILE"

echo "正在启动入排审核工作台（界面试用）…"
echo "访问地址：http://127.0.0.1:$PORT/"

# ---- 等待服务就绪（用版本标记确认是 V2，而非其他程序）----
WAITED=0
OK=0
while [ "$WAITED" -lt "$HEALTH_TIMEOUT_SEC" ]; do
  if is_v2_at "$PORT"; then
    OK=1
    break
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    break
  fi
  sleep 1
  WAITED=$((WAITED + 1))
done

if [ "$OK" != "1" ]; then
  # 只结束本次启动、且未通过健康检查的进程（归属明确）
  kill "$SERVER_PID" 2>/dev/null
  rm -f "$PID_FILE"
  fail "服务未能正常启动（等待 ${HEALTH_TIMEOUT_SEC} 秒仍未就绪），系统已停止本次启动。请联系管理员处理（日志：$LOG_FILE）。"
fi

PAGE_VERSION="$(/usr/bin/python3 -c 'import sys, json
try:
    print(json.load(open(sys.argv[1])).get("pageVersion", ""))
except Exception:
    pass' "$DIST_DIR/uat-status.json" 2>/dev/null)"
if [ -z "$PAGE_VERSION" ]; then
  PAGE_VERSION="（版本号读取失败，请联系管理员）"
fi

echo ""
echo "=========================================="
echo "  入排审核工作台（界面试用）启动完成"
echo "=========================================="
echo "  界面版本：$PAGE_VERSION"
echo "  访问地址：http://127.0.0.1:$PORT/"
echo ""
echo "  本窗口可以关闭，试用服务会继续运行。"
echo "  如需停止试用，请双击「停止试用」入口。"
echo "=========================================="

if [ "$NO_BROWSER" != "1" ]; then
  /usr/bin/open "http://127.0.0.1:$PORT/" 2>/dev/null \
    || echo "（未能自动打开浏览器，请手动输入上方地址。）"
fi
exit 0
