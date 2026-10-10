-- GEO 平台数据库初始化
-- 库名 geo-op 含连字符，需用反引号
CREATE DATABASE IF NOT EXISTS `geo-op`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

-- 表结构由应用启动时通过 SQLAlchemy create_all 自动创建
-- 亦可运行: python deployment/init_platform.py
