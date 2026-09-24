#!/bin/zsh
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/../app/main.py" ]; then
  APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  APP_DIR="${ENROLLMENT_REVIEW_APP_DIR:-/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app}"
fi
# Finder 双击启动时 PATH 很精简；MTPLX/oMLX 常安装在用户本地目录。
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Explicit env-file contract for worktree / dedicated processes. Process exports
# still win; config.py loads this path via setdefault at import time.
if [ -z "${ENROLLMENT_ENV_FILE:-}" ] && [ -f "$APP_DIR/.env" ]; then
  export ENROLLMENT_ENV_FILE="$APP_DIR/.env"
fi
if [[ "$APP_DIR" == */.worktrees/* ]] && [ -z "${ENROLLMENT_ENV_FILE:-}" ]; then
  echo "【启动失败】worktree 必须通过 ENROLLMENT_ENV_FILE 显式指定环境文件。"
  exit 1
fi

dotenv_value() {
  local env_file="${ENROLLMENT_ENV_FILE:-$APP_DIR/.env}"
  [ -f "$env_file" ] || return 0
  /usr/bin/python3 - "$env_file" "$1" <<'PY'
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

base_url() {
  local value="${1%/}"
  if [[ "$value" == */v1 ]]; then
    value="${value%/v1}"
  fi
  echo "$value"
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

OMLX_CONFIG="$HOME/Library/Application Support/oMLX/config.json"
OMLX_PORT="$(/usr/bin/python3 - "$OMLX_CONFIG" <<'PY' 2>/dev/null || true
import json
import sys
from pathlib import Path

try:
    port = int(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["port"])
    if 1 <= port <= 65535:
        print(port)
except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
    pass
PY
)"
OMLX_CONFIGURED_URL="${OMLX_BASE_URL:-}"
if [ -z "$OMLX_CONFIGURED_URL" ]; then
  OMLX_CONFIGURED_URL="$(dotenv_value OMLX_BASE_URL)"
