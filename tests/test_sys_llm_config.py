# -*- coding: utf-8 -*-
"""平台侧算力方案（SystemLLMConfig）功能测试：CRUD、启用互斥、调用测试浮层、算力优先级。"""
from geo_optimizer.web.portal.auth.service import create_user


def _create_plan(client, name="平台百炼", api_key="sk-sys1234567890", provider="bailian",
                 base_url="", model="qwen-plus"):
    return client.post("/admin/llm-configs/save", data={
        "id": "0", "provider": provider, "name": name,
        "api_key": api_key, "base_url": base_url, "model": model,
    })


class TestSysLLMConfigPage:
    """系统配置页的算力方案区块与浮层骨架。"""

    def test_page_shows_plan_section_and_modal(self, admin_login):
        resp = admin_login.get("/admin/config")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        # 方案新增表单与测试浮层骨架
        assert "/admin/llm-configs/save" in html
        assert 'id="test-modal"' in html
        assert "showTestModal" in html

    def test_legacy_hint_when_no_plan(self, app, admin_login):
        with app.app_context():
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.models import SystemConfig
            SystemConfig.set("api_key", "sk-legacy-key-123456")
            db.session.commit()
        html = admin_login.get("/admin/config").data.decode("utf-8")
        # 旧版单键配置生效提示（脱敏展示）
        assert "sk-leg" in html
        assert "sk-legacy-key-123456" not in html

    def test_plan_listed_after_create(self, app, admin_login):
        _create_plan(admin_login, name="列表校验")
        html = admin_login.get("/admin/config").data.decode("utf-8")
        assert "列表校验" in html
        assert "llm-test-form" in html
        # 编辑按钮携带回填数据
        assert "editPlan" in html
        # API Key 脱敏，不出现明文
        assert "sk-sys1234567890" not in html

    def test_non_admin_forbidden(self, app, client):
        with app.app_context():
            create_user("sysllm_normal", "pass123", eval_quota=5)
        client.post("/login", data={"username": "sysllm_normal", "password": "pass123"})
        assert _create_plan(client).status_code == 403
        assert client.post("/admin/llm-configs/1/activate").status_code == 403
        assert client.post("/admin/llm-configs/1/delete").status_code == 403
        assert client.post("/admin/llm-configs/1/test").status_code == 403


