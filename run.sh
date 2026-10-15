#!/bin/bash
# 启动本目录的 V2 工作台；随机空闲端口不占用共享服务。
set -eu
cd "$(dirname "$0")"
ENV_FILE="${ENROLLMENT_ENV_FILE:-$PWD/.env}"
if [ ! -f "$ENV_FILE" ]; then
  echo "缺少本工作台配置，请先按 .env.example 准备 .env。" >&2
  exit 1
fi
if [ ! -x .venv/bin/python ] || [ ! -f frontend/dist/product-build.json ]; then
  echo "运行环境或正式界面尚未准备好，请先安装依赖并构建正式界面。" >&2
  exit 1
fi
echo "正在打开入排审核工作台 0.2.0；关闭此窗口将结束本次服务。"
exec .venv/bin/python -m scripts.run_v2_desktop --env-file "$ENV_FILE" "$@"
