#!/bin/bash
# ================================================================
#  后端服务守护启动脚本（由 launchd 调用，勿手动运行）
#  作用: 在正确的环境下启动 林清轩种草智能体 后端 (端口 5210)
#  端口已被健康占用 → 正常退出(exit 0)，launchd 不会重启，避免双实例
# ================================================================
export NO_PROXY="localhost,127.0.0.1" no_proxy="localhost,127.0.0.1"
unset HTTP_PROXY http_proxy HTTPS_PROXY https_proxy ALL_PROXY all_proxy 2>/dev/null
export PATH="/Users/lily/.workbuddy/binaries/node/versions/22.22.2/bin:$PATH"

PROJ_DIR="/Users/lily/WorkBuddy/2026-08-12-11-29-21/LinQingXuan-Agent"
PYTHON_BIN="/Users/lily/.workbuddy/binaries/python/envs/default/bin/python"
BACKEND_PORT=5210

# 端口已被占用 → 视为已有实例在跑，正常退出
if /usr/bin/python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', $BACKEND_PORT)); s.close()" 2>/dev/null; then
  echo "[run_backend] 端口 ${BACKEND_PORT} 已有服务监听，正常退出（避免双实例）"
  exit 0
fi

cd "$PROJ_DIR" || exit 1
echo "[run_backend] $(date '+%F %T') 启动后端服务..."
exec "$PYTHON_BIN" backend/app.py
