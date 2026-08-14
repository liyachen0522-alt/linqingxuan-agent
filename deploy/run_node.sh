#!/bin/bash
# ================================================================
#  Node 数据服务守护启动脚本（由 launchd 调用，勿手动运行）
#  作用: 启动 feishu-douyin-tool Node 服务 (端口 4000)
#  注: 抖音互动数据已迁移到 CDP(Edge) 方案，此服务保留供其他功能使用
#  端口已被健康占用 → 正常退出(exit 0)
# ================================================================
export PATH="/Users/lily/.workbuddy/binaries/node/versions/22.22.2/bin:$PATH"
NODE_PORT=4000

if /usr/bin/python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', $NODE_PORT)); s.close()" 2>/dev/null; then
  echo "[run_node] 端口 ${NODE_PORT} 已有服务监听，正常退出（避免双实例）"
  exit 0
fi

NODE_DIR="/Users/lily/WorkBuddy/2026-08-12-11-29-21/feishu-douyin-tool/backend"
if [ ! -d "$NODE_DIR" ]; then
  echo "[run_node] 未找到 feishu-douyin-tool/backend"
  exit 1
fi

echo "[run_node] $(date '+%F %T') 启动 Node 数据服务..."
cd "$NODE_DIR" || exit 1
exec /Users/lily/.workbuddy/binaries/node/versions/22.22.2/bin/node ./bin/www
