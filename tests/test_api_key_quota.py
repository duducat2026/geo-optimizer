# -*- coding: utf-8 -*-
"""API 密钥每日调用额度与调用统计测试。"""
from datetime import date, datetime, timedelta

import pytest

from geo_optimizer.web.portal.api.auth import generate_api_key
from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models import ApiKey, User


@pytest.fixture()
def admin_key(app, client):
    """为管理员创建一个密钥，登录会话保留，返回 (明文key, key_id)。"""
    client.post("/login", data={"username": "admin", "password": "admin123"})
    with app.app_context():
        user = User.query.filter_by(username="admin").first()
        _, raw_key = generate_api_key(user.id, name="quota-key", expires_days=365)
        key = ApiKey.query.filter_by(user_id=user.id).order_by(ApiKey.id.desc()).first()
        key_id = key.id
    return raw_key, key_id


def _headers(raw_key):
    return {"Authorization": f"Bearer {raw_key}"}


# ─── 模型默认值与属性 ────────────────────────────────────────────────────────


class TestQuotaModel:
    def test_default_daily_quota_is_50(self, app, client, admin_key):
        raw_key, key_id = admin_key
        with app.app_context():
            key = db.session.get(ApiKey, key_id)
            assert key.daily_quota == 50
            assert key.used_today == 0
            assert key.quota_left == 50

    def test_used_today_resets_across_days(self, app, client, admin_key):
        raw_key, key_id = admin_key
        with app.app_context():
            key = db.session.get(ApiKey, key_id)
            key.calls_today = 30
            key.quota_date = date.today() - timedelta(days=1)  # 昨天
            db.session.commit()
            key = db.session.get(ApiKey, key_id)
            assert key.used_today == 0
            assert key.quota_left == key.daily_quota

    def test_quota_left_zero_means_unlimited(self, app, client, admin_key):
        raw_key, key_id = admin_key
        with app.app_context():
            key = db.session.get(ApiKey, key_id)
            key.daily_quota = 0
            db.session.commit()
            key = db.session.get(ApiKey, key_id)
            assert key.quota_left > 10 ** 6


# ─── 开放 API 限额拦截 ───────────────────────────────────────────────────────


class TestQuotaEnforcement:
    def test_counts_each_call(self, app, client, admin_key):
        raw_key, key_id = admin_key
        for _ in range(3):
            resp = client.get("/api/v1/usage", headers=_headers(raw_key))
            assert resp.status_code == 200
        with app.app_context():
            key = db.session.get(ApiKey, key_id)
            assert key.used_today == 3
            assert key.total_calls == 3

    def test_blocks_over_quota(self, app, client, admin_key):
        raw_key, key_id = admin_key
        with app.app_context():
            key = db.session.get(ApiKey, key_id)
            key.daily_quota = 2
            db.session.commit()

        assert client.get("/api/v1/usage", headers=_headers(raw_key)).status_code == 200
        assert client.get("/api/v1/usage", headers=_headers(raw_key)).status_code == 200
        resp = client.get("/api/v1/usage", headers=_headers(raw_key))
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "quota_exceeded"

    def test_unlimited_allows_many(self, app, client, admin_key):
        raw_key, key_id = admin_key
        with app.app_context():
            key = db.session.get(ApiKey, key_id)
            key.daily_quota = 0
            db.session.commit()
        for _ in range(6):
            assert client.get("/api/v1/usage", headers=_headers(raw_key)).status_code == 200

    def test_usage_reports_current_key_quota(self, client, admin_key):
        raw_key, key_id = admin_key
        client.get("/api/v1/usage", headers=_headers(raw_key))
        data = client.get("/api/v1/usage", headers=_headers(raw_key)).get_json()
        assert "current_key" in data
        assert data["current_key"]["daily_quota"] == 50
        assert data["current_key"]["used_today"] == 2


# ─── 用户侧调用统计页 ────────────────────────────────────────────────────────


class TestStatsPage:
    def test_stats_page_renders_daily_table(self, client, admin_key):
        raw_key, key_id = admin_key
        client.get("/api/v1/usage", headers=_headers(raw_key))
        resp = client.get(f"/api-keys/{key_id}/logs")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        # 统计页标题 + 按天统计区块
        assert "调用统计" in html
        assert "按天调用统计" in html

    def test_stats_date_filter(self, client, admin_key):
        raw_key, key_id = admin_key
        client.get("/api/v1/usage", headers=_headers(raw_key))
        today = date.today().isoformat()
        # 以 UTC 记录，日期过滤应命中当日明细
        resp = client.get(f"/api-keys/{key_id}/logs?date={today}")
        assert resp.status_code == 200


# ─── 管理后台额度维护 ────────────────────────────────────────────────────────


class TestAdminQuota:
    def test_admin_list_page(self, client, admin_key):
        resp = client.get("/admin/api-keys")
        assert resp.status_code == 200
        assert "API 密钥额度管理" in resp.get_data(as_text=True)

    def test_admin_update_quota(self, app, client, admin_key):
        raw_key, key_id = admin_key
        resp = client.post(f"/admin/api-keys/{key_id}/quota",
                           data={"daily_quota": "100"})
        assert resp.status_code in (200, 302)
        with app.app_context():
            key = db.session.get(ApiKey, key_id)
            assert key.daily_quota == 100

    def test_admin_update_quota_negative_clamped(self, app, client, admin_key):
        raw_key, key_id = admin_key
        client.post(f"/admin/api-keys/{key_id}/quota", data={"daily_quota": "-5"})
        with app.app_context():
            key = db.session.get(ApiKey, key_id)
            assert key.daily_quota == 0
