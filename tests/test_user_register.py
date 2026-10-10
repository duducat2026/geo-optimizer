# -*- coding: utf-8 -*-
"""用户注册与审批激活测试。"""
import hashlib

from geo_optimizer.web.portal.models import STATUS_ACTIVE, STATUS_PENDING, User
from geo_optimizer.web.portal.models.user import PASSWORD_MD5_KEY

REG_DATA = {
    "username": "reg_user",
    "password": "pw12345",
    "password2": "pw12345",
    "email": "reg@example.com",
    "phone": "13800001111",
}


def _register(client, **overrides):
    data = dict(REG_DATA)
    data.update(overrides)
    return client.post("/register", data=data)


class TestRegisterPage:
    def test_register_page_renders(self, client):
        resp = client.get("/register")
        assert resp.status_code == 200
        html = resp.data.decode()
        # 必填字段与明文查看按钮均渲染
        assert 'name="username"' in html
        assert 'name="password"' in html
        assert 'name="password2"' in html
        assert 'name="email"' in html
        assert 'name="phone"' in html
        assert "togglePwd" in html

    def test_login_page_has_register_link(self, client):
        html = client.get("/login").data.decode()
        assert "/register" in html


class TestRegisterSubmit:
    def test_register_creates_pending_user_with_md5(self, app, client):
        resp = _register(client)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]
        with app.app_context():
            user = User.query.filter_by(username="reg_user").first()
            assert user is not None
            assert user.status == STATUS_PENDING
            assert user.email == "reg@example.com"
            assert user.phone == "13800001111"
            # 密码 MD5+固定密钥存储
            digest = hashlib.md5(("pw12345" + PASSWORD_MD5_KEY).encode()).hexdigest()
            assert user.password_hash == "md5$" + digest
            assert user.check_password("pw12345")
            assert not user.check_password("wrong")

    def test_duplicate_username_rejected(self, app, client):
        _register(client)
        resp = _register(client, email="another@example.com")
        assert resp.status_code == 200  # 停留在注册页
        with app.app_context():
            assert User.query.filter_by(username="reg_user").count() == 1

    def test_password_mismatch_rejected(self, app, client):
        resp = _register(client, username="reg_mismatch", password2="other")
        assert resp.status_code == 200
        with app.app_context():
            assert User.query.filter_by(username="reg_mismatch").first() is None

    def test_email_and_phone_required(self, app, client):
        for missing in ("email", "phone"):
            resp = _register(client, username=f"reg_no_{missing}", **{missing: ""})
            assert resp.status_code == 200
            with app.app_context():
                assert User.query.filter_by(
                    username=f"reg_no_{missing}").first() is None


class TestApprovalFlow:
    def test_pending_user_login_blocked_with_hint(self, app, client):
        _register(client)
        resp = client.post("/login", data={
            "username": "reg_user", "password": "pw12345",
        })
        assert resp.status_code == 200  # 未登录成功，停留在登录页
        assert "审批" in resp.data.decode()

    def test_admin_sees_pending_and_approve_button(self, app, admin_login):
        # admin_login 与 client 是同一会话，注册需用独立未登录 client
        _register(app.test_client())
        html = admin_login.get("/admin/users").data.decode()
        assert "reg_user" in html
        assert "reg@example.com" in html
        assert "13800001111" in html
        assert "/approve" in html

    def test_approve_then_login_success(self, app, admin_login):
        _register(app.test_client())
        with app.app_context():
            user = User.query.filter_by(username="reg_user").first()
            uid = user.id
        resp = admin_login.post(f"/admin/users/{uid}/approve")
        assert resp.status_code == 302
        with app.app_context():
            assert User.query.filter_by(username="reg_user").first().status == STATUS_ACTIVE
        # 审批后可登录（换个新 client 避免 admin 会话）
        fresh = app.test_client()
        resp = fresh.post("/login", data={
            "username": "reg_user", "password": "pw12345",
        })
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/dashboard")

    def test_admin_created_user_active_by_default(self, app, admin_login):
        admin_login.post("/admin/users", data={
            "username": "backoffice", "password": "pw12345",
            "role": "user", "eval_quota": "5",
        })
        with app.app_context():
            user = User.query.filter_by(username="backoffice").first()
            assert user.status == STATUS_ACTIVE
        fresh = app.test_client()
        resp = fresh.post("/login", data={
            "username": "backoffice", "password": "pw12345",
        })
        assert resp.status_code == 302
