# -*- coding: utf-8 -*-
"""任务处理日志：写入 / 时间倒排 / 状态接口返回与翻译。"""
from datetime import datetime, timedelta

from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models import EvalTask, TaskLog, User
from geo_optimizer.web.portal.tasks import service


def _make_task(app) -> str:
    with app.app_context():
        admin = User.query.filter_by(username="admin").first()
        task = service.create_task(admin.id, "https://example.com", "eval")
        return task.id


class TestLogService:
    def test_create_task_writes_log(self, app):
        task_id = _make_task(app)
        with app.app_context():
            logs = service.logs_for(task_id)
            assert len(logs) == 1
            assert logs[0].message == "log_created"
            assert logs[0].detail == "https://example.com"

    def test_update_progress_appends_log(self, app):
        task_id = _make_task(app)
        with app.app_context():
            service.update_progress(task_id, 10, "crawling")
            service.update_progress(task_id, 40, "analyzing")
            messages = [log.message for log in service.logs_for(task_id)]
            assert "crawling" in messages and "analyzing" in messages

    def test_logs_sorted_desc(self, app):
        task_id = _make_task(app)
        with app.app_context():
            base = datetime(2026, 1, 1, 12, 0, 0)
            for i, msg in enumerate(["first", "second", "third"]):
                db.session.add(TaskLog(task_id=task_id, message=msg,
                                       created_at=base + timedelta(seconds=i)))
            db.session.commit()
            logs = service.logs_for(task_id)
            idx = {log.message: n for n, log in enumerate(logs)}
            # 时间倒排：最新的 third 在最前
            assert idx["third"] < idx["second"] < idx["first"]

    def test_mark_failed_writes_error_log(self, app):
        task_id = _make_task(app)
        with app.app_context():
            service.mark_failed(task_id, "boom")
            top = service.logs_for(task_id)[0]
            assert top.message == "log_failed"
            assert top.level == "error"
            assert top.detail == "boom"

    def test_logs_for_limit(self, app):
        task_id = _make_task(app)
        with app.app_context():
            for i in range(15):
                service.add_log(task_id, f"m{i}")
            assert len(service.logs_for(task_id, limit=10)) == 10
            assert service.count_logs(task_id) == 16  # 含 log_created

    def test_purge_expired_logs(self, app):
        task_id = _make_task(app)
        with app.app_context():
            old = datetime.utcnow() - timedelta(days=4)
            db.session.add(TaskLog(task_id=task_id, message="stale", created_at=old))
            db.session.commit()
            deleted = service.purge_expired_logs()
            assert deleted == 1
            messages = [log.message for log in service.logs_for(task_id)]
            # 保留期内的 log_created 不受影响
            assert "stale" not in messages and "log_created" in messages


class TestStatusEndpoint:
    def test_status_contains_translated_logs(self, app, admin_login):
        task_id = _make_task(app)
        with app.app_context():
            service.update_progress(task_id, 10, "crawling")
        resp = admin_login.get(f"/eval/{task_id}/status")
        data = resp.get_json()
        assert resp.status_code == 200
        logs = data["logs"]
        # 倒排：最新（crawling）在前；默认中文翻译
        assert logs[0]["message"] == "正在爬取页面"
        assert logs[-1]["message"] == "任务已创建"
        assert data["message_text"] == "正在爬取页面"

    def test_detail_page_renders_console(self, app, admin_login):
        task_id = _make_task(app)
        resp = admin_login.get(f"/eval/{task_id}")
        assert resp.status_code == 200
        assert "task-console" in resp.get_data(as_text=True)

    def test_status_limits_recent_and_reports_total(self, app, admin_login):
        task_id = _make_task(app)
        with app.app_context():
            for i in range(15):
                service.add_log(task_id, f"m{i}")
        data = admin_login.get(f"/eval/{task_id}/status").get_json()
        assert len(data["logs"]) == service.RECENT_LOGS
        assert data["log_total"] == 16

    def test_full_history_endpoint(self, app, admin_login):
        task_id = _make_task(app)
        with app.app_context():
            for i in range(15):
                service.add_log(task_id, f"m{i}")
        data = admin_login.get(f"/eval/{task_id}/logs").get_json()
        assert len(data["logs"]) == 16
        # 倒排：最早的 log_created 在末尾
        assert data["logs"][-1]["message"] == "任务已创建"

    def test_delete_cascades_logs(self, app, admin_login):
        task_id = _make_task(app)
        resp = admin_login.post(f"/history/{task_id}/delete")
        assert resp.status_code == 302
        with app.app_context():
            assert TaskLog.query.filter_by(task_id=task_id).count() == 0
            assert db.session.get(EvalTask, task_id) is None


class TestDetailedLogKeys:
    def test_all_pipeline_log_keys_bilingual(self):
        """流水线细粒度日志键均具备中英双语文案。"""
        from geo_optimizer.web.portal.i18n.messages import MESSAGES

        keys = [
            "log_created", "log_crawl_done", "log_page_meta",
            "log_analyze_done", "log_engine_scores", "log_audit_done",
            "log_report_written", "log_faq_done", "log_faq_failed",
            "log_schema_done", "log_schema_failed",
            "log_authority_done", "log_authority_failed",
            "log_enhance_done", "log_enhance_failed",
            "log_export_done", "log_export_failed",
            "log_items_done", "log_items_failed",
            "log_zip_done", "log_done", "log_failed",
        ]
        for key in keys:
            assert key in MESSAGES, key
            assert MESSAGES[key]["zh"] and MESSAGES[key]["en"], key
