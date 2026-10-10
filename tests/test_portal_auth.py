# -*- coding: utf-8 -*-
"""portal 登录鉴权与权限测试。"""
from geo_optimizer.web.portal.auth.service import create_user


class TestLogin:
    def test_login_success(self, client):
        resp = client.post("/login", data={"username": "admin", "password": "admin123"})
        assert resp.status_code == 302
        # 管理员登录默认落地后台用户列表
        assert resp.headers["Location"].endswith("/admin/users")

    def test_login_normal_user_lands_dashboard(self, app, client):
        with app.app_context():
            create_user("landuser", "pass123", eval_quota=5)
        resp = client.post("/login", data={"username": "landuser", "password": "pass123"})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/dashboard")

    def test_login_wrong_password(self, client):
        resp = client.post("/login", data={"username": "admin", "password": "nope"})
        assert resp.status_code == 200  # 停留在登录页

    def test_anonymous_sees_landing(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.data.decode()
        # 公开首页包含资源模块与登录/注册入口
        assert "/login" in html
        assert "/register" in html
        assert "/geo-skill" in html
        assert "/user-guide" in html
        assert "faq" in html.lower()

    def test_anonymous_dashboard_redirected(self, client):
        resp = client.get("/dashboard")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_logout(self, admin_login):
        resp = admin_login.post("/logout")
        assert resp.status_code == 302
        # 退出后回到平台首页
        assert resp.headers["Location"].rstrip("/").endswith("localhost") or resp.headers["Location"] == "/"


class TestPermissions:
    def test_admin_can_access_config(self, admin_login):
        assert admin_login.get("/admin/config").status_code == 200

    def test_normal_user_forbidden_admin(self, app, client):
        with app.app_context():
            create_user("normal1", "pass123", eval_quota=2)
        client.post("/login", data={"username": "normal1", "password": "pass123"})
        assert client.get("/admin/config").status_code == 403
        assert client.get("/admin/users").status_code == 403
        assert client.get("/admin/audit").status_code == 403

    def test_normal_user_dashboard_ok(self, app, client):
        with app.app_context():
            create_user("normal2", "pass123", eval_quota=2)
        client.post("/login", data={"username": "normal2", "password": "pass123"})
        assert client.get("/").status_code == 200
        assert client.get("/eval/new").status_code == 200

    def test_admin_create_user_via_page(self, app, admin_login):
        resp = admin_login.post("/admin/users", data={
            "username": "newbie", "password": "pw12345",
            "role": "user", "eval_quota": "5",
        })
        assert resp.status_code == 302
        from geo_optimizer.web.portal.models import User
        with app.app_context():
            user = User.query.filter_by(username="newbie").first()
            assert user is not None
            assert user.eval_quota == 5
