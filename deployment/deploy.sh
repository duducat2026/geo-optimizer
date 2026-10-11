#!/usr/bin/env bash
# ============================================================
# GEO-Optimizer 云端部署脚本
# 用法: bash deployment/deploy.sh
# 说明: 将本地 geo-optimizer 打包并部署到 GEO 主机
# ============================================================
set -e

# ---- 部署配置（可通过环境变量覆盖，避免真实信息入库） ----
REMOTE_HOST="${REMOTE_HOST:-your-ssh-host-alias}"   # SSH 别名 (~/.ssh/config)
REMOTE_IP="${REMOTE_IP:-203.0.113.10}"
REMOTE_USER="${REMOTE_USER:-root}"
DEPLOY_BASE="${DEPLOY_BASE:-/opt/geotool}"           # 云端部署根目录
APP_PORT=${APP_PORT:-5000}                            # Flask 应用端口
DOMAIN="${DOMAIN:-geo.tool.example.com}"

# ---- 版本号生成: geotool-release-yyyyMMddHHmmss-v0.1.0 ----
TIMESTAMP=$(date +"%Y%m%d%H%M%S")
VERSION="geotool-release-${TIMESTAMP}-v0.1.0"
RELEASE_DIR="${DEPLOY_BASE}/releases/${VERSION}"
CURRENT_LINK="${DEPLOY_BASE}/current"

# ---- 本地路径 ----
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "============================================================"
echo " GEO-Optimizer 部署"
echo " 版本: ${VERSION}"
echo " 目标: ${REMOTE_USER}@${REMOTE_IP} (${REMOTE_HOST})"
echo " 域名: https://${DOMAIN}"
echo "============================================================"

# ---- Step 1: 本地打包 ----
echo ""
echo "[1/7] 本地打包..."
ARCHIVE="/tmp/${VERSION}.tar.gz"
tar czf "$ARCHIVE" \
    --exclude='.venv' \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='*.egg-info' \
    --exclude='tmp' \
    --exclude='output' \
    --exclude='node_modules' \
    --exclude='data/artifacts' \
    --exclude='backups' \
    -C "$REPO_ROOT" .
echo "  打包完成: ${ARCHIVE} ($(du -h "$ARCHIVE" | cut -f1))"

# ---- Step 2: 上传到云端 ----
echo ""
echo "[2/7] 上传到 GEO 主机..."
ssh "$REMOTE_HOST" "mkdir -p ${DEPLOY_BASE}/releases ${DEPLOY_BASE}/shared/data/artifacts"
# 分块流式上传：本地代理可能掐断单条大流量传输，切成小分块、每块独立短连接并重试。
SPLIT_DIR="$(mktemp -d)"
split -b 2m "$ARCHIVE" "${SPLIT_DIR}/part."
first=1
for p in "${SPLIT_DIR}"/part.*; do
    n=0
    redirect=">"
    [ "$first" = "1" ] || redirect=">>"
    first=0
    until ssh "$REMOTE_HOST" "cat ${redirect} /tmp/${VERSION}.tar.gz" < "$p"; do
        n=$((n + 1))
        if [ "$n" -ge 4 ]; then
            echo "  [ERROR] 分块上传失败: $p"
            rm -rf "$SPLIT_DIR"
            exit 1
        fi
        echo "  分块重试 ($n): $(basename "$p")"
        sleep 2
    done
done
rm -rf "$SPLIT_DIR"
echo "  上传完成"

# ---- Step 3: 云端解压与安装 ----
echo ""
echo "[3/7] 云端解压与安装依赖..."
ssh "$REMOTE_HOST" bash <<REMOTE_SCRIPT
set -e
# 解压到版本目录
mkdir -p "${RELEASE_DIR}"
tar xzf "/tmp/${VERSION}.tar.gz" -C "${RELEASE_DIR}"
rm -f "/tmp/${VERSION}.tar.gz"

# 创建虚拟环境并安装依赖（使用 Python 3.11）
cd "${RELEASE_DIR}"
if [ ! -d ".venv" ]; then
    python3.11 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e ".[web,mcp]" -q
pip install gunicorn -q

# 安装 Playwright 浏览器
PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/ \
    playwright install chromium 2>/dev/null || true

echo "  依赖安装完成"
REMOTE_SCRIPT

# ---- Step 4: 同步共享配置与数据 ----
echo ""
echo "[4/7] 同步配置与数据目录..."
ssh "$REMOTE_HOST" bash <<REMOTE_SCRIPT
set -e
SHARED="${DEPLOY_BASE}/shared"

# 配置文件（首次部署时从 example 生成）
if [ ! -f "\${SHARED}/settings.py" ]; then
    cp "${RELEASE_DIR}/deployment/settings.example.py" "\${SHARED}/settings.py"
    echo "  [INFO] 已生成 shared/settings.py，请按需修改数据库配置"
fi

