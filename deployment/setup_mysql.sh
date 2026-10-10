#!/usr/bin/env bash
# ============================================================
# GEO 主机 MySQL 8 社区版安装 + 本地数据迁移
# 用法: bash deployment/setup_mysql.sh
# 说明: 在云端安装 MySQL8，并将本地 geo-op 数据库迁移到云端
# ============================================================
set -e

# ---- 配置（可用环境变量覆盖，避免把真实主机/口令写进脚本） ----
REMOTE_HOST="${REMOTE_HOST:-your-ssh-host-alias}"
REMOTE_IP="${REMOTE_IP:-203.0.113.10}"
DB_NAME="geo-op"
DB_USER="root"
DB_PASSWORD="${DB_PASSWORD:-change-me-db-password}"
LOCAL_DB_HOST="localhost"
LOCAL_DB_PORT="3306"

# ---- 本地路径 ----
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DUMP_FILE="/tmp/${DB_NAME}_migration_$(date +%Y%m%d%H%M%S).sql"

echo "============================================================"
echo " MySQL 8 安装 & 数据迁移"
echo " 目标主机: ${REMOTE_IP}"
echo " 数据库: ${DB_NAME}"
echo "============================================================"

# ---- Step 1: 云端安装 MySQL 8 社区版 ----
echo ""
echo "[1/4] 云端安装 MySQL 8 社区版..."
ssh "$REMOTE_HOST" bash <<'REMOTE_SCRIPT'
set -e

# 检测是否已安装
if command -v mysql &>/dev/null && mysql --version | grep -q "8\."; then
    echo "  MySQL 8 已安装: $(mysql --version)"
    exit 0
fi

# 检测系统类型
if [ -f /etc/redhat-release ]; then
    # CentOS / Alibaba Cloud Linux
    echo "  检测到 RHEL 系系统，使用 yum 安装..."
    
    # 添加 MySQL 官方 yum 源
    if [ ! -f /etc/yum.repos.d/mysql-community.repo ]; then
        rpm -Uvh https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm 2>/dev/null || \
        rpm -Uvh https://dev.mysql.com/get/mysql80-community-release-el9-5.noarch.rpm 2>/dev/null || true
    fi
    
    yum install -y mysql-community-server
    
elif [ -f /etc/debian_version ]; then
    # Ubuntu / Debian
    echo "  检测到 Debian 系系统，使用 apt 安装..."
    
    apt-get update -qq
    apt-get install -y mysql-server
    
else
    echo "  [ERROR] 未识别的操作系统，请手动安装 MySQL 8"
    exit 1
fi

# 启动 MySQL
systemctl start mysqld 2>/dev/null || systemctl start mysql 2>/dev/null || true
systemctl enable mysqld 2>/dev/null || systemctl enable mysql 2>/dev/null || true

echo "  MySQL 安装完成: $(mysql --version)"
REMOTE_SCRIPT

# ---- Step 2: 配置 MySQL root 密码 ----
echo ""
echo "[2/4] 配置 MySQL 访问..."
ssh "$REMOTE_HOST" bash <<REMOTE_SCRIPT
set -e

# 尝试获取临时密码（首次安装时 MySQL 会生成）
TEMP_PASS=\$(grep 'temporary password' /var/log/mysqld.log 2>/dev/null | tail -1 | awk '{print \$NF}')

if [ -n "\$TEMP_PASS" ]; then
    echo "  检测到临时密码，修改 root 密码..."
    mysql -u root -p"\$TEMP_PASS" --connect-expired-password -e "
        ALTER USER 'root'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
        FLUSH PRIVILEGES;
    " 2>/dev/null || true
else
    # 无临时密码（Ubuntu 或已配置过），直接尝试设置
    mysql -u root -e "
        ALTER USER 'root'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
        FLUSH PRIVILEGES;
    " 2>/dev/null || \
    mysql -u root -p"${DB_PASSWORD}" -e "SELECT 1" 2>/dev/null || true
fi

# 创建数据库
mysql -u root -p"${DB_PASSWORD}" -e "
    CREATE DATABASE IF NOT EXISTS \\\`${DB_NAME}\\\`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;
"
echo "  数据库 \`${DB_NAME}\` 已就绪"
REMOTE_SCRIPT

# ---- Step 3: 本地数据库导出 ----
echo ""
echo "[3/4] 导出本地数据库 ${DB_NAME}..."
mysqldump -h "$LOCAL_DB_HOST" -P "$LOCAL_DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" \
    --databases "$DB_NAME" \
    --single-transaction \
    --routines \
    --triggers \
    --set-gtid-purged=OFF \
    > "$DUMP_FILE"
echo "  导出完成: ${DUMP_FILE} ($(du -h "$DUMP_FILE" | cut -f1))"

# ---- Step 4: 上传并导入到云端 ----
echo ""
echo "[4/4] 上传并导入到云端 MySQL..."
scp "$DUMP_FILE" "${REMOTE_HOST}:/tmp/geotool_dump.sql"

ssh "$REMOTE_HOST" bash <<REMOTE_SCRIPT
set -e
mysql -u root -p"${DB_PASSWORD}" < /tmp/geotool_dump.sql
rm -f /tmp/geotool_dump.sql
echo "  数据导入完成"

# 验证
TABLE_COUNT=\$(mysql -u root -p"${DB_PASSWORD}" -N -e "
    SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB_NAME}';
")
echo "  验证: \`${DB_NAME}\` 共 \${TABLE_COUNT} 张表"
REMOTE_SCRIPT

# 清理本地临时文件
rm -f "$DUMP_FILE"

echo ""
echo "============================================================"
echo " MySQL 迁移完成!"
echo " 云端连接: mysql -h ${REMOTE_IP} -u ${DB_USER} -p"
echo " 数据库: ${DB_NAME}"
echo "============================================================"
