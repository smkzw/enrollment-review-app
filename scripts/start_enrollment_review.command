#!/bin/zsh
set -u

APP_DIR="/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app"
OMLX_URL="${OMLX_BASE_URL:-http://127.0.0.1:8000}"
LOG_DIR="$APP_DIR/output/runtime_logs"
STATE_DIR="$APP_DIR/output/runtime_state"
PORT_FILE="$STATE_DIR/port"
APP_LOG="$LOG_DIR/enrollment-review-uvicorn.log"
OMLX_LOG="$LOG_DIR/omlx-start.log"
LAUNCH_LOG="$LOG_DIR/enrollment-review-launch.log"
LABEL="com.smkzw.enrollment-review"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SERVICE_SCRIPT="$APP_DIR/scripts/run_enrollment_review_service.sh"
TERMINAL_SERVICE_SCRIPT="$APP_DIR/scripts/run_enrollment_review_terminal.command"

mkdir -p "$LOG_DIR" "$STATE_DIR"
cd "$APP_DIR" || exit 1

is_http_up() {
  /usr/bin/curl -fsS --connect-timeout 2 --max-time 4 "$1" >/dev/null 2>&1
}

is_enrollment_app() {
  local port="$1"
  local body
  body="$(/usr/bin/curl -fsS --connect-timeout 2 --max-time 4 "http://127.0.0.1:$port/api/health" 2>/dev/null)" || return 1
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

wait_for_url() {
  local url="$1"
  local seconds="$2"
  local i=0
  local printed=0
  while [ "$i" -lt "$seconds" ]; do
    if is_http_up "$url"; then
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
echo "oMLX: $OMLX_URL"
echo ""

if ! is_http_up "$OMLX_URL/v1/models"; then
  echo "oMLX 未就绪，正在启动 oMLX..."
  /usr/bin/open -a oMLX >/dev/null 2>&1 || true
  if ! wait_for_url "$OMLX_URL/v1/models" 30; then
    if command -v omlx >/dev/null 2>&1; then
      echo "尝试使用 omlx start 启动后台服务..."
      nohup omlx start --timeout 60 >> "$OMLX_LOG" 2>&1 &
      wait_for_url "$OMLX_URL/v1/models" 75 || true
    fi
  fi
fi

if is_http_up "$OMLX_URL/v1/models"; then
  echo "oMLX 已就绪。"
else
  echo "oMLX 仍未就绪；页面会打开，但 OCR/本地模型审核可能不可用。"
  echo "日志: $OMLX_LOG"
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
