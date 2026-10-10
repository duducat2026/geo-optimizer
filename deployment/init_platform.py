#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GEO 平台初始化脚本

功能：
1. 创建数据库 `geo-op`（若不存在）
2. 创建所有数据表（SQLAlchemy create_all）
3. 写入默认管理员与系统 LLM 配置种子数据

用法：
    python deployment/init_platform.py
"""
import sys
from pathlib import Path

# 确保可导入 src 下的包
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import pymysql  # noqa: E402

from geo_optimizer.web.portal.settings import get_settings  # noqa: E402


def ensure_database() -> None:
    """连接 MySQL 服务器并创建数据库（库名含连字符，用反引号）。"""
    s = get_settings()
    conn = pymysql.connect(
        host=s["DB_HOST"],
        port=int(s["DB_PORT"]),
        user=s["DB_USER"],
        password=s["DB_PASSWORD"],
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{s['DB_NAME']}` "
                "DEFAULT CHARACTER SET utf8mb4 "
                "DEFAULT COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
        print(f"[OK] 数据库 `{s['DB_NAME']}` 已就绪")
    finally:
        conn.close()


def main() -> None:
    ensure_database()
    # 延迟导入，确保数据库已创建
    from geo_optimizer.web.portal.app import create_app

    app = create_app()
    with app.app_context():
        print("[OK] 数据表与种子数据已初始化（建表 + admin + 系统配置）")
    print("\n完成。启动服务： geo-web  或  python -m geo_optimizer.web.app")


if __name__ == "__main__":
    main()