class TestSysLLMConfigCRUD:
    """方案新建、启用互斥、删除。"""

    def test_first_plan_auto_active(self, app, admin_login):
        assert _create_plan(admin_login).status_code == 302
        from geo_optimizer.web.portal.models import SystemLLMConfig
        with app.app_context():
            cfg = SystemLLMConfig.query.first()
            assert cfg is not None
            assert cfg.is_active is True
            # 非自定义方案自动填充 base_url
            assert "dashscope" in cfg.base_url

    def test_second_plan_not_active(self, app, admin_login):
        _create_plan(admin_login, name="一号")
        _create_plan(admin_login, name="二号", api_key="sk-sp-9876543210",
                     provider="token_plan")
        from geo_optimizer.web.portal.models import SystemLLMConfig
        with app.app_context():
            actives = SystemLLMConfig.query.filter_by(is_active=True).all()
            assert len(actives) == 1
            assert actives[0].name == "一号"
            second = SystemLLMConfig.query.filter_by(name="二号").first()
            assert second.is_active is False
            assert "token-plan" in second.base_url

    def test_api_key_required(self, app, admin_login):
        _create_plan(admin_login, api_key="")
        from geo_optimizer.web.portal.models import SystemLLMConfig
        with app.app_context():
            assert SystemLLMConfig.query.count() == 0

    def test_edit_provider_and_name(self, app, admin_login):
        """编辑方案：修改方案类型与备注名，API Key 留空保留原 Key。"""
        _create_plan(admin_login, name="原名", api_key="sk-origin1234567")
        from geo_optimizer.web.portal.models import SystemLLMConfig
        with app.app_context():
            cfg_id = SystemLLMConfig.query.first().id
        resp = admin_login.post("/admin/llm-configs/save", data={
            "id": str(cfg_id), "provider": "token_plan", "name": "新备注",
            "api_key": "", "base_url": "", "model": "qwen-max",
        })
        assert resp.status_code == 302
        with app.app_context():
            cfg = SystemLLMConfig.query.first()
            assert cfg.provider == "token_plan"
            assert cfg.name == "新备注"
            assert cfg.model == "qwen-max"
            # API Key 留空时保留原 Key
            assert cfg.api_key == "sk-origin1234567"
            # 切换方案类型后 base_url 自动填充为新预设
            assert "token-plan" in cfg.base_url

    def test_edit_replaces_api_key_when_provided(self, app, admin_login):
        _create_plan(admin_login, name="换钥", api_key="sk-oldkey12345678")
        from geo_optimizer.web.portal.models import SystemLLMConfig
        with app.app_context():
            cfg_id = SystemLLMConfig.query.first().id
        admin_login.post("/admin/llm-configs/save", data={
            "id": str(cfg_id), "provider": "bailian", "name": "换钥",
            "api_key": "sk-newkey87654321", "base_url": "", "model": "",
        })
        with app.app_context():
            assert SystemLLMConfig.query.first().api_key == "sk-newkey87654321"

    def test_edit_keeps_active_flag(self, app, admin_login):
        """编辑不改变启用状态。"""
        _create_plan(admin_login, name="启用中")
        from geo_optimizer.web.portal.models import SystemLLMConfig
        with app.app_context():
            cfg_id = SystemLLMConfig.query.first().id
        admin_login.post("/admin/llm-configs/save", data={
            "id": str(cfg_id), "provider": "bailian", "name": "改名后",
            "api_key": "", "base_url": "", "model": "",
        })
        with app.app_context():
            cfg = SystemLLMConfig.query.first()
            assert cfg.name == "改名后"
            assert cfg.is_active is True

    def test_edit_nonexistent_plan(self, app, admin_login):
        resp = admin_login.post("/admin/llm-configs/save", data={
            "id": "9999", "provider": "bailian", "name": "幽灵",
            "api_key": "", "base_url": "", "model": "",
        })
        assert resp.status_code == 302
        from geo_optimizer.web.portal.models import SystemLLMConfig
        with app.app_context():
            assert SystemLLMConfig.query.count() == 0

    def test_activate_mutual_exclusive(self, app, admin_login):
        _create_plan(admin_login, name="一号")
        _create_plan(admin_login, name="二号", api_key="sk-second1234567")
        from geo_optimizer.web.portal.models import SystemLLMConfig
        with app.app_context():
            second_id = SystemLLMConfig.query.filter_by(name="二号").first().id
        admin_login.post(f"/admin/llm-configs/{second_id}/activate")
        with app.app_context():
            actives = SystemLLMConfig.query.filter_by(is_active=True).all()
            assert len(actives) == 1
            assert actives[0].name == "二号"

    def test_delete_plan(self, app, admin_login):
        _create_plan(admin_login, name="待删")
        from geo_optimizer.web.portal.models import SystemLLMConfig
        with app.app_context():
            cfg_id = SystemLLMConfig.query.first().id
        admin_login.post(f"/admin/llm-configs/{cfg_id}/delete")
        with app.app_context():
            assert SystemLLMConfig.query.count() == 0


