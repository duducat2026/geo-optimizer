# -*- coding: utf-8 -*-
"""普通用户控制台测试：评估历史最近 10 条展示与级联删除。"""
from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models import EvalTask, PlanItem, TaskLog, User
from geo_optimizer.web.portal.tasks import service


def _user_client(app, client, count: int = 0) -> list:
    """创建普通用户并登录，预置 count 条任务，返回任务 id 列表。"""
    from geo_optimizer.web.portal.auth.service import create_user

    with app.app_context():
        user = create_user("member", "pw123456", role="user", eval_quota=99)
        uid = user.id
        task_ids = [service.create_task(uid, f"https://m{i}.com", "eval").id
                    for i in range(count)]
    client.post("/login", data={"username": "member", "password": "pw123456"})
    return task_ids


class TestDashboardRecent:
    def test_recent_limited_to_10(self, app, client):
        _user_client(app, client, count=13)
        html = client.get("/").data.decode()
        # 控制台评估历史仅展示最近 10 条，附查看全部链接
        assert html.count("btn-danger") == 10
        assert "/history" in html

    def test_delete_button_rendered(self, app, client):
        _user_client(app, client, count=1)
        html = client.get("/").data.decode()
        assert "next=dashboard" in html
        assert html.count("btn-danger") == 1


class TestDashboardDelete:
    def test_delete_cascades_and_back_to_dashboard(self, app, client):
        task_id = _user_client(app, client, count=1)[0]
        with app.app_context():
            uid = User.query.filter_by(username="member").first().id
            db.session.add(PlanItem(task_id=task_id, user_id=uid, code="wechat_mp",
                                    priority="high", title="t", content="c"))
            db.session.commit()

        resp = client.post(f"/history/{task_id}/delete?next=dashboard")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/dashboard")
        with app.app_context():
            assert db.session.get(EvalTask, task_id) is None
            assert PlanItem.query.filter_by(task_id=task_id).count() == 0
            assert TaskLog.query.filter_by(task_id=task_id).count() == 0

    def test_delete_without_next_back_to_history(self, app, client):
        task_id = _user_client(app, client, count=1)[0]
        resp = client.post(f"/history/{task_id}/delete")
        assert resp.status_code == 302
        assert "/history" in resp.headers["Location"]

    def test_cannot_delete_others_task(self, app, client):
        # admin 名下任务，普通用户不可删
        with app.app_context():
            admin_id = User.query.filter_by(username="admin").first().id
            task_id = service.create_task(admin_id, "https://a.com", "eval").id
        _user_client(app, client)
        resp = client.post(f"/history/{task_id}/delete")
        assert resp.status_code == 403
        with app.app_context():
            assert db.session.get(EvalTask, task_id) is not None


class TestHistoryPagination:
    def test_default_10_per_page(self, app, client):
        _user_client(app, client, count=15)
        html = client.get("/history").data.decode()
        # 默认每页 10 条（+1 为批量删除按钮）
        assert html.count("btn-danger") == 11
        assert "1 / 2" in html

    def test_per_page_choices(self, app, client):
        _user_client(app, client, count=25)
        for per_page, expect in ((10, 10), (20, 20), (50, 25)):
            html = client.get(f"/history?per_page={per_page}").data.decode()
            assert html.count("btn-danger") == expect + 1

    def test_invalid_per_page_falls_back(self, app, client):
        _user_client(app, client, count=12)
        html = client.get("/history?per_page=999").data.decode()
        assert html.count("btn-danger") == 11

    def test_page_out_of_range_clamped(self, app, client):
        _user_client(app, client, count=5)
        resp = client.get("/history?page=99")
        assert resp.status_code == 200
        assert "1 / 1" in resp.data.decode()

    def test_second_page(self, app, client):
        _user_client(app, client, count=12)
        html = client.get("/history?page=2&per_page=10").data.decode()
        assert html.count("btn-danger") == 3
        assert "2 / 2" in html

    def test_delete_preserves_pagination(self, app, client):
        task_id = _user_client(app, client, count=1)[0]
        resp = client.post(f"/history/{task_id}/delete?page=1&per_page=20")
        assert resp.status_code == 302
        assert "per_page=20" in resp.headers["Location"]


class TestHistoryBatchDelete:
    """历史评估批量删除。"""

    def test_batch_delete_cascades(self, app, client):
        task_ids = _user_client(app, client, count=3)
        resp = client.post("/history/batch-delete",
                           data={"task_ids": task_ids[:2]})
        assert resp.status_code == 302
        with app.app_context():
            assert db.session.get(EvalTask, task_ids[0]) is None
            assert db.session.get(EvalTask, task_ids[1]) is None
            assert db.session.get(EvalTask, task_ids[2]) is not None
            assert TaskLog.query.filter_by(task_id=task_ids[0]).count() == 0

    def test_batch_delete_skips_others_tasks(self, app, client):
        """批量删除跳过他人任务，不报错不误删。"""
        with app.app_context():
            admin_id = User.query.filter_by(username="admin").first().id
            admin_task = service.create_task(admin_id, "https://a.com", "eval").id
        own_task = _user_client(app, client, count=1)[0]
        resp = client.post("/history/batch-delete",
                           data={"task_ids": [own_task, admin_task]})
        assert resp.status_code == 302
        with app.app_context():
            assert db.session.get(EvalTask, own_task) is None
            assert db.session.get(EvalTask, admin_task) is not None

    def test_batch_delete_empty_selection(self, app, client):
        """未勾选时提交不报错，重定向回历史页。"""
        _user_client(app, client)
        resp = client.post("/history/batch-delete", data={})
        assert resp.status_code == 302
        assert "/history" in resp.headers["Location"]

    def test_batch_delete_preserves_pagination(self, app, client):
        task_ids = _user_client(app, client, count=1)
        resp = client.post("/history/batch-delete?page=2&per_page=20",
                           data={"task_ids": task_ids})
        assert resp.status_code == 302
        assert "per_page=20" in resp.headers["Location"]

    def test_checkboxes_rendered(self, app, client):
        task_ids = _user_client(app, client, count=2)
        html = client.get("/history").data.decode()
        for tid in task_ids:
            assert f'value="{tid}" form="batch-del-form"' in html
        assert "check-all" in html
