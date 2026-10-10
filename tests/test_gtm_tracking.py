# -*- coding: utf-8 -*-
"""全站流量监测（GTM 容器）注入覆盖测试。

页面只挂 GTM 容器（容器 ID 由配置项 GTM_CONTAINER 注入），
GA4 衡量 ID 全部由容器内标签投放；snippet 必须含 gtm.start push。"""
import re


CONTAINER = "GTM-XXXXXXX"
HEAD_MARK = b"googletagmanager.com/gtm.js?id="
PUSH_MARK = b"{'gtm.start'"
NOS_MARK = b"ns.html?id=" + CONTAINER.encode()

# 公开页（独立模板）+ 登录后页（继承 base.html）
PUBLIC_PAGES = ["/", "/login", "/register", "/user-guide"]
LOGIN_PAGES = ["/dashboard", "/guide", "/api-docs", "/history",
               "/admin/config", "/admin/users"]


def _assert_gtm(html: bytes):
    """容器 snippet 在场、含 gtm.start push、位置符合 head/body 规范。"""
    assert CONTAINER.encode() in html, "缺少 GTM 容器 ID"
    assert HEAD_MARK in html, "缺少 gtm.js 加载脚本"
    assert PUSH_MARK in html, "缺少 gtm.start push（延迟注入历史教训）"
    assert NOS_MARK in html, "缺少 noscript iframe 回退"
    # head 内：应在 <meta charset> 之后
    assert html.find(b"<meta charset") < html.find(HEAD_MARK)
    # body 内：noscript 应在 <body> 之后
    assert html.find(b"<body>") < html.find(NOS_MARK)


class TestGtmPublicPages:
    def test_public_pages_carry_container(self, client):
        for path in PUBLIC_PAGES:
            resp = client.get(path)
            assert resp.status_code == 200, path
            _assert_gtm(resp.data)


class TestGtmLoginPages:
    def test_login_pages_carry_container(self, admin_login):
        for path in LOGIN_PAGES:
            resp = admin_login.get(path)
            assert resp.status_code == 200, path
            _assert_gtm(resp.data)


class TestGtmNoHardcodedMeasurementId:
    def test_pages_do_not_embed_ga4_id(self, client):
        """页面不得直挂 GA4 衡量 ID（ID 由容器统一管理，避免双重计数）。"""
        html = client.get("/").data
        assert b"googletagmanager.com/gtag/js" not in html  # 无 gtag.js 直挂
        assert not re.search(rb"G-[A-Z0-9]{7,10}", html)  # 无硬编码衡量 ID
