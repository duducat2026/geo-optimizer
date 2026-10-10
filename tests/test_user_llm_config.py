# -*- coding: utf-8 -*-
"""用户侧算力配置功能测试。"""
from geo_optimizer.web.portal.auth.service import create_user


class TestUserLLMConfig:
    """用户算力配置 CRUD、激活、删除。"""

    def _login_user(self, app, client, username="llmuser"):
        with app.app_context():
            create_user(username, "pass123", eval_quota=10)
        client.post("/login", data={"username": username, "password": "pass123"})
        return client

    def test_llm_config_page_accessible(self, app, client):
        self._login_user(app, client)
        resp = client.get("/llm-config")
        assert resp.status_code == 200

    def test_create_llm_config(self, app, client):
        self._login_user(app, client)
        resp = client.post("/llm-config/save", data={
            "provider": "bailian",
            "name": "我的百炼",
            "api_key": "sk-test1234567890",
            "base_url": "",
            "model": "qwen-plus",
        })
        assert resp.status_code == 302
        from geo_optimizer.web.portal.models import UserLLMConfig
        with app.app_context():
            cfg = UserLLMConfig.query.first()
            assert cfg is not None
            assert cfg.provider == "bailian"
            assert cfg.name == "我的百炼"
            # 非自定义方案自动填充 base_url
            assert "dashscope" in cfg.base_url

    def test_create_token_plan_config(self, app, client):
        self._login_user(app, client)
        resp = client.post("/llm-config/save", data={
            "provider": "token_plan",
            "name": "TP Key",
            "api_key": "sk-sp-test1234567890",
            "base_url": "",
            "model": "qwen3.7-max",
        })
        assert resp.status_code == 302
        from geo_optimizer.web.portal.models import UserLLMConfig
        with app.app_context():
            cfg = UserLLMConfig.query.first()
            assert "token-plan" in cfg.base_url

    def test_api_key_required(self, app, client):
        self._login_user(app, client)
        resp = client.post("/llm-config/save", data={
            "provider": "bailian",
            "name": "no key",
            "api_key": "",
        }, follow_redirects=True)
        assert resp.status_code == 200
        from geo_optimizer.web.portal.models import UserLLMConfig
        with app.app_context():
            assert UserLLMConfig.query.count() == 0

    def test_activate_config(self, app, client):
        self._login_user(app, client)
        # 创建两条配置
        client.post("/llm-config/save", data={
            "provider": "bailian", "name": "A", "api_key": "sk-aaa1234567890",
        })
        client.post("/llm-config/save", data={
            "provider": "token_plan", "name": "B", "api_key": "sk-sp-bbb1234567890",
        })
        from geo_optimizer.web.portal.models import UserLLMConfig
        with app.app_context():
            cfgs = UserLLMConfig.query.all()
            assert len(cfgs) == 2
            cfg_id = cfgs[0].id

        # 激活第一条
        resp = client.post(f"/llm-config/{cfg_id}/activate")
        assert resp.status_code == 302
        with app.app_context():
            active = UserLLMConfig.query.filter_by(is_active=True).all()
            assert len(active) == 1
            assert active[0].id == cfg_id

    def test_delete_config(self, app, client):
        self._login_user(app, client)
        client.post("/llm-config/save", data={
            "provider": "bailian", "name": "del", "api_key": "sk-del1234567890",
        })
        from geo_optimizer.web.portal.models import UserLLMConfig
        with app.app_context():
            cfg_id = UserLLMConfig.query.first().id
        resp = client.post(f"/llm-config/{cfg_id}/delete")
        assert resp.status_code == 302
        with app.app_context():
            assert UserLLMConfig.query.count() == 0

    def test_cannot_access_other_user_config(self, app, client):
        self._login_user(app, client, username="user_a")
        client.post("/llm-config/save", data={
            "provider": "bailian", "name": "A", "api_key": "sk-aaa1234567890",
        })
        from geo_optimizer.web.portal.models import UserLLMConfig
        with app.app_context():
            cfg_id = UserLLMConfig.query.first().id

        # 另一个用户登录
        client.post("/logout")
        with app.app_context():
            create_user("user_b", "pass123", eval_quota=10)
        client.post("/login", data={"username": "user_b", "password": "pass123"})
        resp = client.post(f"/llm-config/{cfg_id}/activate")
        assert resp.status_code == 404


