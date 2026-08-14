#!/bin/bash
# ================================================================
#  Edge 无头实例守护启动脚本（由 launchd 调用，勿手动运行）
#  作用: 启动 Edge headless (端口 9350)，供 CDP 抓取（抖音/合作笔记/外溢进店）
#  端口已被健康占用 → 正常退出(exit 0)
# ================================================================
EDGE_BIN="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
EDGE_PORT=9350

if /usr/bin/python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', $EDGE_PORT)); s.close()" 2>/dev/null; then
  echo "[run_edge] 端口 ${EDGE_PORT} 已有服务监听，正常退出（避免双实例）"
  exit 0
fi

if [ ! -f "$EDGE_BIN" ]; then
  echo "[run_edge] 未找到 Edge: $EDGE_BIN"
  exit 1
fi

echo "[run_edge] $(date '+%F %T') 启动 Edge 无头实例..."
exec "$EDGE_BIN" --headless=new --remote-debugging-port=$EDGE_PORT '--remote-allow-origins=*' \
  --user-data-dir="$HOME/Library/Application Support/Microsoft Edge-headless" \
  --disable-blink-features=AutomationControlled --no-first-run about:blank
