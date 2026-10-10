# -*- coding: utf-8 -*-
"""后台用户管理（翻页/编辑/禁用/删除/新建浮层）与操作审计（翻页/批量删除）、配额按天重置测试。"""
from datetime import date, timedelta

from geo_optimizer.web.portal.auth.service import create_user


class TestAdminIndex:
    def test_admin_root_redirects_to_users(self, admin_login):
        resp = admin_login.get("/admin/")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/admin/users")


class TestUsersPage:
    def test_pagination(self, app, admin_login):
        with app.app_context():
            for i in range(12):
                create_user(f"pageuser{i}", "pass123", eval_quota=5)
        html = admin_login.get("/admin/users?per_page=10").data.decode()
        assert "1 / 2" in html
        html2 = admin_login.get("/admin/users?page=2&per_page=10").data.decode()
        assert "2 / 2" in html2

    def test_new_user_modal_markup(self, admin_login):
        html = admin_login.get("/admin/users").data.decode()
        # 新建用户浮层骨架与触发按钮
        assert 'id="user-modal"' in html
        assert "openUserModal()" in html
        assert 'name="user_id"' in html

    def test_edit_user_info(self, app, admin_login):
        with app.app_context():
            uid = create_user("edituser", "pass123", eval_quota=5).id
        resp = admin_login.post("/admin/users", data={
            "user_id": str(uid), "email": "e@x.com", "phone": "13800001111",
            "role": "user", "eval_quota": "20", "can_use_platform_llm": "on",
            "password": "",
        })
        assert resp.status_code == 302
        with app.app_context():
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.models import User
            user = db.session.get(User, uid)
            assert user.email == "e@x.com"
            assert user.phone == "13800001111"
            assert user.eval_quota == 20
            assert user.can_use_platform_llm is True
            # 密码留空不修改
            assert user.check_password("pass123")

    def test_edit_user_change_password(self, app, admin_login):
        with app.app_context():
            uid = create_user("pwduser", "pass123", eval_quota=5).id
        admin_login.post("/admin/users", data={
            "user_id": str(uid), "email": "", "phone": "",
            "role": "user", "eval_quota": "5", "password": "newpw123",
        })
        with app.app_context():
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.models import User
            user = db.session.get(User, uid)
            assert user.check_password("newpw123")

    def test_disable_and_enable(self, app, admin_login):
        with app.app_context():
            uid = create_user("toggleme", "pass123", eval_quota=5).id
        admin_login.post(f"/admin/users/{uid}/toggle-active")
        with app.app_context():
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.models import User
            assert db.session.get(User, uid).is_active is False
        # 禁用后无法登录
        fresh = app.test_client()
        resp = fresh.post("/login", data={"username": "toggleme", "password": "pass123"})
        assert resp.status_code == 200  # 停留在登录页
        # 再次切换恢复启用
        admin_login.post(f"/admin/users/{uid}/toggle-active")
        with app.app_context():
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.models import User
            assert db.session.get(User, uid).is_active is True

    def test_delete_user_cascades(self, app, admin_login):
        from geo_optimizer.web.portal.tasks import service
        with app.app_context():
            uid = create_user("deleteme", "pass123", eval_quota=5).id
            task_id = service.create_task(uid, "https://del.example.com", "eval").id
        resp = admin_login.post(f"/admin/users/{uid}/delete")
        assert resp.status_code == 302
        with app.app_context():
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.models import EvalTask, User
            assert db.session.get(User, uid) is None
            assert db.session.get(EvalTask, task_id) is None

    def test_cannot_operate_self(self, app, admin_login):
        with app.app_context():
            from geo_optimizer.web.portal.models import User
            admin_id = User.query.filter_by(username="admin").first().id
        admin_login.post(f"/admin/users/{admin_id}/toggle-active")
        admin_login.post(f"/admin/users/{admin_id}/delete")
        with app.app_context():
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.models import User
            admin = db.session.get(User, admin_id)
            assert admin is not None
            assert admin.is_active is True


class TestAuditPage:
    def _seed_logs(self, app, count=15):
        with app.app_context():
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.models import AuditLog
            for i in range(count):
                db.session.add(AuditLog(username="seeder", action="login",
                                        target=f"t{i}", ip="127.0.0.1", detail=""))
            db.session.commit()
            return [log.id for log in AuditLog.query.filter_by(username="seeder").all()]

    def test_pagination(self, app, admin_login):
        self._seed_logs(app, 15)
        html = admin_login.get("/admin/audit?per_page=10").data.decode()
        assert "audit-check" in html
        assert "/ 2" in html
        html2 = admin_login.get("/admin/audit?page=2&per_page=10").data.decode()
        assert "2 /" in html2

    def test_batch_delete(self, app, admin_login):
        log_ids = self._seed_logs(app, 5)
        resp = admin_login.post("/admin/audit/batch-delete",
                                data={"log_ids": [str(i) for i in log_ids[:3]]})
        assert resp.status_code == 302
        with app.app_context():
            from geo_optimizer.web.portal.models import AuditLog
            remain = AuditLog.query.filter(AuditLog.id.in_(log_ids)).count()
            assert remain == 2

    def test_batch_delete_empty_ok(self, admin_login):
        resp = admin_login.post("/admin/audit/batch-delete", data={})
        assert resp.status_code == 302
        assert "/admin/audit" in resp.headers["Location"]

    def test_batch_delete_forbidden_for_user(self, app, client):
        with app.app_context():
            create_user("auditnormal", "pass123", eval_quota=5)
        client.post("/login", data={"username": "auditnormal", "password": "pass123"})
        assert client.post("/admin/audit/batch-delete", data={}).status_code == 403


class TestDailyQuota:
    def test_register_default_quota_10(self, app):
        from geo_optimizer.web.portal.auth.service import register_user
        with app.app_context():
            user = register_user("quotareg", "pass123", "q@x.com", "13800000000")
            assert user.eval_quota == 10

    def test_used_today_resets_across_days(self, app):
        with app.app_context():
            from geo_optimizer.web.portal.extensions import db
            user = create_user("dayuser", "pass123", eval_quota=3)
            user.eval_used = 3
            user.quota_date = date.today() - timedelta(days=1)
            db.session.commit()
            # 昨日用满，今日视为 0，配额恢复
            assert user.used_today == 0
            assert user.quota_left == 3

    def test_reserve_quota_resets_on_new_day(self, app):
        from geo_optimizer.web.portal.tasks import service
        with app.app_context():
            from geo_optimizer.web.portal.extensions import db
            user = create_user("reserveuser", "pass123", eval_quota=3)
            user.eval_used = 3
            user.quota_date = date.today() - timedelta(days=1)
            db.session.commit()
            service.reserve_quota(user.id)
            assert user.quota_date == date.today()
            assert user.eval_used == 1
            assert user.used_today == 1

    def test_refund_quota_only_same_day(self, app):
        from geo_optimizer.web.portal.tasks import service
        with app.app_context():
            from geo_optimizer.web.portal.extensions import db
            user = create_user("refunduser", "pass123", eval_quota=3)
            service.reserve_quota(user.id)
            assert user.eval_used == 1
            service.refund_quota(user.id)
            assert user.eval_used == 0
            # 昨日计数不予归还
            user.eval_used = 2
            user.quota_date = date.today() - timedelta(days=1)
            db.session.commit()
            service.refund_quota(user.id)
            assert user.eval_used == 2
