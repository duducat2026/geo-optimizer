# -*- coding: utf-8 -*-
"""站点总览测试：翻页（10/20/50）与管理端删除任务及关联记录。"""
from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models import EvalTask, PlanItem, TaskLog, User
from geo_optimizer.web.portal.tasks import service


def _seed_tasks(app, count: int) -> list:
    with app.app_context():
        uid = User.query.filter_by(username="admin").first().id
        return [service.create_task(uid, f"https://s{i}.com", "eval").id
                for i in range(count)]


class TestSitesPagination:
    def test_dashboard_recent_limited_to_5(self, app, admin_login):
        _seed_tasks(app, 8)
        html = admin_login.get("/").data.decode()
        # 控制台总体概览仅展示最近 5 条，附查看全部链接
        assert html.count("/eval/") == 5
        assert "/admin/sites" in html
        assert "总体概览" in html

    def test_default_10_per_page(self, app, admin_login):
        _seed_tasks(app, 15)
        resp = admin_login.get("/admin/sites")
        assert resp.status_code == 200
        html = resp.data.decode()
        # 默认每页 10 条：第 1 页不含最早创建的任务
        assert html.count("btn-danger") == 10
        assert "1 / 2" in html

    def test_per_page_choices(self, app, admin_login):
        _seed_tasks(app, 25)
        for per_page, expect in ((10, 10), (20, 20), (50, 25)):
            html = admin_login.get(f"/admin/sites?per_page={per_page}").data.decode()
            assert html.count("btn-danger") == expect

    def test_invalid_per_page_falls_back(self, app, admin_login):
        _seed_tasks(app, 12)
        html = admin_login.get("/admin/sites?per_page=999").data.decode()
        assert html.count("btn-danger") == 10

    def test_page_out_of_range_clamped(self, app, admin_login):
        _seed_tasks(app, 5)
        resp = admin_login.get("/admin/sites?page=99")
        assert resp.status_code == 200
        assert "1 / 1" in resp.data.decode()

    def test_second_page(self, app, admin_login):
        _seed_tasks(app, 12)
        html = admin_login.get("/admin/sites?page=2&per_page=10").data.decode()
        assert html.count("btn-danger") == 2
        assert "2 / 2" in html


class TestSiteDelete:
    def test_admin_delete_cascades(self, app, admin_login):
        task_id = _seed_tasks(app, 1)[0]
        with app.app_context():
            uid = User.query.filter_by(username="admin").first().id
            db.session.add(PlanItem(task_id=task_id, user_id=uid, code="wechat_mp",
                                    priority="high", title="t", content="c"))
            db.session.commit()

        resp = admin_login.post(f"/admin/sites/{task_id}/delete")
        assert resp.status_code == 302
        with app.app_context():
            assert db.session.get(EvalTask, task_id) is None
            assert PlanItem.query.filter_by(task_id=task_id).count() == 0
            assert TaskLog.query.filter_by(task_id=task_id).count() == 0

    def test_delete_missing_task_no_error(self, app, admin_login):
        resp = admin_login.post("/admin/sites/not-exist/delete")
        assert resp.status_code == 302

    def test_non_admin_forbidden(self, app, client):
        from geo_optimizer.web.portal.auth.service import create_user

        task_id = _seed_tasks(app, 1)[0]
        with app.app_context():
            create_user("member", "pw123456", role="user", eval_quota=5)
        client.post("/login", data={"username": "member", "password": "pw123456"})
        resp = client.post(f"/admin/sites/{task_id}/delete")
        assert resp.status_code in (302, 403)  # admin_required 拒绝
        with app.app_context():
            assert db.session.get(EvalTask, task_id) is not None
