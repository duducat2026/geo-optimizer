#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GEO 平台初始化脚本

功能：
1. 创建数据库 `geo-op`（若不存在）
2. 创建所有数据表（SQLAlchemy create_all）
3. 写入系统 LLM 默认配置种子数据
4. 写入演示数据：普通用户 geo_tool + 一把**限额**通用 API 密钥（供 MCP / Skill 导出开箱即用）

用法：
    python deployment/init_platform.py

注意：
- 管理员账号**不在本脚本初始化**（由 settings.py 的 seed_defaults 或后台维护）。
- 本脚本用于「快速起步 / 演示」，内含写死的演示用户口令与通用 API 密钥；所有密钥均强制限额。
  正式对外部署请务必登录后修改口令、并轮换或删除该通用密钥。
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 确保可导入 src 下的包
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from geo_optimizer.web.portal.settings import get_settings  # noqa: E402

# ---- 演示数据默认值（写死，便于开箱即用；上线请修改） ----
# 说明：管理员账号不在这里初始化（由 settings.py 的 seed_defaults 或后台维护），
#       本脚本只初始化「演示普通用户 + 通用 API 密钥」。
DEMO_USER_USERNAME = "geo_tool"
DEMO_USER_PASSWORD = "geo_tool666"
# 通用 API 密钥明文（MCP / Skill 导出会把它写入 config.json / mcp-config.json）
DEMO_API_KEY_PLAIN = "geo_General2026DemoKey00000000000000"
DEMO_API_KEY_NAME = "通用密钥(演示)"
DEMO_API_KEY_QUOTA = 50  # 通用密钥每日调用额度（所有密钥都必须限额，不允许 0 不限）


def ensure_database() -> None:
    """连接 MySQL 服务器并创建数据库（库名含连字符，用反引号）。"""
    import pymysql

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


def seed_demo_data() -> None:
    """幂等写入演示数据：普通用户 geo_tool + 一把限额的通用 API 密钥。

    不初始化管理员账号（由 settings.py 的 seed_defaults 或后台维护）。
    """
    from geo_optimizer.web.portal.api.auth import _hash_key
    from geo_optimizer.web.portal.extensions import db
    from geo_optimizer.web.portal.models import ROLE_USER, ApiKey, User

    # 1) 普通用户 geo_tool（默认配额 50，可直接登录）
    user = User.query.filter_by(username=DEMO_USER_USERNAME).first()
    if not user:
        user = User(username=DEMO_USER_USERNAME, role=ROLE_USER, eval_quota=50)
        user.set_password(DEMO_USER_PASSWORD)
        db.session.add(user)
        db.session.commit()
        print(f"[OK] 已创建普通用户: {DEMO_USER_USERNAME}")
    else:
        print(f"[SKIP] 普通用户已存在: {DEMO_USER_USERNAME}")

    # 2) 通用 API 密钥（写死明文，每日额度受限，供 MCP / Skill 导出开箱即用）
    key_hash = _hash_key(DEMO_API_KEY_PLAIN)
    existing = ApiKey.query.filter_by(key_hash=key_hash).first()
    if not existing:
        api_key = ApiKey(
            user_id=user.id,
            key_hash=key_hash,
            key_prefix=DEMO_API_KEY_PLAIN[:12],
            key_plaintext=DEMO_API_KEY_PLAIN,
            name=DEMO_API_KEY_NAME,
            expires_at=datetime.utcnow() + timedelta(days=3650),
            is_active=True,
            daily_quota=DEMO_API_KEY_QUOTA,  # 所有密钥都必须限额，禁止 0 不限
        )
        db.session.add(api_key)
        db.session.commit()
        print(f"[OK] 已为 {DEMO_USER_USERNAME} 创建通用 API 密钥: {DEMO_API_KEY_PLAIN} "
              f"(每日额度 {DEMO_API_KEY_QUOTA})")
    else:
        print(f"[SKIP] 通用 API 密钥已存在（属主 id={existing.user_id}）")


def main() -> None:
    ensure_database()
    # 延迟导入，确保数据库已创建
    from geo_optimizer.web.portal.app import create_app

    app = create_app()
    with app.app_context():
        print("[OK] 数据表与基础种子已初始化（建表 + 系统配置）")
        seed_demo_data()
    print("\n完成。启动服务： geo-web  或  python -m geo_optimizer.web.app")
    print(f"  演示用户登录： {DEMO_USER_USERNAME} / {DEMO_USER_PASSWORD}")
    print(f"  通用 API 密钥： {DEMO_API_KEY_PLAIN} (每日额度 {DEMO_API_KEY_QUOTA})")
    print("  在用户侧「API 密钥」页对该密钥可一键导出 Skill / MCP 包。")
    print("  注：管理员账号不在本脚本初始化，请通过 settings.py 或后台维护。")


if __name__ == "__main__":
    main()
