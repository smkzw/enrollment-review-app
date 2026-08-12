#!/bin/bash
# 启动临床试验入排审核系统（生产模式）
set -e
cd "$(dirname "$0")"
echo "=========================================="
echo "  临床试验入排审核系统 v2.0"
echo "  Enrollment Review Application"
echo "=========================================="
echo ""
echo "启动服务: http://127.0.0.1:8900"
echo "API文档: http://127.0.0.1:8900/docs"
echo ""
echo "前置条件:"
echo "  - oMLX 运行中 (http://127.0.0.1:8000)"
echo "  - .env 文件已配置 (参考 .env.example)"
echo "  - 可选: DeepSeek API Key / 百度 OCR Key"
echo ""
echo "按 Ctrl+C 停止服务"
echo "=========================================="
echo ""
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8900
