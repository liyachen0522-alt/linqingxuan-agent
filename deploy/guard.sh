#!/bin/bash
# ================================================================
#  服务守护循环（核心：崩溃自动拉起）
#  启动方式: ./deploy/start_guard.sh
#  停止方式: ./deploy/stop_guard.sh
#
#  每 8 秒检查三个服务端口，任何服务挂掉立即自动拉起：
#     - 后端 (5210)  Edge 无头 (9350)  Node 数据 (4000)
#  不依赖 launchd/cron，纯进程级守护，任何环境都能跑。
# ================================================================
PROJ_DIR="/Users/lily/WorkBuddy/2026-08-12-11-29-21/LinQingXuan-Agent"
LOG_DIR="$PROJ_DIR/logs"
mkdir -p "$LOG_DIR"

echo "$$" > "$LOG_DIR/guard.pid"

log() { echo "[guard] $(date '+%F %T') $*" >> "$LOG_DIR/guard.log"; }

port_open() {
  /usr/bin/python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', $1)); s.close()" 2>/dev/null
}

ensure() {
  local port=$1 label=$2 script=$3
  if ! port_open "$port"; then
    # 有残留进程但端口不通（僵死）→ 强杀，再拉起
    local pids
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null)
    if [ -n "$pids" ]; then
      log "${label}($port) 端口无响应，强杀残留进程 $pids"
      kill -9 $pids 2>/dev/null
      sleep 1
    fi
    log "拉起 ${label} ($script)"
    nohup "$script" >> "$LOG_DIR/guard.log" 2>&1 &
  fi
}

log "守护循环启动 (PID $$)"
while true; do
  ensure 5210 "后端" "$PROJ_DIR/deploy/run_backend.sh"
  ensure 9350 "Edge" "$PROJ_DIR/deploy/run_edge.sh"
  ensure 4000 "Node" "$PROJ_DIR/deploy/run_node.sh"
  sleep 8
done
