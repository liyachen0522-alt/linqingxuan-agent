#!/bin/bash
# ================================================================
#  林清轩 · 种草智能体 —— 生产守护部署安装脚本
#  用法: ./deploy/install.sh
#  作用:
#    1. 启动守护循环（崩溃自动拉起后端/Edge/Node）
#    2. 注册「登录项」实现开机自动拉起（受系统权限限制时跳过）
#    3. 验证三个服务端口
#  卸载: ./deploy/uninstall.sh
# ================================================================
PROJ_DIR="/Users/lily/WorkBuddy/2026-08-12-11-29-21/LinQingXuan-Agent"
LOG_DIR="$PROJ_DIR/logs"
mkdir -p "$LOG_DIR"
chmod +x "$PROJ_DIR"/deploy/*.sh

echo "=== 1. 启动守护循环 ==="
"$PROJ_DIR/deploy/start_guard.sh"

echo ""
echo "=== 2. 注册开机自启（登录项）==="
LOGIN_CMD="nohup $PROJ_DIR/deploy/guard.sh >/dev/null 2>&1 &"
osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"$PROJ_DIR/deploy/guard.sh\", hidden:false}" 2>&1 && echo "[OK] 已添加到登录项（重启后自动守护）" || echo "[提示] 登录项注册被系统权限拦截，重启后需手动运行一次: ./deploy/start_guard.sh"

echo ""
echo "=== 3. 状态总览 ==="
for port in 5210 9350 4000; do
  if /usr/bin/python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1',$port)); s.close()" 2>/dev/null; then
    echo "[OK] 端口 ${port} 在线"
  else
    echo "[!!] 端口 ${port} 未就绪（查看 $LOG_DIR/guard.log）"
  fi
done

echo ""
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")
echo "部署完成 ✅"
echo "  本机访问:  http://localhost:5210"
echo "  同事访问:  http://${IP}:5210"
echo "  守护日志:  $LOG_DIR/guard.log"
echo "  常用命令:  ./deploy/start_guard.sh  启动守护"
echo "             ./deploy/stop_guard.sh   停止守护"
