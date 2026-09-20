#!/bin/sh
# 本地模型服务直接启动与健康检查（oMLX 8001 / MTPLX 8002）。
#
# 设计边界（与 app/llm/mtplx_model_lifecycle.py 一致）：
# - MTPLX 产品属主模式（owned-serial/v1）要求 ENROLLMENT_MTPLX_MODELS_FILE 指向
#   显式清单，并由后端进程独占装卸（防止两个会话同时加载）。端口已被外部
#   实例占用时属主启动会按设计拒绝——本脚本只报告，不抢占、不杀外部服务。
# - oMLX 由 `omlx start` 托管启动；OCR 权威模型由共享门禁
#   ~/.codex/tools/omlx_workload_gate.py 决定（当前 GLM-OCR-bf16），调用方不得指定。
set -eu
W="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$W/artifacts/mtplx-dual-basic-20260916/owned-lifecycle-models-direct-cli.json"

port_open() { nc -z -w 1 127.0.0.1 "$1" >/dev/null 2>&1; }

echo "== oMLX (8001, OCR/通用) =="
if port_open 8001; then
  echo "  已在运行。模型清单："
  curl -s -m 5 http://127.0.0.1:8001/v1/models | python3 -c "
import json,sys
try:
    for m in json.load(sys.stdin).get('data', []): print('   -', m.get('id'))
except Exception: print('   （/v1/models 无响应）')"
else
  echo "  未运行，执行 omlx start …"
  omlx start --timeout 180
  echo "  已启动。"
fi

echo "== MTPLX (8002, 方案语义/页读) =="
if port_open 8002; then
  echo "  8002 已有服务监听（外部/共享实例）。产品属主模式不接管；"
  echo "  消费该端点时后端路由可显式指向它，勿重启/占用/停止。当前模型："
  curl -s -m 5 http://127.0.0.1:8002/v1/models | python3 -c "
import json,sys
try:
    for m in json.load(sys.stdin).get('data', []): print('   -', m.get('id'))
except Exception: print('   （/v1/models 无响应）')"
else
  echo "  8002 空闲。产品自有串行启动（装卸保护生效）需："
  echo "    export ENROLLMENT_MTPLX_MODELS_FILE=$MANIFEST"
  echo "    启动 uvicorn 后首次语义调用自动加载模型（Flash-Next 约 107GB，需数分钟）。"
  echo "  注意：DECONSTRUCT_REASONING_EFFORT 必须与清单 effort 一致（xhigh）。"
  [ -f "$MANIFEST" ] && echo "  清单存在：$MANIFEST" || echo "  !! 清单缺失：$MANIFEST"
fi

echo "== 方案解构路由（当前 shell 建议）=="
if port_open 8002; then
  echo "  共享实例可用时：DECONSTRUCT_BACKEND=<见任务记录>；属主清单方式仅在 8002 空闲时可行。"
else
  echo "  export ENROLLMENT_MTPLX_MODELS_FILE=$MANIFEST"
  echo "  export DECONSTRUCT_BACKEND=mtplx DECONSTRUCT_MODEL=Youssofal--Qwen3.8-Flash-Next-MTPLX-Optimized-Speed DECONSTRUCT_REASONING_EFFORT=xhigh"
  echo "  可选 ENROLLMENT_SEMANTIC_ROUTE_PREFLIGHT=0（跳过启动预检，让首次调用吸收首次装载耗时）"
fi