class TestSysLLMTest:
    """方案调用测试：AJAX 返回 JSON 供浮层展示，无 JS 回退 flash。"""

    def _plan_id(self, app, admin_login):
        _create_plan(admin_login, name="测试方案")
        from geo_optimizer.web.portal.models import SystemLLMConfig
        with app.app_context():
            return SystemLLMConfig.query.first().id

    def test_ajax_returns_json_for_modal(self, app, admin_login, monkeypatch):
        cfg_id = self._plan_id(app, admin_login)
        from geo_optimizer.web.portal.admin import routes as admin_routes
        monkeypatch.setattr(
            admin_routes, "_test_llm_connection",
            lambda k, u, m: (True, {
                "endpoint": u, "model_requested": m, "model_responded": "m-sys",
                "elapsed_ms": 66, "usage": {"prompt": 3, "completion": 2, "total": 5},
                "reply": "hey", "error": "",
            }),
        )
        resp = admin_login.post(f"/admin/llm-configs/{cfg_id}/test",
                                headers={"X-Requested-With": "fetch"})
        assert resp.status_code == 200
        assert resp.is_json
        data = resp.get_json()
        assert data["ok"] is True
        assert data["model_responded"] == "m-sys"
        assert data["config_name"] == "测试方案"
        assert "****" in data["api_key_masked"]

    def test_ajax_failure_returns_error_json(self, app, admin_login, monkeypatch):
        cfg_id = self._plan_id(app, admin_login)
        from geo_optimizer.web.portal.admin import routes as admin_routes
        monkeypatch.setattr(
            admin_routes, "_test_llm_connection",
            lambda k, u, m: (False, {
                "endpoint": u, "model_requested": m, "model_responded": "",
                "elapsed_ms": 15000, "usage": None, "reply": "",
                "error": "Error code: 401 - invalid api key",
            }),
        )
        resp = admin_login.post(f"/admin/llm-configs/{cfg_id}/test",
                                headers={"X-Requested-With": "fetch"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is False
        assert "invalid api key" in data["error"]

    def test_no_js_fallback_flash(self, app, admin_login, monkeypatch):
        cfg_id = self._plan_id(app, admin_login)
        from geo_optimizer.web.portal.admin import routes as admin_routes
        monkeypatch.setattr(
            admin_routes, "_test_llm_connection",
            lambda k, u, m: (True, {
                "endpoint": u, "model_requested": m, "model_responded": "m-fb",
                "elapsed_ms": 80, "usage": None, "reply": "ok", "error": "",
            }),
        )
        resp = admin_login.post(f"/admin/llm-configs/{cfg_id}/test",
                                follow_redirects=True)
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "连接成功" in html
        assert "m-fb" in html

    def test_not_found_returns_404_json(self, admin_login):
        resp = admin_login.post("/admin/llm-configs/9999/test",
                                headers={"X-Requested-With": "fetch"})
        assert resp.status_code == 404


class TestSysLLMPriority:
    """平台算力选择：启用方案优先，旧版单键配置回退。"""

    def test_active_plan_over_legacy(self, app):
        with app.app_context():
            user = create_user("sysprio_user", "pass123", eval_quota=5)
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.models import SystemConfig, SystemLLMConfig
            from geo_optimizer.web.portal.tasks.config_builder import build_config

            SystemConfig.set("api_key", "sk-legacy-key")
            SystemConfig.set("openai_base_url", "https://legacy.example.com/v1")
            plan = SystemLLMConfig(provider="token_plan", name="平台方案",
                                   api_key="sk-sp-plan-key",
                                   base_url="https://plan.example.com/v1",
                                   model="qwen-max", is_active=True)
            db.session.add(plan)
            db.session.commit()

            config = build_config("https://test.com", "/tmp/out", user_id=user.id)
            assert config["llm"]["api_key"] == "sk-sp-plan-key"
            assert config["llm"]["base_url"] == "https://plan.example.com/v1"
            assert config["llm"]["model"] == "qwen-max"

    def test_plan_without_base_url_uses_preset(self, app):
        with app.app_context():
            user = create_user("sysprio_user2", "pass123", eval_quota=5)
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.models import SystemLLMConfig
            from geo_optimizer.web.portal.tasks.config_builder import build_config

            plan = SystemLLMConfig(provider="bailian", api_key="sk-plan-nourlkey",
                                   base_url="", model="", is_active=True)
            db.session.add(plan)
            db.session.commit()

            config = build_config("https://test.com", "/tmp/out", user_id=user.id)
            assert config["llm"]["api_key"] == "sk-plan-nourlkey"
            assert "dashscope" in config["llm"]["base_url"]

    def test_fallback_to_legacy_when_no_plan(self, app):
        with app.app_context():
            user = create_user("sysprio_user3", "pass123", eval_quota=5)
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.models import SystemConfig
            from geo_optimizer.web.portal.tasks.config_builder import build_config

            SystemConfig.set("api_key", "sk-legacy-only")
            SystemConfig.set("openai_base_url", "https://legacy.example.com/v1")
            db.session.commit()

            config = build_config("https://test.com", "/tmp/out", user_id=user.id)
            assert config["llm"]["api_key"] == "sk-legacy-only"

    def test_user_has_available_llm_with_plan(self, app):
        with app.app_context():
            user = create_user("sysavail_user", "pass123", eval_quota=5)
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.models import SystemConfig, SystemLLMConfig
            from geo_optimizer.web.portal.tasks.config_builder import user_has_available_llm

            # 清空旧版单键配置，仅保留启用方案
            SystemConfig.set("api_key", "")
            plan = SystemLLMConfig(provider="bailian", api_key="sk-plan-avail123",
                                   is_active=True)
            db.session.add(plan)
            db.session.commit()
            assert user_has_available_llm(user.id, True) is True