# MCP 服务端环境（首次部署时从 example 生成；含 API Key，chmod 600，不进版本库）
if [ ! -f "\${SHARED}/mcp.env" ]; then
    cp "${RELEASE_DIR}/deployment/mcp.env.example" "\${SHARED}/mcp.env"
    chmod 600 "\${SHARED}/mcp.env"
    echo "  [INFO] 已生成 shared/mcp.env，请填入有效的 GEO_API_KEY 后 systemctl restart geo-mcp"
fi

# 软链接配置到当前版本
ln -sf "\${SHARED}/settings.py" "${RELEASE_DIR}/deployment/settings.py"

# 软链接数据目录
ln -sf "\${SHARED}/data/artifacts" "${RELEASE_DIR}/data/artifacts"

# 写入版本信息
echo "${VERSION}" > "${RELEASE_DIR}/VERSION"
echo "  配置同步完成"
REMOTE_SCRIPT

# ---- Step 5: 切换当前版本 ----
echo ""
echo "[5/7] 切换当前版本..."
ssh "$REMOTE_HOST" bash <<REMOTE_SCRIPT
set -e
ln -sfn "${RELEASE_DIR}" "${CURRENT_LINK}"
echo "  当前版本: \$(cat ${CURRENT_LINK}/VERSION)"

# 清理旧版本（保留最近 5 个）
cd "${DEPLOY_BASE}/releases"
ls -dt */ 2>/dev/null | tail -n +6 | xargs -r rm -rf
echo "  旧版本清理完成（保留最近5个）"
REMOTE_SCRIPT

# ---- Step 6: 重启服务 ----
echo ""
echo "[6/7] 重启应用服务..."
ssh "$REMOTE_HOST" bash <<REMOTE_SCRIPT
set -e
# 安装/更新 systemd 服务文件（平台 geotool + MCP 服务 geo-mcp）
cp "${CURRENT_LINK}/deployment/geotool.service" /etc/systemd/system/geotool.service
cp "${CURRENT_LINK}/deployment/geo-mcp.service" /etc/systemd/system/geo-mcp.service
systemctl daemon-reload
systemctl enable geotool geo-mcp
systemctl restart geotool
systemctl restart geo-mcp

# 等待启动并逐一校验
sleep 3
for svc in geotool geo-mcp; do
    if systemctl is-active --quiet \$svc; then
        echo "  \$svc 启动成功 ✓"
    else
        echo "  [ERROR] \$svc 启动失败，查看日志: journalctl -u \$svc -n 50"
        exit 1
    fi
done
REMOTE_SCRIPT

# ---- Step 7: 同步 Nginx 配置（新增 /mcp streamable-HTTP 反代）----
echo ""
echo "[7/7] 同步 Nginx 配置..."
# 仓库模板为开源脱敏版（域名为 geo.tool.example.com），上传前用真实 DOMAIN 替换，
# 避免证书路径与云端不符导致 nginx -t 失败。
NGINX_RENDERED="/tmp/${VERSION}.nginx.local"
sed "s/geo\.tool\.example\.com/${DOMAIN}/g" \
    "${REPO_ROOT}/deployment/nginx_geotool.conf" > "$NGINX_RENDERED"
scp "$NGINX_RENDERED" "${REMOTE_HOST}:/tmp/geotool.conf.new"
rm -f "$NGINX_RENDERED"
ssh "$REMOTE_HOST" bash <<'REMOTE_SCRIPT'
set -e
CONF=/etc/nginx/conf.d/geotool.conf
NEW=/tmp/geotool.conf.new
# 备份现有配置（若存在）
if [ -f "$CONF" ]; then
    cp "$CONF" "${CONF}.bak.$(date +%Y%m%d%H%M%S)"
fi
# 覆盖后校验；nginx -t 失败则回滚最近备份（未 reload，线上不受影响）
cp "$NEW" "$CONF"
if nginx -t 2>/tmp/nginx_test.log; then
    systemctl reload nginx
    echo "  Nginx 已 reload：/ → 127.0.0.1:5000, /mcp → 127.0.0.1:8000"
else
    echo "  [ERROR] nginx -t 校验失败，回滚："
    cat /tmp/nginx_test.log
    LATEST_BAK=$(ls -t ${CONF}.bak.* 2>/dev/null | head -1)
    if [ -n "$LATEST_BAK" ]; then
        cp "$LATEST_BAK" "$CONF"
        nginx -t && systemctl reload nginx
        echo "  已回滚到: $LATEST_BAK"
    fi
    rm -f "$NEW"
    exit 1
fi
rm -f "$NEW"
REMOTE_SCRIPT

# ---- 完成 ----
echo ""
echo "============================================================"
echo " 部署完成!"
echo " 版本: ${VERSION}"
echo " 平台: https://${DOMAIN}"
echo " MCP : https://${DOMAIN}/mcp  (streamable-HTTP)"
echo " 管理: ssh ${REMOTE_HOST}"
echo " 日志: ssh ${REMOTE_HOST} 'journalctl -u geotool -f'"
echo "       ssh ${REMOTE_HOST} 'journalctl -u geo-mcp -f'"
echo "============================================================"

# 清理本地临时文件
rm -f "$ARCHIVE"