fi
OMLX_URL="$(base_url "${OMLX_CONFIGURED_URL:-http://127.0.0.1:${OMLX_PORT:-8000}}")"

MTPLX_CONFIGURED_URL="${MTPLX_BASE_URL:-}"
if [ -z "$MTPLX_CONFIGURED_URL" ]; then
  MTPLX_CONFIGURED_URL="$(dotenv_value MTPLX_BASE_URL)"
fi
MTPLX_CONFIGURED_PORT="${MTPLX_PORT:-}"
if [ -z "$MTPLX_CONFIGURED_PORT" ]; then
  MTPLX_CONFIGURED_PORT="$(dotenv_value MTPLX_PORT)"
fi
if [ -z "$MTPLX_CONFIGURED_URL" ]; then
  OMLX_EFFECTIVE_PORT="$(url_port "$OMLX_URL")"
  OMLX_EFFECTIVE_PORT="${OMLX_EFFECTIVE_PORT:-8000}"
  MTPLX_DEFAULT_PORT=8000
  if [ "$OMLX_EFFECTIVE_PORT" = "$MTPLX_DEFAULT_PORT" ]; then
    MTPLX_DEFAULT_PORT=8001
  fi
  MTPLX_URL="http://127.0.0.1:$MTPLX_DEFAULT_PORT"
else
  MTPLX_URL="$(base_url "$MTPLX_CONFIGURED_URL")"
fi
MTPLX_PORT="${MTPLX_CONFIGURED_PORT:-$(url_port "$MTPLX_URL")}"
MTPLX_PORT="${MTPLX_PORT:-8000}"
MTPLX_MODEL="${MTPLX_MODEL:-$(dotenv_value MTPLX_MODEL)}"
MTPLX_MODEL="${MTPLX_MODEL:-mtplx-flash-next-optimized-speed}"
MTPLX_REASONING_EFFORT="${MTPLX_REASONING_EFFORT:-$(dotenv_value MTPLX_REASONING_EFFORT)}"
MTPLX_REASONING_EFFORT="${MTPLX_REASONING_EFFORT:-medium}"

DECONSTRUCT_ROUTE_MODE="${DECONSTRUCT_ROUTE_MODE:-$(dotenv_value DECONSTRUCT_ROUTE_MODE)}"
DECONSTRUCT_ROUTE_MODE="$(printf '%s' "${DECONSTRUCT_ROUTE_MODE:-pinned}" | tr '[:upper:]' '[:lower:]')"
DECONSTRUCT_BACKEND="${DECONSTRUCT_BACKEND:-$(dotenv_value DECONSTRUCT_BACKEND)}"
DECONSTRUCT_BACKEND="$(printf '%s' "${DECONSTRUCT_BACKEND:-cms-router}" | tr '[:upper:]' '[:lower:]')"
DECONSTRUCT_MODEL="${DECONSTRUCT_MODEL:-$(dotenv_value DECONSTRUCT_MODEL)}"
DECONSTRUCT_MODEL="${DECONSTRUCT_MODEL:-glm-5.3-flash}"
DECONSTRUCT_REASONING_EFFORT="${DECONSTRUCT_REASONING_EFFORT:-$(dotenv_value DECONSTRUCT_REASONING_EFFORT)}"
DECONSTRUCT_REASONING_EFFORT="$(printf '%s' "${DECONSTRUCT_REASONING_EFFORT:-high}" | tr '[:upper:]' '[:lower:]')"
DECONSTRUCT_GLM_PROVIDER="${DECONSTRUCT_GLM_PROVIDER:-$(dotenv_value DECONSTRUCT_GLM_PROVIDER)}"
DECONSTRUCT_GLM_PROVIDER="$(printf '%s' "${DECONSTRUCT_GLM_PROVIDER:-cms-router}" | tr '[:upper:]' '[:lower:]')"
DECONSTRUCT_GLM_MODEL="${DECONSTRUCT_GLM_MODEL:-$(dotenv_value DECONSTRUCT_GLM_MODEL)}"
DECONSTRUCT_GLM_MODEL="${DECONSTRUCT_GLM_MODEL:-glm-5.3-flash}"
DECONSTRUCT_GLM_REASONING_EFFORT="${DECONSTRUCT_GLM_REASONING_EFFORT:-$(dotenv_value DECONSTRUCT_GLM_REASONING_EFFORT)}"
DECONSTRUCT_GLM_REASONING_EFFORT="$(printf '%s' "${DECONSTRUCT_GLM_REASONING_EFFORT:-high}" | tr '[:upper:]' '[:lower:]')"
DECONSTRUCT_FALLBACK_DEEPSEEK_MODEL="${DECONSTRUCT_FALLBACK_DEEPSEEK_MODEL:-$(dotenv_value DECONSTRUCT_FALLBACK_DEEPSEEK_MODEL)}"
DECONSTRUCT_FALLBACK_DEEPSEEK_MODEL="${DECONSTRUCT_FALLBACK_DEEPSEEK_MODEL:-deepseek-latest-cloud}"
DECONSTRUCT_FALLBACK_DEEPSEEK_REASONING_EFFORT="${DECONSTRUCT_FALLBACK_DEEPSEEK_REASONING_EFFORT:-$(dotenv_value DECONSTRUCT_FALLBACK_DEEPSEEK_REASONING_EFFORT)}"
DECONSTRUCT_FALLBACK_DEEPSEEK_REASONING_EFFORT="$(printf '%s' "${DECONSTRUCT_FALLBACK_DEEPSEEK_REASONING_EFFORT:-high}" | tr '[:upper:]' '[:lower:]')"

# Graded complex work prefers GLM first. Do not auto-start MTPLX unless the
# operator pins MTPLX, or explicitly requests a local MTPLX warm-up.
SHOULD_AUTOSTART_MTPLX=0
if [ "${ENROLLMENT_START_MTPLX:-0}" = "1" ]; then
  SHOULD_AUTOSTART_MTPLX=1
elif [ "$DECONSTRUCT_ROUTE_MODE" = "pinned" ] && [[ "$DECONSTRUCT_BACKEND" == mtplx || "$DECONSTRUCT_BACKEND" == mtplx-api ]]; then
  SHOULD_AUTOSTART_MTPLX=1
fi


if [ "$OMLX_URL" = "$MTPLX_URL" ]; then
  echo "【启动失败】oMLX OCR服务与 MTPLX 语义服务指向同一地址：$OMLX_URL"
  echo "请为两个本地服务配置不同端口，系统不会把一个服务同时当作 OCR 和语义服务。"
  exit 1
fi

LOG_DIR="$APP_DIR/output/runtime_logs"
STATE_DIR="$APP_DIR/output/runtime_state"
PORT_FILE="$STATE_DIR/port"
APP_LOG="$LOG_DIR/enrollment-review-uvicorn.log"
OMLX_LOG="$LOG_DIR/omlx-start.log"
MTPLX_LOG="$LOG_DIR/mtplx-start.log"
LAUNCH_LOG="$LOG_DIR/enrollment-review-launch.log"
MTPLX_PID_FILE="$STATE_DIR/mtplx.pid"
MODEL_RUNTIME_ENV_FILE="$STATE_DIR/model-services.env"
LABEL="com.smkzw.enrollment-review"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SERVICE_SCRIPT="$APP_DIR/scripts/run_enrollment_review_service.sh"
TERMINAL_SERVICE_SCRIPT="$APP_DIR/scripts/run_enrollment_review_terminal.command"
MTPLX_SERVICE_SCRIPT="$APP_DIR/scripts/run_mtplx_service.sh"

mkdir -p "$LOG_DIR" "$STATE_DIR"
cd "$APP_DIR" || exit 1

is_number() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

model_list_matches() {
  local body="$1"
  local mode="$2"
  local expected="$3"
  /usr/bin/python3 -c '
import json
import sys

try:
    payload = json.load(sys.stdin)
    models = payload.get("data", [])
    if not isinstance(models, list) or not models:
        raise ValueError
    expected = sys.argv[2]
    mode = sys.argv[1]
    if mode == "owner":
        ok = any(
            str(item.get("owned_by", "")).strip().lower() == expected.lower()
            for item in models
            if isinstance(item, dict)
        )
    else:
        ok = any(
            str(item.get("id", "")) == expected
            for item in models
            if isinstance(item, dict)
        )
    raise SystemExit(0 if ok else 1)
except (ValueError, TypeError, AttributeError, json.JSONDecodeError, KeyError):
    raise SystemExit(1)
' "$mode" "$expected" <<< "$body"
}

is_omlx_up() {
  local body
  body="$(/usr/bin/curl --noproxy '*' -fsS --connect-timeout 2 --max-time 4 "$(base_url "$1")/v1/models" 2>/dev/null)" || return 1
  model_list_matches "$body" owner omlx
}

is_mtplx_up() {
  local body
  body="$(/usr/bin/curl --noproxy '*' -fsS --connect-timeout 2 --max-time 4 "$(base_url "$1")/v1/models" 2>/dev/null)" || return 1
  model_list_matches "$body" id "$MTPLX_MODEL"
}

is_enrollment_app() {
  local port="$1"
  local body
  body="$(/usr/bin/curl --noproxy '*' -fsS --connect-timeout 2 --max-time 4 "http://127.0.0.1:$port/api/health" 2>/dev/null)" || return 1
  [[ "$body" == *'"service":"enrollment-review-app"'* ]]
}

port_is_free() {
  ! /usr/sbin/lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

select_app_port() {
  local requested="${PORT:-}"
  local stored=""
  local candidate

  if [ -n "$requested" ]; then
    if is_enrollment_app "$requested" || port_is_free "$requested"; then
      echo "$requested"
      return 0
    fi
    echo "指定端口 $requested 已被其他程序占用。" >&2
    return 1
  fi

  if [ -f "$PORT_FILE" ]; then
    stored="$(tr -cd '0-9' < "$PORT_FILE")"
    if [ -n "$stored" ] && { is_enrollment_app "$stored" || port_is_free "$stored"; }; then
      echo "$stored"
      return 0
    fi
  fi

  for candidate in 8901 8902 8903 8904 8905 8906 8907 8908 8909 8910; do
    if is_enrollment_app "$candidate" || port_is_free "$candidate"; then
      echo "$candidate"
      return 0
    fi
  done


  echo "8901-8910 端口均已被占用，无法启动入排审核系统。" >&2
  return 1
}

APP_PORT="$(select_app_port)" || exit 1
PORT="$APP_PORT"
export PORT
printf '%s\n' "$APP_PORT" > "$PORT_FILE"
APP_URL="http://127.0.0.1:$APP_PORT"

wait_for_omlx() {
  local seconds="$1"
  local i=0
  local printed=0
  while [ "$i" -lt "$seconds" ]; do
    if is_omlx_up "$OMLX_URL"; then
      if [ "$printed" -eq 1 ]; then
        echo ""
      fi
      return 0
    fi
    sleep 1
    i=$((i + 1))
    if [ $((i % 5)) -eq 0 ]; then
      printf "."
      printed=1
    fi
  done
  if [ "$printed" -eq 1 ]; then
    echo ""
  fi
  return 1
}

wait_for_mtplx() {
  local seconds="$1"
  local i=0
  local printed=0
  while [ "$i" -lt "$seconds" ]; do
    if is_mtplx_up "$MTPLX_URL"; then
      if [ "$printed" -eq 1 ]; then
        echo ""
      fi
      return 0
    fi
    if [ -f "$MTPLX_PID_FILE" ]; then
      local pid
      pid="$(tr -cd '0-9' < "$MTPLX_PID_FILE")"
      if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
    fi
    sleep 1
    i=$((i + 1))
    if [ $((i % 10)) -eq 0 ]; then
      printf "."
      printed=1
    fi
  done
  if [ "$printed" -eq 1 ]; then
    echo ""
  fi
  return 1
}

start_mtplx_service() {
  if ! command -v mtplx >/dev/null 2>&1; then
    echo "【启动失败】未找到 MTPLX 本地服务命令；无法启动语义审核服务。"
    echo "请联系管理员安装并配置 MTPLX，不要改用 oMLX 代替语义服务。"
    return 1
  fi
  if [ ! -f "$MTPLX_SERVICE_SCRIPT" ]; then
    echo "【启动失败】缺少 MTPLX 启动脚本：$MTPLX_SERVICE_SCRIPT"
    echo "请联系管理员修复安装文件。"
    return 1
  fi
  if ! is_number "$MTPLX_PORT" || [ "$MTPLX_PORT" -lt 1 ] || [ "$MTPLX_PORT" -gt 65535 ]; then
    echo "【启动失败】MTPLX 端口设置不正确：$MTPLX_PORT"
    echo "请联系管理员核对 MTPLX_PORT 或 MTPLX_BASE_URL。"
    return 1
  fi
  if ! port_is_free "$MTPLX_PORT"; then
    echo "【启动失败】MTPLX 端口 $MTPLX_PORT 已被其他程序占用，且未发现目标模型 $MTPLX_MODEL。"
    echo "请关闭占用程序或修改 MTPLX_BASE_URL 后重新双击启动。"
    return 1
  fi

  rm -f "$MTPLX_PID_FILE"
  echo "MTPLX 未就绪，正在启动本地语义服务（模型：$MTPLX_MODEL，推理强度：$MTPLX_REASONING_EFFORT）..."
  MTPLX_BASE_URL="$MTPLX_URL" \
    MTPLX_PORT="$MTPLX_PORT" \
    MTPLX_MODEL="$MTPLX_MODEL" \
    MTPLX_REASONING_EFFORT="$MTPLX_REASONING_EFFORT" \
    nohup /bin/zsh "$MTPLX_SERVICE_SCRIPT" >> "$MTPLX_LOG" 2>&1 &
  MTPLX_PID="$!"
  printf '%s\n' "$MTPLX_PID" > "$MTPLX_PID_FILE"
  return 0
}

stop_started_mtplx() {
  [ "${MTPLX_STARTED_BY_LAUNCHER:-0}" = "1" ] || return 0
  [ -f "$MTPLX_PID_FILE" ] || return 0
  local pid
  pid="$(tr -cd '0-9' < "$MTPLX_PID_FILE")"
  [ -n "$pid" ] || return 0
  local command_line
  command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  if [[ "$command_line" == *"run_mtplx_service.sh"* || "$command_line" == *"mtplx quickstart"* ]]; then
    kill "$pid" >/dev/null 2>&1 || true
  fi
  rm -f "$MTPLX_PID_FILE"
}

write_model_runtime_env() {
  umask 077
  {
    if [ -n "${ENROLLMENT_ENV_FILE:-}" ]; then
      echo "ENROLLMENT_ENV_FILE=$ENROLLMENT_ENV_FILE"
    fi
    echo "ENROLLMENT_SEMANTIC_ROUTE_PREFLIGHT=${ENROLLMENT_SEMANTIC_ROUTE_PREFLIGHT:-1}"
    echo "ENROLLMENT_SEMANTIC_ROUTE_PREFLIGHT_MODE=${ENROLLMENT_SEMANTIC_ROUTE_PREFLIGHT_MODE:-degrade}"
    echo "ENROLLMENT_SEMANTIC_ENDPOINT_PREFLIGHT=${ENROLLMENT_SEMANTIC_ENDPOINT_PREFLIGHT:-1}"
    echo "MTPLX_BASE_URL=$MTPLX_URL"
    echo "MTPLX_PORT=$MTPLX_PORT"
    echo "MTPLX_MODEL=$MTPLX_MODEL"
    echo "MTPLX_REASONING_EFFORT=$MTPLX_REASONING_EFFORT"
    echo "DECONSTRUCT_ROUTE_MODE=$DECONSTRUCT_ROUTE_MODE"
    echo "DECONSTRUCT_BACKEND=$DECONSTRUCT_BACKEND"
    echo "DECONSTRUCT_MODEL=$DECONSTRUCT_MODEL"
    echo "DECONSTRUCT_REASONING_EFFORT=$DECONSTRUCT_REASONING_EFFORT"
    echo "DECONSTRUCT_GLM_PROVIDER=$DECONSTRUCT_GLM_PROVIDER"
    echo "DECONSTRUCT_GLM_MODEL=$DECONSTRUCT_GLM_MODEL"
    echo "DECONSTRUCT_GLM_REASONING_EFFORT=$DECONSTRUCT_GLM_REASONING_EFFORT"
    echo "DECONSTRUCT_FALLBACK_DEEPSEEK_MODEL=$DECONSTRUCT_FALLBACK_DEEPSEEK_MODEL"
    echo "DECONSTRUCT_FALLBACK_DEEPSEEK_REASONING_EFFORT=$DECONSTRUCT_FALLBACK_DEEPSEEK_REASONING_EFFORT"
  } > "$MODEL_RUNTIME_ENV_FILE"
  chmod 600 "$MODEL_RUNTIME_ENV_FILE"
}

wait_for_app() {
  local seconds="$1"
  local i=0
  local printed=0
  while [ "$i" -lt "$seconds" ]; do
    if is_enrollment_app "$APP_PORT"; then
      if [ "$printed" -eq 1 ]; then
        echo ""
      fi
      return 0
    fi
    sleep 1
    i=$((i + 1))
    if [ $((i % 5)) -eq 0 ]; then
      printf "."
      printed=1
    fi
  done
  if [ "$printed" -eq 1 ]; then
    echo ""
  fi
  return 1
}

write_launch_agent() {
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>$SERVICE_SCRIPT</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$APP_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$APP_LOG</string>
    <key>StandardErrorPath</key>
    <string>$APP_LOG</string>
</dict>
</plist>
PLIST
  chmod 644 "$PLIST" >/dev/null 2>&1 || true
}

ensure_app_service() {
  write_launch_agent
  chmod +x "$SERVICE_SCRIPT" >/dev/null 2>&1 || true
  chmod +x "$TERMINAL_SERVICE_SCRIPT" >/dev/null 2>&1 || true

  {
    echo "----- $(date '+%Y-%m-%d %H:%M:%S') launcher start -----"
    echo "plist=$PLIST"
    echo "service_script=$SERVICE_SCRIPT"
    /usr/bin/plutil -lint "$PLIST"
    local lint_rc=$?
    echo "plutil_exit=$lint_rc"
    if [ "$lint_rc" -ne 0 ]; then
      return "$lint_rc"
    fi

    if /bin/launchctl print "gui/$(id -u)/$LABEL"; then
      echo "existing_service=found; bootout before restart"
      /bin/launchctl bootout "gui/$(id -u)" "$PLIST"
      echo "bootout_exit=$?"
    else
      echo "existing_service=not_found"
    fi

    /bin/launchctl bootstrap "gui/$(id -u)" "$PLIST"
    local bootstrap_rc=$?
    echo "bootstrap_exit=$bootstrap_rc"
    if [ "$bootstrap_rc" -ne 0 ]; then
      return "$bootstrap_rc"
    fi

    /bin/launchctl kickstart -k "gui/$(id -u)/$LABEL"
    local kickstart_rc=$?
    echo "kickstart_exit=$kickstart_rc"
    if [ "$kickstart_rc" -ne 0 ]; then
      return "$kickstart_rc"
    fi

    /bin/launchctl print "gui/$(id -u)/$LABEL" >/dev/null
    local print_rc=$?
    echo "service_registered_exit=$print_rc"
    return "$print_rc"
  } >> "$LAUNCH_LOG" 2>&1
}

start_terminal_service() {
  {
    echo "----- $(date '+%Y-%m-%d %H:%M:%S') terminal fallback -----"
    /bin/launchctl bootout "gui/$(id -u)" "$PLIST"
    echo "fallback_bootout_exit=$?"
  } >> "$LAUNCH_LOG" 2>&1 || true
  chmod +x "$TERMINAL_SERVICE_SCRIPT" >/dev/null 2>&1 || true
  /usr/bin/open -a Terminal "$TERMINAL_SERVICE_SCRIPT"
}

open_browser_window() {
  local chrome="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  if [ -x "$chrome" ]; then
    nohup "$chrome" --new-window --window-size=2200,1300 --window-position=0,0 "$APP_URL" >/dev/null 2>&1 &
    sleep 1
    /usr/bin/osascript <<OSA >/dev/null 2>&1 || true
tell application "Google Chrome"
  activate
  if (count of windows) > 0 then set bounds of front window to {0, 0, 2200, 1300}
end tell
OSA
  else
    /usr/bin/open "$APP_URL"
  fi
}

echo "=========================================="
echo "  临床试验入排审核系统"
echo "=========================================="
echo "工作目录: $APP_DIR"
echo "前端入口: $APP_URL"
echo "oMLX OCR服务: $OMLX_URL"
echo "MTPLX本地服务: $MTPLX_URL（模型：$MTPLX_MODEL / $MTPLX_REASONING_EFFORT）"
if [ "$DECONSTRUCT_ROUTE_MODE" = "graded" ]; then
  echo "方案语义路由: graded"
  echo "  复杂任务: $DECONSTRUCT_GLM_PROVIDER/$DECONSTRUCT_GLM_MODEL:$DECONSTRUCT_GLM_REASONING_EFFORT -> mtplx/$MTPLX_MODEL:$MTPLX_REASONING_EFFORT -> deepseek/$DECONSTRUCT_FALLBACK_DEEPSEEK_MODEL:$DECONSTRUCT_FALLBACK_DEEPSEEK_REASONING_EFFORT"
  echo "  短提示任务: mtplx/$MTPLX_MODEL:$MTPLX_REASONING_EFFORT -> deepseek/$DECONSTRUCT_FALLBACK_DEEPSEEK_MODEL:$DECONSTRUCT_FALLBACK_DEEPSEEK_REASONING_EFFORT"
  echo "  说明: 不自动启动 MTPLX；仅在短任务或完整尝试回退时需要本地 MTPLX。"
else
  echo "方案语义路由: pinned -> $DECONSTRUCT_BACKEND/$DECONSTRUCT_MODEL:$DECONSTRUCT_REASONING_EFFORT"
fi
echo ""

if ! is_omlx_up "$OMLX_URL"; then
  echo "oMLX 未就绪，正在启动 oMLX..."
  /usr/bin/open -a oMLX >/dev/null 2>&1 || true
  if ! wait_for_omlx 30; then
    if command -v omlx >/dev/null 2>&1; then
      echo "尝试使用 omlx start 启动后台服务..."
      nohup omlx start --timeout 60 >> "$OMLX_LOG" 2>&1 &
      wait_for_omlx 75 || true
    fi
  fi
fi

if ! is_omlx_up "$OMLX_URL"; then
  rm -f "$PORT_FILE"
  rm -f "$MODEL_RUNTIME_ENV_FILE"
  echo "【启动失败】oMLX OCR服务仍未就绪，未打开审核页面。"
  echo "请确认 oMLX 已安装并能提供 OpenAI 兼容接口；日志：$OMLX_LOG"
  echo "系统不会把 MTPLX 误用为 OCR 服务。"
  exit 1
fi
echo "oMLX OCR服务已就绪。"

MTPLX_STARTED_BY_LAUNCHER=0
if is_mtplx_up "$MTPLX_URL"; then
  echo "MTPLX 本地服务已在线（模型：$MTPLX_MODEL）；可作为短任务首选或复杂任务回退。"
elif [ "$SHOULD_AUTOSTART_MTPLX" = "1" ]; then
  if start_mtplx_service; then
    MTPLX_STARTED_BY_LAUNCHER=1
    if wait_for_mtplx 180; then
      echo "MTPLX 本地服务已就绪（按 pinned/显式请求启动）。"
    else
      stop_started_mtplx
      rm -f "$PORT_FILE"
      rm -f "$MODEL_RUNTIME_ENV_FILE"
      echo "【启动失败】MTPLX 本地服务在 180 秒内未就绪，未打开审核页面。"
      echo "目标模型：$MTPLX_MODEL；日志：$MTPLX_LOG"
      echo "请确认模型已下载且 MTPLX_BASE_URL/MTPLX_PORT 配置正确。"
      exit 1
    fi
  else
    rm -f "$PORT_FILE"
    rm -f "$MODEL_RUNTIME_ENV_FILE"
    echo "【启动失败】MTPLX 本地服务不可用，未打开审核页面。"
    echo "目标模型：$MTPLX_MODEL；请按上方提示处理后重新双击启动。"
    exit 1
  fi
else
  echo "跳过自动启动 MTPLX（graded 复杂任务首选 GLM）。短任务或回退前请按需启动本地 MTPLX，或设置 ENROLLMENT_START_MTPLX=1。"
fi

if ! write_model_runtime_env; then
  rm -f "$PORT_FILE" "$MODEL_RUNTIME_ENV_FILE"
  echo "【启动失败】无法保存本次模型路由配置，未打开审核页面。"
  echo "请确认运行状态目录可写后重新双击启动。"
  exit 1
fi

if ! is_enrollment_app "$APP_PORT"; then
  echo "入排审核服务未运行，正在打开服务窗口..."
  start_terminal_service
  if wait_for_app 45; then
    echo "入排审核服务已在服务窗口中启动。请保留该窗口。"
  else
    echo "服务窗口未在预期时间内响应，正在尝试后台常驻启动..."
    if ensure_app_service; then
      echo "后台常驻服务已提交，正在等待响应（最多30秒）..."
      if wait_for_app 30; then
        echo "入排审核服务已通过后台常驻启动。"
      else
        echo "入排审核服务启动超时，请查看日志: $APP_LOG"
        echo "启动诊断日志: $LAUNCH_LOG"
      fi
    else
      echo "后台常驻启动也未成功，请查看日志: $APP_LOG"
      echo "启动诊断日志: $LAUNCH_LOG"
    fi
  fi
else
  echo "入排审核服务已运行。"
fi

echo "正在打开浏览器..."
open_browser_window
echo "完成。若出现单独的服务窗口，请保留该窗口以维持服务运行。"
sleep 2
