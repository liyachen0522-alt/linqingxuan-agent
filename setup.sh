#!/bin/bash
# ================================================================
#  环境初始化脚本 — 克隆外部依赖 + 安装 Python 包
#  使用方法: ./setup.sh
# ================================================================
set -e
cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"

echo "=================================================="
echo "  林清轩种草智能体 - 环境初始化"
echo "=================================================="

# ---------- 1. 安装 Python 依赖 ----------
echo "[1/3] 安装 Python 依赖..."
pip install -r requirements.txt
echo "[OK] Python 依赖安装完成"

# ---------- 2. 克隆 Spider_XHS ----------
echo "[2/3] 检查 Spider_XHS..."
SPIDER_DIR="../Spider_XHS"
if [ -d "$SPIDER_DIR" ]; then
  echo "[OK] Spider_XHS 已存在，跳过"
else
  git clone https://github.com/cv-cat/Spider_XHS.git "$SPIDER_DIR"
  echo "[OK] Spider_XHS 克隆完成"
fi

# 安装 Spider_XHS 的 Python 依赖
if [ -f "$SPIDER_DIR/requirements.txt" ]; then
  echo "  安装 Spider_XHS Python 依赖..."
  pip install -r "$SPIDER_DIR/requirements.txt"
fi

# 提示配置 .env
if [ ! -f "$SPIDER_DIR/.env" ]; then
  echo ""
  echo "  [重要] 请配置小红书 Cookie:"
  echo "    1. 编辑 $SPIDER_DIR/.env"
  echo "    2. 填入 COOKIES=你的小红书Cookie"
  echo "    3. 或启动后在页面点「扫码刷新登录」自动获取"
  echo ""
fi

# ---------- 3. 克隆 feishu-douyin-tool ----------
echo "[3/3] 检查 feishu-douyin-tool..."
FEISHU_DIR="../feishu-douyin-tool"
if [ -d "$FEISHU_DIR" ]; then
  echo "[OK] feishu-douyin-tool 已存在，跳过"
else
  echo "[提示] feishu-douyin-tool 需手动获取并放在 $FEISHU_DIR"
  echo "       该项目用于抖音视频互动数据查询（端口 4000）"
  echo "       如不需要此功能可跳过"
fi

# 安装 Node 依赖
if [ -d "$FEISHU_DIR/backend" ]; then
  echo "  安装 feishu-douyin-tool Node 依赖..."
  (cd "$FEISHU_DIR/backend" && npm install 2>/dev/null || echo "  [警告] npm install 失败，请手动安装")
fi

echo ""
echo "=================================================="
echo "  初始化完成！"
echo "  启动: ./start.sh"
echo "  访问: http://localhost:5210"
echo "=================================================="
