#!/usr/bin/env bash
# ============================================================
# test_start_v2_uat.sh — V2 启动器行为验收（本地自测）
#   0) shell 语法检查
#   1) 首次启动（版本标记验证）
#   2) 重复启动（不新建服务）
#   3) 端口被其他服务占用（包括伪装成 V2 的服务）：顺延端口，且不复用或结束占用方
#   4) 缺少构建产物（报错退出且不启动服务）
# 通过 V2_UAT_PORT 覆盖端口、V2_UAT_NO_BROWSER=1 禁止自动打开浏览器；
# 只结束测试自己启动的进程，退出前全部清理。
# 用法：bash scripts/test_start_v2_uat.sh
# ============================================================
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCHER="$ROOT/scripts/start_v2_uat.sh"
BASE_PORT="${V2_UAT_TEST_BASE_PORT:-4230}"
SCAN=3

PASS=0
FAIL=0
DUMMY_PIDS=""
V2_PIDS=""
STATE_DIRS=""
DUMMY_DIR=""

log() { echo "[test] $*"; }
ok() { PASS=$((PASS + 1)); echo "  [通过] $*"; }
no() { FAIL=$((FAIL + 1)); echo "  [失败] $*"; }

cleanup() {
  for p in $V2_PIDS; do kill -0 "$p" 2>/dev/null && kill "$p" 2>/dev/null; done
  for p in $DUMMY_PIDS; do kill -0 "$p" 2>/dev/null && kill "$p" 2>/dev/null; done
  sleep 1
  for p in $V2_PIDS; do kill -0 "$p" 2>/dev/null && kill -9 "$p" 2>/dev/null; done
  for p in $DUMMY_PIDS; do kill -0 "$p" 2>/dev/null && kill -9 "$p" 2>/dev/null; done
  for d in $STATE_DIRS; do rm -rf "$d"; done
}
trap cleanup EXIT

