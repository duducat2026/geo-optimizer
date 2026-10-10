# -*- coding: utf-8 -*-
"""任务监控测试：服务重启遗留任务回收 + 卡死任务巡检。"""
from datetime import datetime, timedelta

from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RUNNING,
    EvalTask,
    TaskLog,
    User,
)
from geo_optimizer.web.portal.tasks import service


def _admin_id(app):
    with app.app_context():
        return User.query.filter_by(username="admin").first().id


class TestInterruptedRecovery:
    def test_startup_fails_leftover_tasks(self, app):
        """启动回收：pending/running 全部标记失败，completed 不受影响。"""
        uid = _admin_id(app)
        with app.app_context():
            t_running = service.create_task(uid, "https://a.com", "eval")
            service.update_progress(t_running.id, 40, "analyzing")
            t_pending = service.create_task(uid, "https://b.com", "eval")
            t_done = service.create_task(uid, "https://c.com", "eval")
            service.mark_completed(t_done.id, {}, 80.0)

            assert service.fail_interrupted_tasks() == 2

            assert db.session.get(EvalTask, t_running.id).status == STATUS_FAILED
            assert db.session.get(EvalTask, t_pending.id).status == STATUS_FAILED
            assert db.session.get(EvalTask, t_done.id).status == STATUS_COMPLETED
            assert db.session.get(EvalTask, t_running.id).error == "task_interrupted"

    def test_interrupted_writes_error_log(self, app):
        uid = _admin_id(app)
        with app.app_context():
            task = service.create_task(uid, "https://a.com", "eval")
            service.fail_interrupted_tasks()
            logs = service.logs_for(task.id)
            assert logs[0].message == "log_failed"
            assert logs[0].level == "error"


class TestStalledDetection:
    def test_stalled_task_marked_failed(self, app):
        """最后一条日志早于超时阈值的 running 任务被判失败。"""
        uid = _admin_id(app)
        with app.app_context():
            task = service.create_task(uid, "https://a.com", "eval")
            service.update_progress(task.id, 10, "crawling")
            stale = datetime.utcnow() - timedelta(minutes=service.STALL_TIMEOUT_MINUTES + 5)
            for log in TaskLog.query.filter_by(task_id=task.id).all():
                log.created_at = stale
            db.session.commit()

            assert service.fail_stalled_tasks() == 1
            refreshed = db.session.get(EvalTask, task.id)
            assert refreshed.status == STATUS_FAILED
            assert refreshed.error == "task_stalled"

    def test_active_task_not_touched(self, app):
        """有近期日志活动的任务不会被误杀。"""
        uid = _admin_id(app)
        with app.app_context():
            task = service.create_task(uid, "https://a.com", "eval")
            service.update_progress(task.id, 40, "analyzing")

            assert service.fail_stalled_tasks() == 0
            assert db.session.get(EvalTask, task.id).status == STATUS_RUNNING

    def test_failed_error_translated_on_detail_page(self, app, admin_login):
        """失败原因（i18n key）在详情页按语言翻译展示。"""
        uid = _admin_id(app)
        with app.app_context():
            task = service.create_task(uid, "https://a.com", "eval")
            service.mark_failed(task.id, "task_interrupted")
            task_id = task.id
        resp = admin_login.get(f"/eval/{task_id}")
        assert resp.status_code == 200
        assert "服务重启，任务已中断".encode() in resp.data
