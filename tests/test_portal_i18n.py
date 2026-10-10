# -*- coding: utf-8 -*-
"""portal i18n 中英切换测试。"""
from geo_optimizer.web.portal.i18n import (
    DEFAULT_LOCALE,
    SUPPORTED,
    set_locale,
    translate,
)
from geo_optimizer.web.portal.i18n.messages import MESSAGES


class TestTranslate:
    def test_default_locale_is_zh(self, app):
        with app.test_request_context("/"):
            assert translate("login") == "登录"

    def test_switch_to_en(self, app):
        with app.test_request_context("/"):
            set_locale("en")
            assert translate("login") == "Sign in"
            assert translate("app_name") == "GEO Optimizer"

    def test_invalid_locale_falls_back(self, app):
        with app.test_request_context("/"):
            set_locale("fr")
            assert translate("login") == "登录"  # 回退默认中文

    def test_missing_key_returns_key(self, app):
        with app.test_request_context("/"):
            assert translate("__no_such_key__") == "__no_such_key__"

    def test_all_messages_bilingual(self):
        """所有文案必须同时具备中英文。"""
        for key, entry in MESSAGES.items():
            assert set(SUPPORTED).issubset(entry.keys()), f"{key} 缺少语言"
            assert entry["zh"] and entry["en"], f"{key} 存在空文案"

    def test_lang_route_switch(self, admin_login):
        resp = admin_login.get("/lang/en")
        assert resp.status_code == 302
        page = admin_login.get("/")
        assert b"Dashboard" in page.data

        admin_login.get("/lang/zh")
        page = admin_login.get("/")
        assert "控制台".encode() in page.data

    def test_constants(self):
        assert DEFAULT_LOCALE == "zh"
        assert SUPPORTED == ("zh", "en")
