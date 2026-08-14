#!/bin/bash
# ================================================================
#  林清轩 · 种草智能体 - 一键启动脚本（内网共享版）
#  使用方法: ./start.sh
#  本机访问: http://localhost:5210
#  同事访问: http://<本机局域网IP>:5210  （需在同一网络）
#  按 Ctrl+C 停止服务
#
#  依赖服务（自动拉起）:
#    - Edge 无头实例 (9350)  合作笔记/外溢进店抓取
#    - Node 数据服务 (4000)  抖音视频互动数据
#   Cookie 配置（Spider_XHS/.env）:
#    - COOKIES      小红书 PC 端 Cookie（笔记互动查询需要）
#    - DY_COOKIES   抖音 Cookie（抖音互动查询需要，可选）
# ================================================================

cd "$(dirname "$0")"

# ---------- 0.5 守护部署检测（推荐模式） ----------
# 若 deploy/guard.sh 守护循环已在运行，直接提示访问，不重复启动
PID_FILE="logs/guard.pid"
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")
  echo "=================================================="
  echo "  守护模式已运行（服务由 ./deploy/guard.sh 保护，崩溃自动拉起）"
  echo "  本机访问:  http://localhost:5210"
  echo "  同事访问:  http://${IP}:5210"
  echo "  停止守护:  ./deploy/stop_guard.sh"
  echo "=================================================="
  exit 0
fi

# 关键：屏蔽代理环境变量，防止 urllib 请求 127.0.0.1 时被代理劫持
export NO_PROXY="localhost,127.0.0.1" no_proxy="localhost,127.0.0.1"
unset HTTP_PROXY http_proxy HTTPS_PROXY https_proxy ALL_PROXY all_proxy 2>/dev/null

export PATH="/Users/lily/.workbuddy/binaries/node/versions/22.22.2/bin:$PATH"
PYTHON_BIN="/Users/lily/.workbuddy/binaries/python/envs/default/bin/python"
EDGE_BIN="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
EDGE_PORT=9350
NODE_PORT=4000
BACKEND_PORT=5210

echo "=================================================="
echo "  林清轩 · 种草智能体 v1.0（内网共享版）"
echo "=================================================="

# ---------- 0. 加载 Cookie 到环境变量（供笔记互动查询使用） ----------
# 兼容两种位置：项目内 Spider_XHS/.env 或 工作区根 Spider_XHS/.env
ENV_FILE="Spider_XHS/.env"
if [ ! -f "$ENV_FILE" ]; then
  ENV_FILE="../Spider_XHS/.env"
fi
if [ -f "$ENV_FILE" ]; then
  # 读取 COOKIES / DY_COOKIES（去掉首尾引号）
  XHS_CK=$(grep -E '^COOKIES=' "$ENV_FILE" | head -1 | cut -d= -f2- | sed -e "s/^'//" -e "s/'$//" -e 's/^"//' -e 's/"$//')
  DY_CK=$(grep -E '^DY_COOKIES=' "$ENV_FILE" | head -1 | cut -d= -f2- | sed -e "s/^'//" -e "s/'$//" -e 's/^"//' -e 's/"$//')
  [ -n "$XHS_CK" ] && export XHS_COOKIES="$XHS_CK" && echo "[OK] 已加载小红书 Cookie（${#XHS_CK} 字符）"
  [ -n "$DY_CK" ] && export DY_COOKIES="$DY_CK" && echo "[OK] 已加载抖音 Cookie（${#DY_CK} 字符）"
  [ -z "$DY_CK" ] && echo "[提示] 未配置抖音 Cookie（DY_COOKIES），抖音互动查询将不可用"
else
  echo "[警告] 未找到 $ENV_FILE，笔记互动查询不可用"
fi

# ---------- 1. Edge 无头实例（合作笔记/外溢进店抓取依赖） ----------
if curl -s -m 2 "http://127.0.0.1:${EDGE_PORT}/json/version" >/dev/null 2>&1; then
  echo "[OK] Edge 无头实例已在运行 (端口 ${EDGE_PORT})"
else
  echo "[启动] 正在拉起 Edge 无头实例..."
  if [ ! -f "$EDGE_BIN" ]; then
    echo "[警告] 未找到 Edge: $EDGE_BIN"
    echo "       合作笔记/外溢进店功能将不可用，其余功能正常"
  else
    "$EDGE_BIN" --headless=new --remote-debugging-port=$EDGE_PORT '--remote-allow-origins=*' \
      --user-data-dir="$HOME/Library/Application Support/Microsoft Edge-headless" \
      --disable-blink-features=AutomationControlled --no-first-run about:blank \
      >/tmp/pgy_edge_headless.log 2>&1 &
    sleep 6
    if curl -s -m 2 "http://127.0.0.1:${EDGE_PORT}/json/version" >/dev/null 2>&1; then
      echo "[OK] Edge 无头实例启动成功"
    else
      echo "[警告] Edge 无头实例启动失败，合作笔记功能不可用"
      echo "       日志: /tmp/pgy_edge_headless.log"
    fi
  fi
fi

# ---------- 1.5 Node 数据服务（抖音视频互动数据依赖） ----------
if curl -s -m 2 "http://127.0.0.1:${NODE_PORT}/" >/dev/null 2>&1; then
  echo "[OK] Node 数据服务已在运行 (端口 ${NODE_PORT})"
else
  echo "[启动] 正在拉起 Node 数据服务..."
  if [ -d "feishu-douyin-tool/backend" ]; then
    (cd feishu-douyin-tool/backend && nohup node ./bin/www >/tmp/feishu_douyin_node.log 2>&1 &)
    sleep 3
    if curl -s -m 2 "http://127.0.0.1:${NODE_PORT}/" >/dev/null 2>&1; then
      echo "[OK] Node 数据服务启动成功"
    else
      echo "[警告] Node 数据服务启动失败，抖音互动查询不可用"
      echo "       日志: /tmp/feishu_douyin_node.log"
    fi
  else
    echo "[警告] 未找到 feishu-douyin-tool，抖音互动查询不可用"
  fi
fi

# ---------- 2. 检查后端端口占用 ----------
if lsof -ti:$BACKEND_PORT >/dev/null 2>&1; then
  echo "[错误] 端口 ${BACKEND_PORT} 已被占用，旧实例可能还在运行。"
  echo "  处理方法:"
  echo "    1) 找到旧进程:  lsof -ti:${BACKEND_PORT}"
  echo "    2) 结束旧进程:  lsof -ti:${BACKEND_PORT} | xargs kill"
  echo "    3) 重新运行:    ./start.sh"
  exit 1
fi

# ---------- 3. 启动后端 ----------
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")
echo "[启动] 后端服务 (生产模式)..."
echo "  本机访问:  http://localhost:${BACKEND_PORT}"
echo "  同事访问:  http://${IP}:${BACKEND_PORT}   <- 把这个地址发给同事"
echo "  (需要同事与你处于同一网络/WiFi)"
echo "  按 Ctrl+C 停止服务"
echo "=================================================="

if [ ! -f "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi
"$PYTHON_BIN" backend/app.py
