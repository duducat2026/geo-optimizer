#!/usr/bin/env bash
# GEO 平台一键启动脚本
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# 1. 虚拟环境
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 2. 安装依赖
pip install -e ".[web]"

# 3. 安装 Playwright 浏览器（使用 npmmirror 镜像加速）
PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/ \
  playwright install chromium

# 4. 准备部署配置
if [ ! -f "deployment/settings.py" ]; then
  cp deployment/settings.example.py deployment/settings.py
  echo "[INFO] 已生成 deployment/settings.py，请按需修改数据库/密钥配置"
fi

# 5. 初始化数据库与种子数据
python deployment/init_platform.py

# 6. 启动服务
HOST="${GEO_HOST:-0.0.0.0}"
PORT="${GEO_PORT:-5000}"
echo "[INFO] 启动 GEO 平台: http://localhost:${PORT}"
python -m geo_optimizer.web.app --host "$HOST" --port "$PORT"