port_in_use() { /usr/sbin/lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

# 空闲端口段查找
free_range() {
  local n="$1" p i allfree
  p=$BASE_PORT
  while :; do
    allfree=1
    for ((i = 0; i < n; i++)); do
      if port_in_use $((p + i)); then allfree=0; break; fi
    done
    [ "$allfree" = "1" ] && break
    p=$((p + 1))
  done
  echo "$p"
}

DIST_OVERRIDE=""
OPEN_PAGE_OVERRIDE=""
run_launcher() { # $1=port  $2=state_dir
  local out
  if [ -n "$DIST_OVERRIDE" ]; then
    out="$(V2_UAT_DIST_DIR="$DIST_OVERRIDE" V2_UAT_STATE_DIR="$2" V2_UAT_NO_BROWSER=1 \
           V2_UAT_OPEN_PAGE="$OPEN_PAGE_OVERRIDE" \
           V2_UAT_PORT="$1" V2_UAT_PORT_SCAN_COUNT="$SCAN" zsh "$LAUNCHER" 2>&1)"
  else
    out="$(V2_UAT_STATE_DIR="$2" V2_UAT_NO_BROWSER=1 \
           V2_UAT_OPEN_PAGE="$OPEN_PAGE_OVERRIDE" \
           V2_UAT_PORT="$1" V2_UAT_PORT_SCAN_COUNT="$SCAN" zsh "$LAUNCHER" 2>&1)"
  fi
  LAUNCH_EXIT=$?
  LAUNCH_OUT="$out"
}

start_dummy() { # $1=port —— 系统 python3 http.server，绝无 V2 标记
  [ -n "$DUMMY_DIR" ] || return 1
  /usr/bin/python3 -m http.server "$1" --bind 127.0.0.1 --directory "$DUMMY_DIR" >/dev/null 2>&1 &
  disown
  DUMMY_PIDS="$DUMMY_PIDS $!"
  local i=0
  while [ "$i" -lt 20 ] && ! port_in_use "$1"; do sleep 0.3; i=$((i + 1)); done
}

marker_of() {
  /usr/bin/curl -fsS --max-time 2 "http://127.0.0.1:$1/uat-status.json" 2>/dev/null \
    | /usr/bin/python3 -c 'import sys, json
try:
    print(json.load(sys.stdin).get("service", ""))
except Exception:
    pass' 2>/dev/null
}

listener_count() {
  /usr/sbin/lsof -t -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | wc -l | tr -d ' '
}

echo "=============================================="
echo " V2 启动器行为验收（端口覆盖 + 禁止自动打开浏览器）"
echo "=============================================="

# 0) 语法检查
log "0) shell 语法检查"
if zsh -n "$LAUNCHER" \
  && zsh -n "$ROOT/scripts/stop_v2_uat.sh" \
  && zsh -n "$ROOT/scripts/start_v2_uat.command" \
  && zsh -n "$ROOT/scripts/stop_v2_uat.command" \
  && bash -n "$0"; then
  ok "zsh -n / bash -n 全部通过"
else
  no "语法检查失败"; exit 1
fi

# 1) 首次启动
log "1) 首次启动"
S1="$(mktemp -d /tmp/v2uat_test.XXXXXX)"
STATE_DIRS="$STATE_DIRS $S1"
P1="$(free_range 3)"
run_launcher "$P1" "$S1"
if [ "$LAUNCH_EXIT" -eq 0 ] \
  && [ "$(echo "$LAUNCH_OUT" | grep -c '启动完成')" -ge 1 ] \
  && [ "$(marker_of "$P1")" = "enrollment-review-v2" ]; then
  V2_PIDS="$V2_PIDS $(awk 'NR==1{print $1}' "$S1/server.pid")"
  ok "首次启动成功：端口 ${P1}，版本标记验证通过"
else
  no "首次启动失败：exit=$LAUNCH_EXIT"
  echo "$LAUNCH_OUT" | sed 's/^/      | /'
fi

# 2) 重复启动
log "2) 重复启动"
if [ -f "$S1/server.pid" ]; then
  PID_BEFORE="$(awk 'NR==1{print $1}' "$S1/server.pid")"
  run_launcher "$P1" "$S1"
  PID_AFTER="$(awk 'NR==1{print $1}' "$S1/server.pid")"
  CNT="$(listener_count "$P1")"
  if [ "$LAUNCH_EXIT" -eq 0 ] \
    && [ "$(echo "$LAUNCH_OUT" | grep -c '已经在运行')" -ge 1 ] \
    && [ "$PID_BEFORE" = "$PID_AFTER" ] \
    && [ "$CNT" -eq 1 ]; then
    ok "重复启动未新建服务：PID 不变、监听数=1"
  else
    no "重复启动行为异常：exit=$LAUNCH_EXIT 监听数=$CNT"
    echo "$LAUNCH_OUT" | sed 's/^/      | /'
  fi
else
  no "行为2跳过：首次启动未留下 pid 文件"
fi

# 3a) 端口被其他服务占用 → 自动顺延到空闲端口，且不结束占用方
log "3a) 端口被其他服务占用（自动顺延端口）"
S3="$(mktemp -d /tmp/v2uat_test.XXXXXX)"
STATE_DIRS="$STATE_DIRS $S3"
DUMMY_DIR="$(mktemp -d /tmp/v2uat_dummy.XXXXXX)"
STATE_DIRS="$STATE_DIRS $DUMMY_DIR"
P3="$(free_range 3)"
start_dummy "$P3"
DUMMY_PID="$(echo "$DUMMY_PIDS" | awk '{print $NF}')"
run_launcher "$P3" "$S3"
if [ "$LAUNCH_EXIT" -eq 0 ] \
  && [ "$(echo "$LAUNCH_OUT" | grep -c '启动完成')" -ge 1 ] \
  && [ "$(marker_of "$((P3 + 1))")" = "enrollment-review-v2" ] \
  && kill -0 "$DUMMY_PID" 2>/dev/null; then
  V2_PIDS="$V2_PIDS $(awk 'NR==1{print $1}' "$S3/server.pid")"
  ok "占用端口 ${P3} 时自动顺延到 $((P3 + 1))，且未结束占用方进程"
else
  no "行为3a失败：exit=${LAUNCH_EXIT}（占用方存活=$([ -n "$DUMMY_PID" ] && kill -0 "$DUMMY_PID" 2>/dev/null && echo 是 || echo 否)）"
  echo "$LAUNCH_OUT" | sed 's/^/      | /'
fi

# 3c) 未被本启动器记录、但返回 V2 标记的服务也不得复用
log "3c) 未登记的同标记服务占用端口（不得误复用）"
S3C="$(mktemp -d /tmp/v2uat_test.XXXXXX)"
STATE_DIRS="$STATE_DIRS $S3C"
FAKE_V2_DIR="$(mktemp -d /tmp/v2uat_fake_v2.XXXXXX)"
STATE_DIRS="$STATE_DIRS $FAKE_V2_DIR"
printf '{"service":"enrollment-review-v2"}\n' > "$FAKE_V2_DIR/uat-status.json"
OLD_DUMMY_DIR="$DUMMY_DIR"
DUMMY_DIR="$FAKE_V2_DIR"
P3C="$(free_range 3)"
start_dummy "$P3C"
FAKE_V2_PID="$(echo "$DUMMY_PIDS" | awk '{print $NF}')"
DUMMY_DIR="$OLD_DUMMY_DIR"
run_launcher "$P3C" "$S3C"
if [ "$LAUNCH_EXIT" -eq 0 ] \
  && [ "$(marker_of "$((P3C + 1))")" = "enrollment-review-v2" ] \
  && [ -f "$S3C/server.pid" ] \
  && [ "$(awk 'NR==2{print $1}' "$S3C/server.pid")" = "$((P3C + 1))" ] \
  && kill -0 "$FAKE_V2_PID" 2>/dev/null; then
  V2_PIDS="$V2_PIDS $(awk 'NR==1{print $1}' "$S3C/server.pid")"
  ok "未登记的同标记服务未被复用，试用服务顺延到 $((P3C + 1))"
else
  no "行为3c失败：误复用或影响了未登记服务"
  echo "$LAUNCH_OUT" | sed 's/^/      | /'
fi

# 3b) 候选端口全部被其他服务占用 → 中文报错退出，不结束任何占用方
log "3b) 候选端口全部被其他服务占用"
S3B="$(mktemp -d /tmp/v2uat_test.XXXXXX)"
STATE_DIRS="$STATE_DIRS $S3B"
P3B="$(free_range 3)"
for i in 0 1 2; do
  start_dummy $((P3B + i))
done
run_launcher "$P3B" "$S3B"
ALIVE=1
for p in $DUMMY_PIDS; do kill -0 "$p" 2>/dev/null || ALIVE=0; done
if [ "$LAUNCH_EXIT" -ne 0 ] \
  && [ "$(echo "$LAUNCH_OUT" | grep -c '均被其他程序占用')" -ge 1 ] \
  && [ "$ALIVE" = "1" ]; then
  ok "候选端口全部占用时报错退出，未结束任何占用方进程"
else
  no "行为3b失败：exit=$LAUNCH_EXIT"
  echo "$LAUNCH_OUT" | sed 's/^/      | /'
fi

# 4a) 缺少构建产物（dist 不存在）
log "4a) 缺少构建产物"
S4="$(mktemp -d /tmp/v2uat_test.XXXXXX)"
STATE_DIRS="$STATE_DIRS $S4"
DIST_OVERRIDE="$S4/no-such-dist"
run_launcher "$P1" "$S4"
if [ "$LAUNCH_EXIT" -ne 0 ] \
  && [ "$(echo "$LAUNCH_OUT" | grep -c '缺少界面试用程序文件')" -ge 1 ] \
  && [ ! -f "$S4/server.pid" ]; then
  ok "缺少构建产物时报错退出，且未启动任何服务"
else
  no "行为4a失败：exit=$LAUNCH_EXIT"
  echo "$LAUNCH_OUT" | sed 's/^/      | /'
fi

# 4b) 构建产物存在但缺少版本标记（版本不完整）
log "4b) 缺少版本标记（版本不完整）"
S4B="$(mktemp -d /tmp/v2uat_test.XXXXXX)"
STATE_DIRS="$STATE_DIRS $S4B"
mkdir -p "$S4B/fake-dist"
printf '<!doctype html><html><body>fake</body></html>\n' > "$S4B/fake-dist/index.html"
DIST_OVERRIDE="$S4B/fake-dist"
run_launcher "$P1" "$S4B"
if [ "$LAUNCH_EXIT" -ne 0 ] \
  && [ "$(echo "$LAUNCH_OUT" | grep -c '版本不完整')" -ge 1 ] \
  && [ ! -f "$S4B/server.pid" ]; then
  ok "缺少版本标记时报错退出，且未启动任何服务"
else
  no "行为4b失败：exit=$LAUNCH_EXIT"
  echo "$LAUNCH_OUT" | sed 's/^/      | /'
fi
DIST_OVERRIDE=""

# 5) 重复停止：没有启动记录也应视为已停止，不制造失败提示
log "5) 重复停止（当前没有运行服务）"
S5="$(mktemp -d /tmp/v2uat_test.XXXXXX)"
STATE_DIRS="$STATE_DIRS $S5"
STOP_OUT="$(V2_UAT_STATE_DIR="$S5" zsh "$ROOT/scripts/stop_v2_uat.sh" 2>&1)"
STOP_EXIT=$?
if [ "$STOP_EXIT" -eq 0 ] \
  && [ "$(echo "$STOP_OUT" | grep -c '无需再次停止')" -ge 1 ]; then
  ok "重复停止按已停止处理，不要求用户排错"
else
  no "行为5失败：exit=$STOP_EXIT"
  echo "$STOP_OUT" | sed 's/^/      | /'
fi

# 6) 打开路径只允许 "/" 与 "/uat-recorder.html"：记录工作台首次启动
log "6) 记录工作台打开路径首次启动"
S6="$(mktemp -d /tmp/v2uat_test.XXXXXX)"
STATE_DIRS="$STATE_DIRS $S6"
S6D="$(mktemp -d /tmp/v2uat_dist.XXXXXX)"
STATE_DIRS="$STATE_DIRS $S6D"
printf '{"service":"enrollment-review-v2","pageVersion":"界面试用版 1.5.1"}\n' > "$S6D/uat-status.json"
printf '<!doctype html><html><body>fake</body></html>\n' > "$S6D/index.html"
printf '<!doctype html><html><body>recorder</body></html>\n' > "$S6D/uat-recorder.html"
P6="$(free_range 1)"
DIST_OVERRIDE="$S6D"
OPEN_PAGE_OVERRIDE="/uat-recorder.html"
run_launcher "$P6" "$S6"
if [ "$LAUNCH_EXIT" -eq 0 ] \
  && [ "$(echo "$LAUNCH_OUT" | grep -c '记录工作台启动完成')" -ge 1 ] \
  && [ "$(echo "$LAUNCH_OUT" | grep -c "http://127.0.0.1:$P6/uat-recorder.html")" -ge 1 ] \
  && [ "$(marker_of "$P6")" = "enrollment-review-v2" ]; then
  V2_PIDS="$V2_PIDS $(awk 'NR==1{print $1}' "$S6/server.pid")"
  ok "记录工作台路径启动成功：端口 ${P6}，地址指向 /uat-recorder.html"
else
  no "行为6失败：exit=$LAUNCH_EXIT"
  echo "$LAUNCH_OUT" | sed 's/^/      | /'
fi

# 7) 已在运行时用记录工作台路径复用，不新建服务
log "7) 记录工作台路径重复启动（复用服务）"
if [ -f "$S6/server.pid" ]; then
  PID_BEFORE="$(awk 'NR==1{print $1}' "$S6/server.pid")"
  run_launcher "$P6" "$S6"
  PID_AFTER="$(awk 'NR==1{print $1}' "$S6/server.pid")"
  CNT="$(listener_count "$P6")"
  if [ "$LAUNCH_EXIT" -eq 0 ] \
    && [ "$(echo "$LAUNCH_OUT" | grep -c '已经在运行')" -ge 1 ] \
    && [ "$(echo "$LAUNCH_OUT" | grep -c "http://127.0.0.1:$P6/uat-recorder.html")" -ge 1 ] \
    && [ "$PID_BEFORE" = "$PID_AFTER" ] \
    && [ "$CNT" -eq 1 ]; then
    ok "记录工作台路径复用已运行服务：PID 不变、监听数=1"
  else
    no "行为7失败：exit=$LAUNCH_EXIT 监听数=$CNT"
    echo "$LAUNCH_OUT" | sed 's/^/      | /'
  fi
else
  no "行为7跳过：行为6未留下 pid 文件"
fi
DIST_OVERRIDE=""
OPEN_PAGE_OVERRIDE=""

# 8) 非法打开路径：中文报错退出，不启动服务
log "8) 非法打开路径（只允许 / 与 /uat-recorder.html）"
S8="$(mktemp -d /tmp/v2uat_test.XXXXXX)"
STATE_DIRS="$STATE_DIRS $S8"
P8="$(free_range 1)"
OPEN_PAGE_OVERRIDE="/secret"
run_launcher "$P8" "$S8"
if [ "$LAUNCH_EXIT" -ne 0 ] \
  && [ "$(echo "$LAUNCH_OUT" | grep -c '打开页面不正确')" -ge 1 ] \
  && [ ! -f "$S8/server.pid" ] \
  && ! port_in_use "$P8"; then
  ok "非法路径被拒绝：中文报错且未启动任何服务"
else
  no "行为8失败：exit=$LAUNCH_EXIT"
  echo "$LAUNCH_OUT" | sed 's/^/      | /'
fi
OPEN_PAGE_OVERRIDE=""

# 9) 记录工作台文件缺失：中文报错退出，不启动服务
log "9) 记录工作台文件缺失"
S9="$(mktemp -d /tmp/v2uat_test.XXXXXX)"
STATE_DIRS="$STATE_DIRS $S9"
S9D="$(mktemp -d /tmp/v2uat_dist.XXXXXX)"
STATE_DIRS="$STATE_DIRS $S9D"
printf '{"service":"enrollment-review-v2"}\n' > "$S9D/uat-status.json"
printf '<!doctype html><html><body>fake</body></html>\n' > "$S9D/index.html"
P9="$(free_range 1)"
DIST_OVERRIDE="$S9D"
OPEN_PAGE_OVERRIDE="/uat-recorder.html"
run_launcher "$P9" "$S9"
if [ "$LAUNCH_EXIT" -ne 0 ] \
  && [ "$(echo "$LAUNCH_OUT" | grep -c '记录工作台程序文件')" -ge 1 ] \
  && [ ! -f "$S9/server.pid" ] \
  && ! port_in_use "$P9"; then
  ok "记录工作台文件缺失被拒绝：中文报错且未启动任何服务"
else
  no "行为9失败：exit=$LAUNCH_EXIT"
  echo "$LAUNCH_OUT" | sed 's/^/      | /'
fi
DIST_OVERRIDE=""
OPEN_PAGE_OVERRIDE=""

# 10) 显式首页路径 "/"：与默认行为一致
log "10) 显式首页路径"
S10="$(mktemp -d /tmp/v2uat_test.XXXXXX)"
STATE_DIRS="$STATE_DIRS $S10"
P10="$(free_range 1)"
DIST_OVERRIDE="$S6D"
OPEN_PAGE_OVERRIDE="/"
run_launcher "$P10" "$S10"
if [ "$LAUNCH_EXIT" -eq 0 ] \
  && [ "$(echo "$LAUNCH_OUT" | grep -c '入排审核工作台（界面试用）启动完成')" -ge 1 ] \
  && [ "$(echo "$LAUNCH_OUT" | grep -c "http://127.0.0.1:$P10/")" -ge 1 ] \
  && [ "$(marker_of "$P10")" = "enrollment-review-v2" ]; then
  V2_PIDS="$V2_PIDS $(awk 'NR==1{print $1}' "$S10/server.pid")"
  ok "显式首页路径启动成功：端口 ${P10}，地址指向 /"
else
  no "行为10失败：exit=$LAUNCH_EXIT"
  echo "$LAUNCH_OUT" | sed 's/^/      | /'
fi
DIST_OVERRIDE=""
OPEN_PAGE_OVERRIDE=""
echo ""
echo "=============================================="
echo " 结果：通过 $PASS 项，失败 $FAIL 项"
echo "=============================================="
[ "$FAIL" -eq 0 ]
