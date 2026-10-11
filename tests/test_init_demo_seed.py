# -*- coding: utf-8 -*-
"""演示种子脚本 init_platform.seed_demo_data 测试（SQLite）。"""
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture()
def init_mod():
    """按文件路径加载 deployment/init_platform.py（不触发 MySQL 连接）。"""
    path = Path(__file__).resolve().parent.parent / "deployment" / "init_platform.py"
    spec = importlib.util.spec_from_file_location("init_platform", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestDemoSeed:
    def test_seed_creates_user_and_limited_key(self, app, init_mod):
        from geo_optimizer.web.portal.api.auth import verify_api_key
        from geo_optimizer.web.portal.models import ApiKey, User

        with app.app_context():
            init_mod.seed_demo_data()

            tool = User.query.filter_by(username=init_mod.DEMO_USER_USERNAME).first()
            assert tool and not tool.is_admin
            assert tool.check_password(init_mod.DEMO_USER_PASSWORD)

            # 管理员账号不应由演示种子创建
            assert User.query.filter_by(username="geoadmin").first() is None

            key = ApiKey.query.filter_by(key_plaintext=init_mod.DEMO_API_KEY_PLAIN).first()
            assert key is not None
            assert key.user_id == tool.id
            assert key.daily_quota == init_mod.DEMO_API_KEY_QUOTA  # 必须限额，非 0/不限
            assert key.daily_quota > 0
            assert key.is_valid

        # 通用密钥可用于开放 API 鉴权，且归属 geo_tool
        with app.app_context():
            result = verify_api_key(init_mod.DEMO_API_KEY_PLAIN)
            assert result is not None
            user, _k = result
            assert user.username == init_mod.DEMO_USER_USERNAME

    def test_seed_is_idempotent(self, app, init_mod):
        from geo_optimizer.web.portal.models import ApiKey, User

        with app.app_context():
            init_mod.seed_demo_data()
            users_before = User.query.count()
            keys_before = ApiKey.query.count()

        with app.app_context():
            init_mod.seed_demo_data()  # 第二次不应重复创建
            assert User.query.count() == users_before
            assert ApiKey.query.count() == keys_before

    def test_general_key_supports_export_fields(self, app, init_mod):
        """导出的 config.json 依赖 key_plaintext，确保已落库。"""
        from geo_optimizer.web.portal.models import ApiKey

        with app.app_context():
            init_mod.seed_demo_data()
            key = ApiKey.query.filter_by(key_plaintext=init_mod.DEMO_API_KEY_PLAIN).first()
            assert key and key.key_plaintext == init_mod.DEMO_API_KEY_PLAIN
            assert key.key_prefix == init_mod.DEMO_API_KEY_PLAIN[:12]
