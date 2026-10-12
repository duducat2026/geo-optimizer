# -*- coding: utf-8 -*-
"""优化指导页渲染测试（zh/en）。"""
from geo_optimizer.web.portal.guide import guide_data


class TestGuideData:
    def test_portals_bilingual(self):
        assert len(guide_data.PORTALS) >= 5
        for row in guide_data.PORTALS:
            assert row["platform"]
            assert row["note"]["zh"] and row["note"]["en"]

    def test_cn_models_complete(self):
        assert len(guide_data.CN_MODELS) == 4
        for card in guide_data.CN_MODELS:
            assert card["name"] and card["actions"]

    def test_checklist_levels(self):
        levels = {row["level"] for row in guide_data.CHECKLIST}
        assert levels <= {"high", "mid", "low"}


class TestGuidePage:
    def test_requires_login(self, client):
        resp = client.get("/guide")
        assert resp.status_code == 302  # 跳转登录

    def test_render_zh(self, admin_login):
        resp = admin_login.get("/guide")
        assert resp.status_code == 200
        assert "提交入口".encode() in resp.data
        assert b"robots.txt" in resp.data

    def test_render_en(self, admin_login):
        admin_login.get("/lang/en")
        resp = admin_login.get("/guide")
        assert resp.status_code == 200
        assert b"Submission" in resp.data


class TestUserGuideRaw:
    """使用指南原始 Markdown 下载（中英双版，免登录）。"""

    def test_zh_guide_downloadable(self, client):
        resp = client.get("/user-guide.md")
        assert resp.status_code == 200
        assert "markdown" in resp.content_type

    def test_en_guide_downloadable(self, client):
        resp = client.get("/user-guide.en.md")
        assert resp.status_code == 200
        assert "markdown" in resp.content_type
        assert b"# GEO-Optimizer User Guide" in resp.data
