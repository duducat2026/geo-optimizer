#!/usr/bin/env bash
# ============================================================
# GEO 主机首次初始化脚本
# 用法: bash deployment/init_server.sh
# 说明: 安装 Nginx、创建目录结构、配置域名分发（仅首次执行）
# ============================================================
set -e

REMOTE_HOST="your-ssh-host-alias"
REMOTE_IP="203.0.113.10"
DOMAIN="geo.tool.example.com"
DEPLOY_BASE="/opt/geotool"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "============================================================"
echo " GEO 主机初始化"
echo " 目标: ${REMOTE_IP}"
echo "============================================================"

# ---- Step 1: 系统基础 ----
echo ""
echo "[1/4] 安装系统基础组件..."
ssh "$REMOTE_HOST" bash <<'REMOTE_SCRIPT'
set -e

# 安装 Nginx
if ! command -v nginx &>/dev/null; then
    if [ -f /etc/redhat-release ]; then
        yum install -y nginx
    elif [ -f /etc/debian_version ]; then
        apt-get update -qq && apt-get install -y nginx
    fi
fi

systemctl enable nginx
systemctl start nginx 2>/dev/null || true

# 安装 Python3 及工具
if ! command -v python3 &>/dev/null; then
    if [ -f /etc/redhat-release ]; then
        yum install -y python3 python3-pip python3-devel
    elif [ -f /etc/debian_version ]; then
        apt-get install -y python3 python3-pip python3-venv python3-dev
    fi
fi

# Playwright 系统依赖
if [ -f /etc/redhat-release ]; then
    yum install -y nss atk at-spi2-atk cups-libs libdrm libXcomposite \
        libXdamage libXrandr mesa-libgbm pango alsa-lib 2>/dev/null || true
elif [ -f /etc/debian_version ]; then
    apt-get install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
        libdrm2 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 \
        libasound2 2>/dev/null || true
fi

# CJK 字体（PDF 报告中文渲染依赖）
if [ -f /etc/redhat-release ]; then
    yum install -y google-noto-sans-cjk-ttc-fonts 2>/dev/null || true
elif [ -f /etc/debian_version ]; then
    apt-get install -y fonts-noto-cjk 2>/dev/null || true
fi

echo "  基础组件安装完成"
REMOTE_SCRIPT

# ---- Step 2: 创建部署目录结构 ----
echo ""
echo "[2/4] 创建部署目录结构..."
ssh "$REMOTE_HOST" bash <<REMOTE_SCRIPT
set -e
mkdir -p ${DEPLOY_BASE}/{releases,shared/data/artifacts}
mkdir -p /var/log/geotool
echo "  目录结构:"
echo "    ${DEPLOY_BASE}/releases/   — 版本发布目录"
echo "    ${DEPLOY_BASE}/shared/     — 共享配置与数据"
echo "    ${DEPLOY_BASE}/current     — 当前版本软链接"
echo "    /var/log/geotool/          — 应用日志"
REMOTE_SCRIPT

# ---- Step 3: 部署 Nginx 配置 ----
echo ""
echo "[3/4] 配置 Nginx 域名分发..."
scp "${REPO_ROOT}/deployment/nginx_geotool.conf" "${REMOTE_HOST}:/etc/nginx/conf.d/geotool.conf"

ssh "$REMOTE_HOST" bash <<REMOTE_SCRIPT
set -e
# 验证配置
nginx -t

# 重载 Nginx
systemctl reload nginx
echo "  Nginx 配置生效: ${DOMAIN} → 127.0.0.1:5000"
REMOTE_SCRIPT

# ---- Step 4: 验证 ----
echo ""
echo "[4/4] 验证环境..."
ssh "$REMOTE_HOST" bash <<REMOTE_SCRIPT
echo "  系统: $(cat /etc/redhat-release 2>/dev/null || lsb_release -d 2>/dev/null | cut -f2)"
echo "  Python: $(python3 --version 2>/dev/null)"
echo "  Nginx: $(nginx -v 2>&1)"
echo "  MySQL: $(mysql --version 2>/dev/null || echo '未安装（运行 setup_mysql.sh）')"
echo "  部署目录: $(ls -d /opt/geotool 2>/dev/null && echo '就绪' || echo '缺失')"
REMOTE_SCRIPT

echo ""
echo "============================================================"
echo " 初始化完成!"
echo ""
echo " 后续步骤:"
echo "   1. bash deployment/setup_mysql.sh   # 安装MySQL并迁移数据"
echo "   2. bash deployment/deploy.sh        # 部署应用"
echo ""
echo " 域名解析（需在DNS服务商添加）:"
echo "   ${DOMAIN}  →  A记录  →  ${REMOTE_IP}"
echo "============================================================"
