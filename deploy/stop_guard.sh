#!/bin/bash
# ================================================================
#  停止守护循环（不影响已运行的服务）
#  用法: ./deploy/stop_guard.sh
# ================================================================
PROJ_DIR="/Users/lily/WorkBuddy/2026-08-12-11-29-21/LinQingXuan-Agent"
PID_FILE="$PROJ_DIR/logs/guard.pid"

if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null
    echo "[stop_guard] 守护循环已停止 (PID $PID)，服务保持运行"
  else
    echo "[stop_guard] 守护进程已不在运行"
  fi
  rm -f "$PID_FILE"
else
  echo "[stop_guard] 未找到守护进程记录"
fi
