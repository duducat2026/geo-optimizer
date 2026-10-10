# -*- coding: utf-8 -*-
"""失败任务重试测试：重置并重启、状态校验、配额校验、越权拦截。"""
from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models import EvalTask, User
from geo_optimizer.web.portal.tasks import service


def _make_failed(app, task_id="rt-1", username="admin", quota=None, used=0):
    """创建指定用户的失败任务，返回任务 id。"""
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, eval_quota=quota or 10)
            user.set_password("pass12345")
            db.session.add(user)
            db.session.commit()
        if quota is not None:
            user.eval_quota = quota
        user.eval_used = used
        # 配额按自然日重置：计数需标记为今日才生效
        if used:
            from datetime import date
            user.quota_date = date.today()
        db.session.commit()
        task = service.create_task(user.id, "https://example.com", "eval")
        service.mark_failed(task.id, "boom")
        return task.id


class TestRetry:
    def test_retry_failed_task_resets_and_restarts(self, app, admin_login, monkeypatch):
        started = []
        monkeypatch.setattr("geo_optimizer.web.portal.user.routes.runner.start",
                            lambda *a, **k: started.append(a))
        tid = _make_failed(app, "rt-ok")
        resp = admin_login.post(f"/eval/{tid}/retry")
        assert resp.status_code == 302
        assert started, "重试应重新启动执行线程"
        with app.app_context():
            task = db.session.get(EvalTask, tid)
            assert task.status == "pending"
            assert task.progress == 0
            assert task.error == ""

    def test_retry_completed_task_rejected(self, app, admin_login, monkeypatch):
        monkeypatch.setattr("geo_optimizer.web.portal.user.routes.runner.start",
                            lambda *a, **k: None)
        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            task = service.create_task(admin.id, "https://c.com", "eval")
            service.mark_completed(task.id, {}, 88.0)
            tid = task.id
        resp = admin_login.post(f"/eval/{tid}/retry", follow_redirects=True)
        assert "仅失败任务可重试".encode() in resp.data
        with app.app_context():
            assert db.session.get(EvalTask, tid).status == "completed"

    def test_retry_blocked_when_quota_exhausted(self, app, client, monkeypatch):
        started = []
        monkeypatch.setattr("geo_optimizer.web.portal.user.routes.runner.start",
                            lambda *a, **k: started.append(a))
        # quota=1 且 used=1 → quota_left=0
        tid = _make_failed(app, "rt-quota", username="quotauser",
                           quota=1, used=1)
        client.post("/login", data={"username": "quotauser",
                                    "password": "pass12345"})
        resp = client.post(f"/eval/{tid}/retry", follow_redirects=True)
        assert "评估次数已用完".encode() in resp.data
        assert not started, "配额耗尽不应重启任务"
        with app.app_context():
            assert db.session.get(EvalTask, tid).status == "failed"

    def test_retry_foreign_user_forbidden(self, app, client, monkeypatch):
        monkeypatch.setattr("geo_optimizer.web.portal.user.routes.runner.start",
                            lambda *a, **k: None)
        tid = _make_failed(app, "rt-403", username="owner1")
        with app.app_context():
            other = User(username="intruder", eval_quota=10)
            other.set_password("pass12345")
            db.session.add(other)
            db.session.commit()
        client.post("/login", data={"username": "intruder",
                                    "password": "pass12345"})
        assert client.post(f"/eval/{tid}/retry").status_code == 403
