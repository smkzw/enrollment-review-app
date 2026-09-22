#!/bin/zsh
# WP08: muse-spark 恢复守望——上游可用后自动提交页判读并轮询到终态。
set -u
BASE="http://127.0.0.1:8902"
SID=$(cat /Users/smkzw/.omp/install-id 2>/dev/null | tr -d '[:space:]')
# 从应用 .env 读取 OPENCODE_API_KEY（密钥不写入本文件）。
KEY="$(grep '^OPENCODE_API_KEY=' .env | head -1 | cut -d= -f2- | tr -d '"' | tr -d ' ')"
if [ -z "$KEY" ]; then echo "[watch] .env 无 OPENCODE_API_KEY，退出"; exit 1; fi
SUB="e851520b052440abb8c6bdb01b7e6cab"
cd "/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile"
SUB="e851520b052440abb8c6bdb01b7e6cab"
EPI="6dbf65262bc54f959aaa0a07c783ba52"

recovered=0
for i in $(seq 1 4032); do  # 4032×300s = 14天长周期守望
  RESP=$(curl -s --max-time 60 -X POST \
    -H "Authorization: Bearer $KEY" -H "x-opencode-session: $SID" \
    -H "Content-Type: application/json" \
    https://opencode.ai/zen/go/v1/chat/completions \
    -d '{"model": "muse-spark-1.3-contributor", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 16}')
  if echo "$RESP" | grep -q '"finish_reason"'; then
    echo "[watch] muse-spark recovered at $(date '+%H:%M:%S') (probe $i)"
    recovered=1
    break
  fi
  echo "[watch] probe $i: still down $(date '+%H:%M:%S')"
  sleep 300
done

if [ "$recovered" != "1" ]; then
  echo "[watch] muse-spark 未在6小时内恢复，退出（不提交页判读）"
  exit 1
fi

JOB=$(curl -s -X POST "$BASE/api/v2/subjects/$SUB/review-episodes/$EPI/page-review-jobs" \
  -H "Content-Type: application/json" -d '{}' | python3 -c "import json,sys; print(json.load(sys.stdin).get('job_id',''))")
echo "[watch] page review job: $JOB"
[ -z "$JOB" ] && exit 1

for i in $(seq 1 90); do
  sleep 45
  STATE=$(.venv/bin/python - "$JOB" <<'PYEOF' 2>/dev/null
import os, sys
os.environ.setdefault('ENROLLMENT_ENV_FILE', os.path.abspath('.env'))
from app.config import load_enrollment_env_file
load_enrollment_env_file()
from app.services.evidence_app_bootstrap import resolve_data_paths, upgrade_or_fail
_, e, sf = upgrade_or_fail(resolve_data_paths())
with sf() as s:
    from sqlalchemy import text
    print(s.execute(text("SELECT state FROM jobs WHERE job_id=:j"), {"j": sys.argv[1]}).scalar())
PYEOF
)
  echo "[watch] poll $i: $STATE"
  case "$STATE" in completed|failed_final|cancelled) break;; esac
done

if [ "$STATE" != "completed" ]; then
  echo "[watch] 页判读未完成（$STATE），不进行事实重整。"
  exit 1
fi

# 页判读完成后：提交事实重整对齐新覆盖（新模型组合的最后一次闭环）
NORM=$(curl -s -X POST "$BASE/api/v2/subjects/$SUB/review-episodes/$EPI/fact-normalization-jobs" \
  -H "Content-Type: application/json" \
  -d '{"idempotency_intent": "wp08-muse-spark-follow-norm"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('job_id',''))")
echo "[watch] normalization job: $NORM"
[ -z "$NORM" ] && exit 1
for i in $(seq 1 90); do
  sleep 45
  NSTATE=$(.venv/bin/python - "$NORM" <<'PYEOF2' 2>/dev/null
import os, sys
os.environ.setdefault('ENROLLMENT_ENV_FILE', os.path.abspath('.env'))
from app.config import load_enrollment_env_file
load_enrollment_env_file()
from app.services.evidence_app_bootstrap import resolve_data_paths, upgrade_or_fail
_, e, sf = upgrade_or_fail(resolve_data_paths())
with sf() as s:
    from sqlalchemy import text
    print(s.execute(text("SELECT state FROM jobs WHERE job_id=:j"), {"j": sys.argv[1]}).scalar())
PYEOF2
)
  echo "[watch] norm poll $i: $NSTATE"
  case "$NSTATE" in completed|failed_final|cancelled) break;; esac
done
echo "[watch] done: page_review=$STATE normalization=$NSTATE"
