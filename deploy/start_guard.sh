#!/bin/bash
# ================================================================
#  启动守护（幂等，可重复执行）
#  用法: ./deploy/start_guard.sh
# ================================================================
PROJ_DIR="/Users/lily/WorkBuddy/2026-08-12-11-29-21/LinQingXuan-Agent"
PID_FILE="$PROJ_DIR/logs/guard.pid"

# 已运行则跳过（kill -0 探测）
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "[start_guard] 守护已在运行 (PID $(cat "$PID_FILE"))"
else
  rm -f "$PID_FILE"
  nohup "$PROJ_DIR/deploy/guard.sh" >/dev/null 2>&1 &
  sleep 1
  echo "[start_guard] 守护已启动 (PID $(cat "$PID_FILE" 2>/dev/null))"
fi

# 等待服务就绪
echo "[start_guard] 等待服务就绪..."
for i in $(seq 1 20); do
  ok=1
  for port in 5210 9350 4000; do
    if ! /usr/bin/python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1',$port)); s.close()" 2>/dev/null; then
      ok=0; break
    fi
  done
  [ "$ok" = "1" ] && break
  sleep 2
done

echo "------------------------------------------"
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")
for port in 5210 9350 4000; do
  if /usr/bin/python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1',$port)); s.close()" 2>/dev/null; then
    echo "[OK] 端口 ${port} 在线"
  else
    echo "[!!] 端口 ${port} 未就绪（查看 logs/guard.log）"
  fi
done
echo "  本机访问:  http://localhost:5210"
echo "  同事访问:  http://${IP}:5210"
