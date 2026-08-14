#!/bin/bash
# ================================================================
#  卸载守护部署（不删除项目文件）
#  用法: ./deploy/uninstall.sh
#  卸载后如需手动启动: ./start.sh
# ================================================================
PROJ_DIR="/Users/lily/WorkBuddy/2026-08-12-11-29-21/LinQingXuan-Agent"

echo "=== 1. 停止守护循环 ==="
"$PROJ_DIR/deploy/stop_guard.sh"

echo "=== 2. 移除登录项（忽略错误）==="
osascript -e "tell application \"System Events\" to delete login item \"guard.sh\"" 2>/dev/null \
  && echo "[OK] 已移除登录项" || echo "[提示] 未找到登录项或权限受限"

echo "=== 完成！守护已卸载 ==="
echo "  手动启动:  cd LinQingXuan-Agent && ./start.sh"