class TestLLMConfigTest:
    """调用测试：成功提示算力方案+模型，并展示调用过程明细。"""

    def _login_and_create(self, app, client, username="testcall"):
        with app.app_context():
            create_user(username, "pass123", eval_quota=10)
        client.post("/login", data={"username": username, "password": "pass123"})
        client.post("/llm-config/save", data={
            "provider": "token_plan", "name": "TP测试",
            "api_key": "sk-sp-test1234567890", "model": "qwen-plus",
        })
        from geo_optimizer.web.portal.models import UserLLMConfig
        with app.app_context():
            return UserLLMConfig.query.first().id

    def test_success_shows_provider_model_and_process(self, app, client, monkeypatch):
        cfg_id = self._login_and_create(app, client)

        from geo_optimizer.web.portal.user import routes as user_routes

        def fake_test(api_key, base_url, model):
            return True, {
                "endpoint": base_url, "model_requested": model,
                "model_responded": "qwen-plus-2026", "elapsed_ms": 321,
                "usage": {"prompt": 9, "completion": 5, "total": 14},
                "reply": "Hello!", "error": "",
            }

        monkeypatch.setattr(user_routes, "_test_llm_connection", fake_test)
        resp = client.post(f"/llm-config/{cfg_id}/test", follow_redirects=True)
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        # flash 摘要：方案 + 模型
        assert "连接成功" in html
        assert "Token Plan 团队版" in html
        assert "qwen-plus-2026" in html
        # 调用过程明细
        assert "调用过程" in html
        assert "321 ms" in html
        assert "token-plan" in html  # 请求端点
        assert "Hello!" in html     # 模型回复

    def test_failure_shows_error_process(self, app, client, monkeypatch):
        cfg_id = self._login_and_create(app, client, username="testfail")

        from geo_optimizer.web.portal.user import routes as user_routes

        def fake_test(api_key, base_url, model):
            return False, {
                "endpoint": base_url, "model_requested": model,
                "model_responded": "", "elapsed_ms": 15000,
                "usage": None, "reply": "", "error": "Error code: 401 - invalid api key",
            }

        monkeypatch.setattr(user_routes, "_test_llm_connection", fake_test)
        resp = client.post(f"/llm-config/{cfg_id}/test", follow_redirects=True)
        html = resp.data.decode("utf-8")
        assert "连接失败" in html
        assert "invalid api key" in html
        assert "调用过程" in html

    def test_detail_shown_once_only(self, app, client, monkeypatch):
        """过程明细仅展示一次，刷新后消失。"""
        cfg_id = self._login_and_create(app, client, username="testonce")

        from geo_optimizer.web.portal.user import routes as user_routes
        monkeypatch.setattr(
            user_routes, "_test_llm_connection",
            lambda k, u, m: (True, {
                "endpoint": u, "model_requested": m, "model_responded": "m1",
                "elapsed_ms": 100, "usage": None, "reply": "hi", "error": "",
            }),
        )
        resp = client.post(f"/llm-config/{cfg_id}/test", follow_redirects=True)
        # 页内明细卡片（无 JS 回退路径）已渲染
        assert 'card" style="border-left' in resp.data.decode("utf-8")
        # 再次刷新列表页，明细不再展示
        resp2 = client.get("/llm-config")
        assert 'card" style="border-left' not in resp2.data.decode("utf-8")

    def test_cannot_test_other_user_config(self, app, client):
        cfg_id = self._login_and_create(app, client, username="owner_t")
        client.post("/logout")
        with app.app_context():
            create_user("intruder_t", "pass123", eval_quota=5)
        client.post("/login", data={"username": "intruder_t", "password": "pass123"})
        assert client.post(f"/llm-config/{cfg_id}/test").status_code == 404

    def test_ajax_returns_json_for_modal(self, app, client, monkeypatch):
        """AJAX 调用（X-Requested-With: fetch）直接返回 JSON 供浮层展示。"""
        cfg_id = self._login_and_create(app, client, username="testajax")

        from geo_optimizer.web.portal.user import routes as user_routes
        monkeypatch.setattr(
            user_routes, "_test_llm_connection",
            lambda k, u, m: (True, {
                "endpoint": u, "model_requested": m, "model_responded": "m-ajax",
                "elapsed_ms": 88, "usage": {"prompt": 3, "completion": 2, "total": 5},
                "reply": "hey", "error": "",
            }),
        )
        resp = client.post(f"/llm-config/{cfg_id}/test",
                           headers={"X-Requested-With": "fetch"})
        assert resp.status_code == 200
        assert resp.is_json
        data = resp.get_json()
        assert data["ok"] is True
        assert data["model_responded"] == "m-ajax"
        assert data["provider_label"] == "Token Plan 团队版"
        assert data["elapsed_ms"] == 88
        # AJAX 路径不写 session，刷新列表页不会出现页内明细卡片
        assert 'card" style="border-left' not in client.get("/llm-config").data.decode("utf-8")

    def test_ajax_failure_returns_error_json(self, app, client, monkeypatch):
        cfg_id = self._login_and_create(app, client, username="testajaxf")

        from geo_optimizer.web.portal.user import routes as user_routes
        monkeypatch.setattr(
            user_routes, "_test_llm_connection",
            lambda k, u, m: (False, {
                "endpoint": u, "model_requested": m, "model_responded": "",
                "elapsed_ms": 15000, "usage": None, "reply": "",
                "error": "Error code: 401 - invalid api key",
            }),
        )
        resp = client.post(f"/llm-config/{cfg_id}/test",
                           headers={"X-Requested-With": "fetch"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is False
        assert "invalid api key" in data["error"]

    def test_modal_markup_rendered(self, app, client):
        """列表页包含测试结果浮层骨架与 fetch 拦截脚本。"""
        self._login_and_create(app, client, username="testmodal")
        html = client.get("/llm-config").data.decode("utf-8")
        assert 'id="test-modal"' in html
        assert "llm-test-form" in html
        assert "showTestModal" in html


class TestLLMConfigRevealKey:
    """算力配置密钥明文查看。"""

    def _login_and_create(self, app, client, username="revealer"):
        with app.app_context():
            create_user(username, "pass123", eval_quota=10)
        client.post("/login", data={"username": username, "password": "pass123"})
        client.post("/llm-config/save", data={
            "provider": "token_plan", "name": "reveal",
            "api_key": "sk-sp-reveal-secret-123456",
        })
        from geo_optimizer.web.portal.models import UserLLMConfig
        with app.app_context():
            return UserLLMConfig.query.first().id

    def test_owner_can_reveal_plaintext(self, app, client):
        cfg_id = self._login_and_create(app, client)
        resp = client.get(f"/llm-config/{cfg_id}/key")
        assert resp.status_code == 200
        assert resp.get_json()["api_key"] == "sk-sp-reveal-secret-123456"

    def test_list_page_shows_masked_only(self, app, client):
        """列表页不预埋明文，仅展示脱敏密钥。"""
        self._login_and_create(app, client, username="masked_u")
        html = client.get("/llm-config").data.decode("utf-8")
        assert "sk-sp-reveal-secret-123456" not in html
        assert "sk-sp-" in html  # 脱敏前缀仍展示

    def test_reveal_records_audit(self, app, client):
        cfg_id = self._login_and_create(app, client, username="audit_u")
        client.get(f"/llm-config/{cfg_id}/key")
        from geo_optimizer.web.portal.models import AuditLog
        with app.app_context():
            log = AuditLog.query.filter_by(action="llm_config_reveal_key").first()
            assert log is not None

    def test_cannot_reveal_other_user_key(self, app, client):
        cfg_id = self._login_and_create(app, client, username="owner_r")
        client.post("/logout")
        with app.app_context():
            create_user("intruder_r", "pass123", eval_quota=5)
        client.post("/login", data={"username": "intruder_r", "password": "pass123"})
        assert client.get(f"/llm-config/{cfg_id}/key").status_code == 404


class TestAdminUserLLM:
    """管理侧查看用户算力配置。"""

    def test_admin_can_view_user_llm_page(self, admin_login):
        resp = admin_login.get("/admin/user-llm")
        assert resp.status_code == 200

    def test_admin_search_by_username(self, app, admin_login):
        with app.app_context():
            user = create_user("searchme", "pass123", eval_quota=5)
            from geo_optimizer.web.portal.models import UserLLMConfig
            from geo_optimizer.web.portal.extensions import db
            cfg = UserLLMConfig(user_id=user.id, provider="bailian",
                                api_key="sk-search123456", base_url="https://x.com")
            db.session.add(cfg)
            db.session.commit()

        resp = admin_login.get("/admin/user-llm?username=searchme")
        assert resp.status_code == 200
        assert b"searchme" in resp.data

    def test_admin_pagination(self, app, admin_login):
        with app.app_context():
            user = create_user("paguser", "pass123", eval_quota=5)
            from geo_optimizer.web.portal.models import UserLLMConfig
            from geo_optimizer.web.portal.extensions import db
            for i in range(15):
                cfg = UserLLMConfig(user_id=user.id, provider="bailian",
                                    api_key=f"sk-page{i}123456", base_url="https://x.com")
                db.session.add(cfg)
            db.session.commit()

        resp = admin_login.get("/admin/user-llm?per_page=10&page=1")
        assert resp.status_code == 200
        resp2 = admin_login.get("/admin/user-llm?per_page=10&page=2")
        assert resp2.status_code == 200

    def test_normal_user_forbidden(self, app, client):
        with app.app_context():
            create_user("normie", "pass123", eval_quota=5)
        client.post("/login", data={"username": "normie", "password": "pass123"})
        assert client.get("/admin/user-llm").status_code == 403


class TestPlatformLLMToggle:
    """管理侧设置用户是否可使用平台算力。"""

    def test_toggle_platform_llm(self, app, admin_login):
        with app.app_context():
            user = create_user("toggleuser", "pass123", eval_quota=5)
            user_id = user.id

        # 默认 can_use_platform_llm=True，关闭它
        resp = admin_login.post(f"/admin/users/{user_id}/quota", data={
            "eval_quota": "5",
            "role": "user",
            # 不传 can_use_platform_llm => off
        })
        assert resp.status_code == 302
        from geo_optimizer.web.portal.models import User
        with app.app_context():
            u = User.query.get(user_id)
            assert u.can_use_platform_llm is False

        # 重新开启
        admin_login.post(f"/admin/users/{user_id}/quota", data={
            "eval_quota": "5",
            "role": "user",
            "can_use_platform_llm": "on",
        })
        with app.app_context():
            u = User.query.get(user_id)
            assert u.can_use_platform_llm is True


class TestLLMPriority:
    """算力调用优先级：用户侧 > 平台侧。"""

    def test_user_config_takes_priority(self, app):
        with app.app_context():
            user = create_user("priouser", "pass123", eval_quota=5)
            from geo_optimizer.web.portal.models import SystemConfig, UserLLMConfig
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.tasks.config_builder import build_config

            # 平台配置
            SystemConfig.set("api_key", "sk-platform-key")
            SystemConfig.set("openai_base_url", "https://platform.example.com/v1")
            db.session.commit()

            # 用户配置
            cfg = UserLLMConfig(user_id=user.id, provider="token_plan",
                                api_key="sk-sp-user-key",
                                base_url="https://user.example.com/v1",
                                model="qwen-max", is_active=True)
            db.session.add(cfg)
            db.session.commit()

            config = build_config("https://test.com", "/tmp/out", user_id=user.id)
            assert config["llm"]["api_key"] == "sk-sp-user-key"
            assert config["llm"]["base_url"] == "https://user.example.com/v1"
            assert config["llm"]["model"] == "qwen-max"

    def test_fallback_to_platform(self, app):
        with app.app_context():
            user = create_user("fallbackuser", "pass123", eval_quota=5)
            from geo_optimizer.web.portal.models import SystemConfig
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.tasks.config_builder import build_config

            SystemConfig.set("api_key", "sk-platform-key")
            SystemConfig.set("openai_base_url", "https://platform.example.com/v1")
            db.session.commit()

            # 用户无自定义配置，回退到平台
            config = build_config("https://test.com", "/tmp/out", user_id=user.id)
            assert config["llm"]["api_key"] == "sk-platform-key"

    def test_user_has_available_llm(self, app):
        with app.app_context():
            user = create_user("availuser", "pass123", eval_quota=5)
            from geo_optimizer.web.portal.models import UserLLMConfig
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.tasks.config_builder import user_has_available_llm

            # 无用户配置 + 无平台权限 => 不可用
            assert user_has_available_llm(user.id, False) is False

            # 有用户配置 => 可用
            cfg = UserLLMConfig(user_id=user.id, provider="bailian",
                                api_key="sk-avail123456", is_active=True)
            db.session.add(cfg)
            db.session.commit()
            assert user_has_available_llm(user.id, False) is True
