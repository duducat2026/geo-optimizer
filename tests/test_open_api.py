# -*- coding: utf-8 -*-
"""开放 API 端点测试：密钥管理、鉴权、任务提交/查询/结果/下载、调用日志。"""
import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest


@pytest.fixture()
def api_key(app, client):
    """为默认管理员生成一个 API 密钥，返回明文。"""
    client.post("/login", data={"username": "admin", "password": "admin123"})
    from geo_optimizer.web.portal.api.auth import generate_api_key
    from geo_optimizer.web.portal.models import User

    with app.app_context():
        user = User.query.filter_by(username="admin").first()
        _, raw_key = generate_api_key(user.id, name="test-key", expires_days=365)
    return raw_key


@pytest.fixture()
def auth_header(api_key):
    """携带 API 密钥的请求头。"""
    return {"Authorization": f"Bearer {api_key}"}


# ─── 鉴权测试 ────────────────────────────────────────────────────────────────


class TestApiAuth:
    def test_missing_auth_header(self, client):
        resp = client.get("/api/v1/usage")
        assert resp.status_code == 401
        data = resp.get_json()
        assert data["error"] == "missing_token"

    def test_invalid_key(self, client):
        resp = client.get("/api/v1/usage",
                          headers={"Authorization": "Bearer geo_invalid_key_123"})
        assert resp.status_code == 401
        data = resp.get_json()
        assert data["error"] == "invalid_token"

    def test_expired_key(self, app, client):
        """过期密钥应被拒绝。"""
        client.post("/login", data={"username": "admin", "password": "admin123"})
        from geo_optimizer.web.portal.api.auth import generate_api_key
        from geo_optimizer.web.portal.models import ApiKey, User

        with app.app_context():
            user = User.query.filter_by(username="admin").first()
            _, raw_key = generate_api_key(user.id, name="expired", expires_days=1)
            # 手动将过期时间改为过去
            key = ApiKey.query.filter_by(user_id=user.id).order_by(ApiKey.id.desc()).first()
            key.expires_at = datetime.utcnow() - timedelta(days=1)
            from geo_optimizer.web.portal.extensions import db
            db.session.commit()

        resp = client.get("/api/v1/usage",
                          headers={"Authorization": f"Bearer {raw_key}"})
        assert resp.status_code == 401

    def test_revoked_key(self, app, client):
        """停用密钥应被拒绝。"""
        client.post("/login", data={"username": "admin", "password": "admin123"})
        from geo_optimizer.web.portal.api.auth import generate_api_key
        from geo_optimizer.web.portal.models import ApiKey, User

        with app.app_context():
            user = User.query.filter_by(username="admin").first()
            _, raw_key = generate_api_key(user.id, name="revoked", expires_days=365)
            key = ApiKey.query.filter_by(user_id=user.id).order_by(ApiKey.id.desc()).first()
            key.is_active = False
            from geo_optimizer.web.portal.extensions import db
            db.session.commit()

        resp = client.get("/api/v1/usage",
                          headers={"Authorization": f"Bearer {raw_key}"})
        assert resp.status_code == 401

    def test_valid_key(self, client, auth_header):
        resp = client.get("/api/v1/usage", headers=auth_header)
        assert resp.status_code == 200


# ─── 提交任务测试 ─────────────────────────────────────────────────────────────


class TestSubmitTask:
    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_submit_success(self, mock_start, client, auth_header):
        resp = client.post("/api/v1/tasks",
                           headers=auth_header,
                           json={"target_url": "https://example.com", "task_type": "plan"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert "task_id" in data
        assert data["status"] == "pending"
        assert data["task_type"] == "plan"
        mock_start.assert_called_once()

    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_submit_marks_source_api(self, mock_start, app, client, auth_header):
        """通过 API 提交的任务 source 应为 'api'。"""
        resp = client.post("/api/v1/tasks",
                           headers=auth_header,
                           json={"target_url": "https://example.com"})
        task_id = resp.get_json()["task_id"]

        with app.app_context():
            from geo_optimizer.web.portal.models import EvalTask
            from geo_optimizer.web.portal.extensions import db
            task = db.session.get(EvalTask, task_id)
            assert task.source == "api"

    def test_submit_missing_url(self, client, auth_header):
        resp = client.post("/api/v1/tasks", headers=auth_header, json={})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "invalid_params"

    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_submit_default_type_eval(self, mock_start, client, auth_header):
        resp = client.post("/api/v1/tasks",
                           headers=auth_header,
                           json={"target_url": "https://example.com"})
        assert resp.status_code == 201
        assert resp.get_json()["task_type"] == "eval"


# ─── 任务状态查询测试 ──────────────────────────────────────────────────────────


class TestTaskStatus:
    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_query_status(self, mock_start, client, auth_header):
        # 先提交任务
        resp = client.post("/api/v1/tasks",
                           headers=auth_header,
                           json={"target_url": "https://example.com"})
        task_id = resp.get_json()["task_id"]

        # 查询状态
        resp = client.get(f"/api/v1/tasks/{task_id}", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["task_id"] == task_id
        assert data["status"] == "pending"
        assert data["source"] == "api"

    def test_query_not_found(self, client, auth_header):
        resp = client.get("/api/v1/tasks/nonexistent-id", headers=auth_header)
        assert resp.status_code == 404


# ─── 任务终止测试 ─────────────────────────────────────


class TestTaskCancel:
    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_cancel_pending_running(self, mock_start, app, client, auth_header):
        """pending/running 任务终止返回 200，运行中为 cancelling。"""
        task_id = client.post("/api/v1/tasks", headers=auth_header,
                              json={"target_url": "https://c.com"}).get_json()["task_id"]
        # 默认 pending 终止 -> cancelled
        resp = client.post(f"/api/v1/tasks/{task_id}/cancel", headers=auth_header)
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "cancelled"

        # running 终止 -> cancelling
        tid2 = client.post("/api/v1/tasks", headers=auth_header,
                          json={"target_url": "https://c2.com"}).get_json()["task_id"]
        with app.app_context():
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.models import EvalTask
            db.session.get(EvalTask, tid2).status = "running"
            db.session.commit()
        resp2 = client.post(f"/api/v1/tasks/{tid2}/cancel", headers=auth_header)
        assert resp2.status_code == 200
        assert resp2.get_json()["status"] == "cancelling"

    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_cancel_completed_conflict(self, mock_start, app, client, auth_header):
        """已结束（completed）任务无法终止，返回 409 invalid_state。"""
        task_id = client.post("/api/v1/tasks", headers=auth_header,
                              json={"target_url": "https://c.com"}).get_json()["task_id"]
        with app.app_context():
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.models import EvalTask
            db.session.get(EvalTask, task_id).status = "completed"
            db.session.commit()
        resp = client.post(f"/api/v1/tasks/{task_id}/cancel", headers=auth_header)
        assert resp.status_code == 409
        assert resp.get_json()["error"] == "invalid_state"

    def test_cancel_not_found(self, client, auth_header):
        resp = client.post("/api/v1/tasks/nonexistent-id/cancel", headers=auth_header)
        assert resp.status_code == 404

    def test_cancel_requires_auth(self, client):
        resp = client.post("/api/v1/tasks/any-id/cancel")
        assert resp.status_code == 401

    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_cancel_forbidden_other_user(self, mock_start, app, client, auth_header):
        """非管理员不能终止他人任务，返回 403。"""
        task_id = client.post("/api/v1/tasks", headers=auth_header,
                              json={"target_url": "https://c.com"}).get_json()["task_id"]
        # 新建一个普通用户与其密钥，用其去终止 admin 的任务
        with app.app_context():
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.api.auth import generate_api_key
            from geo_optimizer.web.portal.models import User
            other = User(username="other", email="o@e.com", is_active=True)
            other.set_password("pw123456")
            db.session.add(other)
            db.session.commit()
            _, other_key = generate_api_key(other.id, name="other-key", expires_days=365)
        resp = client.post(f"/api/v1/tasks/{task_id}/cancel",
                           headers={"Authorization": f"Bearer {other_key}"})
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "forbidden"


# ─── 任务列表（总数/分页/日期范围）测试 ────────────────────────────


class TestListTasks:
    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_pagination_and_total(self, mock_start, client, auth_header):
        """返回总条数与分页数据（默认每页 10 条）。"""
        for i in range(12):
            client.post("/api/v1/tasks", headers=auth_header,
                        json={"target_url": f"https://example.com/{i}"})

        data = client.get("/api/v1/tasks", headers=auth_header).get_json()
        assert data["total"] == 12
        assert data["limit"] == 10
        assert data["page"] == 1
        assert data["pages"] == 2
        assert len(data["tasks"]) == 10

        d2 = client.get("/api/v1/tasks?page=2", headers=auth_header).get_json()
        assert d2["page"] == 2
        assert len(d2["tasks"]) == 2

        d3 = client.get("/api/v1/tasks?limit=5", headers=auth_header).get_json()
        assert d3["limit"] == 5
        assert d3["pages"] == 3
        assert len(d3["tasks"]) == 5

    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_date_range_filter(self, mock_start, app, client, auth_header):
        """start/end 按 created_at 过滤，end 为纯日期时含当天。"""
        ids = [client.post("/api/v1/tasks", headers=auth_header,
                           json={"target_url": f"https://d.com/{i}"}).get_json()["task_id"]
               for i in range(3)]
        with app.app_context():
            from geo_optimizer.web.portal.extensions import db
            from geo_optimizer.web.portal.models import EvalTask
            base = datetime(2026, 7, 10)
            for offset, tid in enumerate(ids):
                db.session.get(EvalTask, tid).created_at = base + timedelta(days=offset * 10)
            db.session.commit()  # created_at -> 07-10 / 07-20 / 07-30

        mid = client.get("/api/v1/tasks?start=2026-07-15&end=2026-07-25",
                         headers=auth_header).get_json()
        assert mid["total"] == 1
        assert mid["tasks"][0]["created_at"].startswith("2026-07-20")

        # end 纯日期含当天：start=end=07-10 应命中 07-10 那条
        same = client.get("/api/v1/tasks?start=2026-07-10&end=2026-07-10",
                          headers=auth_header).get_json()
        assert same["total"] == 1


# ─── 任务执行日志测试 ──────────────────────────────────────────────────────────────────────


class TestTaskLogs:
    @staticmethod
    def _submit(client, auth_header):
        with patch("geo_optimizer.web.portal.api.routes.runner.start"):
            resp = client.post("/api/v1/tasks",
                               headers=auth_header,
                               json={"target_url": "https://example.com"})
        return resp.get_json()["task_id"]

    def test_logs_translated(self, app, client, auth_header):
        """日志端点返回翻译后的文案（默认中文），按时间正排。"""
        task_id = self._submit(client, auth_header)
        from geo_optimizer.web.portal.tasks import service

        with app.app_context():
            service.update_progress(task_id, 10, "crawling")

        resp = client.get(f"/api/v1/tasks/{task_id}/logs", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        messages = [entry["message"] for entry in data["logs"]]
        # 正排：最早的 log_created 在前，且已翻译为中文
        assert messages[0] == "任务已创建"
        assert "正在爬取页面" in messages
        assert data["last_id"] == data["logs"][-1]["id"]

    def test_logs_incremental(self, app, client, auth_header):
        """after_id 增量拉取：只返回新日志。"""
        task_id = self._submit(client, auth_header)
        from geo_optimizer.web.portal.tasks import service

        resp = client.get(f"/api/v1/tasks/{task_id}/logs", headers=auth_header)
        last_id = resp.get_json()["last_id"]

        with app.app_context():
            service.update_progress(task_id, 40, "analyzing")

        resp = client.get(f"/api/v1/tasks/{task_id}/logs?after_id={last_id}",
                          headers=auth_header)
        data = resp.get_json()
        assert len(data["logs"]) == 1
        assert data["logs"][0]["message"] == "正在分析评分与体检"
        assert data["last_id"] > last_id

        # 无新日志时返回空列表，last_id 保持不变
        resp = client.get(f"/api/v1/tasks/{task_id}/logs?after_id={data['last_id']}",
                          headers=auth_header)
        again = resp.get_json()
        assert again["logs"] == []
        assert again["last_id"] == data["last_id"]

    def test_logs_not_found(self, client, auth_header):
        resp = client.get("/api/v1/tasks/nonexistent-id/logs", headers=auth_header)
        assert resp.status_code == 404

    def test_logs_requires_auth(self, client):
        resp = client.get("/api/v1/tasks/any-id/logs")
        assert resp.status_code == 401


# ─── 任务结果测试 ─────────────────────────────────────────────────────────────


class TestTaskResult:
    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_result_not_completed(self, mock_start, client, auth_header):
        resp = client.post("/api/v1/tasks",
                           headers=auth_header,
                           json={"target_url": "https://example.com"})
        task_id = resp.get_json()["task_id"]

        resp = client.get(f"/api/v1/tasks/{task_id}/result", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "pending"
        assert "result" not in data

    def test_result_completed(self, app, client, auth_header):
        """模拟已完成任务的结果获取。"""
        from geo_optimizer.web.portal.extensions import db
        from geo_optimizer.web.portal.models import EvalTask, User

        with app.app_context():
            user = User.query.filter_by(username="admin").first()
            task = EvalTask(
                id="test-completed-task",
                user_id=user.id,
                target_url="https://example.com",
                type="plan",
                source="api",
                status="completed",
                progress=100,
                overall_score=75.5,
            )
            task.set_result({"url": "https://example.com", "overall_score": 75.5})
            db.session.add(task)
            db.session.commit()

        resp = client.get("/api/v1/tasks/test-completed-task/result", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "completed"
        assert data["overall_score"] == 75.5
        assert data["result"]["overall_score"] == 75.5
        # 无方案条目时不返回免登录分享链接
        assert data["share_download_url"] is None

    def test_result_share_download_url(self, app, client, auth_header):
        """存在方案条目时，结果返回免登录分享下载链接。"""
        from geo_optimizer.web.portal.extensions import db
        from geo_optimizer.web.portal.models import EvalTask, PlanItem, User

        with app.app_context():
            user = User.query.filter_by(username="admin").first()
            task = EvalTask(
                id="test-share-task",
                user_id=user.id,
                target_url="https://example.com",
                type="plan",
                source="api",
                status="completed",
                progress=100,
                overall_score=80.0,
            )
            task.set_result({"overall_score": 80.0})
            db.session.add(task)
            db.session.add(PlanItem(task_id="test-share-task", user_id=user.id,
                                    code="C1", priority="P0", title="t", content="c"))
            db.session.commit()

        resp = client.get("/api/v1/tasks/test-share-task/result", headers=auth_header)
        data = resp.get_json()
        assert data["share_download_url"].endswith("/plan/test-share-task/download")
        assert data["share_download_url"].startswith("http")


class TestListTasks:
    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_list_recent_tasks(self, mock_start, client, auth_header):
        """GET /api/v1/tasks 返回最近提交的任务列表（新→旧）。"""
        for i in range(3):
            client.post("/api/v1/tasks", headers=auth_header,
                        json={"target_url": f"https://site{i}.com"})

        resp = client.get("/api/v1/tasks", headers=auth_header)
        assert resp.status_code == 200
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 3
        assert {"task_id", "target_url", "task_type", "status",
                "progress", "overall_score", "created_at"} <= set(tasks[0])
        urls = [t["target_url"] for t in tasks]
        assert "https://site0.com" in urls and "https://site2.com" in urls

    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_list_tasks_limit(self, mock_start, client, auth_header):
        for i in range(3):
            client.post("/api/v1/tasks", headers=auth_header,
                        json={"target_url": f"https://limit{i}.com"})
        resp = client.get("/api/v1/tasks?limit=2", headers=auth_header)
        assert len(resp.get_json()["tasks"]) == 2

    def test_list_tasks_requires_auth(self, client):
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 401


# ─── 下载测试 ─────────────────────────────────────────────────────────────────


class TestTaskDownload:
    def test_download_not_available(self, app, client, auth_header):
        """无下载包时返回 404。"""
        from geo_optimizer.web.portal.extensions import db
        from geo_optimizer.web.portal.models import EvalTask, User

        with app.app_context():
            user = User.query.filter_by(username="admin").first()
            task = EvalTask(
                id="test-no-zip",
                user_id=user.id,
                target_url="https://example.com",
                type="eval",
                source="api",
                status="completed",
                progress=100,
            )
            db.session.add(task)
            db.session.commit()

        resp = client.get("/api/v1/tasks/test-no-zip/download", headers=auth_header)
        assert resp.status_code == 404

    def test_download_success(self, app, client, auth_header, tmp_path):
        """有 ZIP 包时正常下载。"""
        import zipfile

        from geo_optimizer.web.portal.extensions import db
        from geo_optimizer.web.portal.models import EvalTask, GeoPlan, User

        # 创建一个测试 ZIP
        zip_path = tmp_path / "geo_plan_test-dl.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("report.md", "# Test Report")

        with app.app_context():
            user = User.query.filter_by(username="admin").first()
            task = EvalTask(
                id="test-dl",
                user_id=user.id,
                target_url="https://example.com",
                type="plan",
                source="api",
                status="completed",
                progress=100,
            )
            db.session.add(task)
            plan = GeoPlan(
                task_id="test-dl",
                user_id=user.id,
                target_url="https://example.com",
                zip_path=str(zip_path),
            )
            db.session.add(plan)
            db.session.commit()

        resp = client.get("/api/v1/tasks/test-dl/download", headers=auth_header)
        assert resp.status_code == 200
        assert resp.content_type == "application/zip" or "zip" in resp.content_type


# ─── 调用日志与统计测试 ────────────────────────────────────────────────────────


class TestUsageAndLogs:
    def test_usage_stats(self, client, auth_header):
        # 先做一次调用
        client.get("/api/v1/usage", headers=auth_header)
        # 再次获取统计
        resp = client.get("/api/v1/usage", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_calls"] >= 1
        assert len(data["keys"]) >= 1

    def test_call_log_recorded(self, app, client, auth_header):
        """每次 API 调用应记录日志。"""
        client.get("/api/v1/usage", headers=auth_header)

        with app.app_context():
            from geo_optimizer.web.portal.models import ApiCallLog
            count = ApiCallLog.query.count()
            assert count >= 1
            log = ApiCallLog.query.first()
            assert log.endpoint == "/api/v1/usage"
            assert log.method == "GET"
            assert log.status_code == 200


# ─── Web 端密钥管理测试 ────────────────────────────────────────────────────────


class TestWebKeyManagement:
    def test_api_keys_page(self, client):
        client.post("/login", data={"username": "admin", "password": "admin123"})
        resp = client.get("/api-keys")
        assert resp.status_code == 200

    def test_generate_key_via_web(self, client):
        client.post("/login", data={"username": "admin", "password": "admin123"})
        resp = client.post("/api-keys/generate",
                           data={"name": "my-key", "expires_days": "30"})
        assert resp.status_code == 200
        assert b"geo_" in resp.data  # 新密钥明文展示

    def test_revoke_endpoint_removed(self, app, client):
        """用户侧停用功能已下线，revoke 路由不再存在。"""
        client.post("/login", data={"username": "admin", "password": "admin123"})
        from geo_optimizer.web.portal.api.auth import generate_api_key
        from geo_optimizer.web.portal.models import User

        with app.app_context():
            user = User.query.filter_by(username="admin").first()
            api_key, _ = generate_api_key(user.id, name="no-revoke")
            key_id = api_key.id

        resp = client.post(f"/api-keys/{key_id}/revoke")
        assert resp.status_code == 404

        with app.app_context():
            from geo_optimizer.web.portal.models import ApiKey
            key = ApiKey.query.get(key_id)
            assert key.is_active is True

    def test_key_logs_page(self, app, client):
        client.post("/login", data={"username": "admin", "password": "admin123"})
        from geo_optimizer.web.portal.api.auth import generate_api_key
        from geo_optimizer.web.portal.models import User

        with app.app_context():
            user = User.query.filter_by(username="admin").first()
            api_key, _ = generate_api_key(user.id, name="log-test")
            key_id = api_key.id

        resp = client.get(f"/api-keys/{key_id}/logs")
        assert resp.status_code == 200


class TestWebKeyReveal:
    """API 密钥明文查看与复制。"""

    def _gen_key(self, app, username="admin", name="reveal"):
        from geo_optimizer.web.portal.api.auth import generate_api_key
        from geo_optimizer.web.portal.models import User
        with app.app_context():
            user = User.query.filter_by(username=username).first()
            api_key, raw_key = generate_api_key(user.id, name=name)
            return api_key.id, raw_key

    def test_generated_key_stores_plaintext(self, app, client):
        """生成的密钥应落库明文，供事后查看。"""
        client.post("/login", data={"username": "admin", "password": "admin123"})
        key_id, raw_key = self._gen_key(app, name="store-pt")
        resp = client.get(f"/api-keys/{key_id}/reveal")
        assert resp.status_code == 200
        assert resp.get_json()["api_key"] == raw_key

    def test_list_page_no_plaintext_preembedded(self, app, client):
        """列表页不预埋明文，仅展示前缀。"""
        client.post("/login", data={"username": "admin", "password": "admin123"})
        _, raw_key = self._gen_key(app, name="masked")
        html = client.get("/api-keys").data.decode("utf-8")
        assert raw_key not in html

    def test_reveal_records_audit(self, app, client):
        client.post("/login", data={"username": "admin", "password": "admin123"})
        key_id, _ = self._gen_key(app, name="audit")
        client.get(f"/api-keys/{key_id}/reveal")
        from geo_optimizer.web.portal.models import AuditLog
        with app.app_context():
            assert AuditLog.query.filter_by(action="api_key_reveal").first() is not None

    def test_legacy_key_without_plaintext_404(self, app, client):
        """历史密钥（未落明文）查看返回 404 与提示。"""
        client.post("/login", data={"username": "admin", "password": "admin123"})
        key_id, _ = self._gen_key(app, name="legacy")
        from geo_optimizer.web.portal.extensions import db
        from geo_optimizer.web.portal.models import ApiKey
        with app.app_context():
            key = db.session.get(ApiKey, key_id)
            key.key_plaintext = None  # 模拟历史密钥
            db.session.commit()
        resp = client.get(f"/api-keys/{key_id}/reveal")
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "no_plaintext"

    def test_cannot_reveal_other_user_key(self, app, client):
        from geo_optimizer.web.portal.auth.service import create_user
        client.post("/login", data={"username": "admin", "password": "admin123"})
        key_id, _ = self._gen_key(app, name="owner")
        client.post("/logout")
        with app.app_context():
            create_user("intruder_k", "pass123", eval_quota=5)
        client.post("/login", data={"username": "intruder_k", "password": "pass123"})
        assert client.get(f"/api-keys/{key_id}/reveal").status_code == 404


# ─── API 文档页面测试 ──────────────────────────────────────────────────────────


class TestApiDocsPage:
    def test_api_docs_accessible(self, client):
        client.post("/login", data={"username": "admin", "password": "admin123"})
        resp = client.get("/api-docs")
        assert resp.status_code == 200
        assert b"/api/v1/tasks" in resp.data


# ─── 算力不可用测试 ──────────────────────────────────────────────────────────────


class TestLlmUnavailable:
    def test_submit_without_llm_returns_503(self, app, client, auth_header):
        """用户无可用算力时提交任务应返回 503 llm_unavailable。"""
        from unittest.mock import patch

        with patch(
            "geo_optimizer.web.portal.api.routes.user_has_available_llm",
            return_value=False,
        ):
            resp = client.post(
                "/api/v1/tasks",
                headers=auth_header,
                json={"target_url": "https://example.com", "task_type": "plan"},
            )
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["error"] == "llm_unavailable"
        assert "算力接口不可用" in data["message"]
        assert "geo_" in data["message"]  # 包含 key_prefix

    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_submit_with_llm_succeeds(self, mock_start, client, auth_header):
        """有可用算力时正常提交。"""
        resp = client.post(
            "/api/v1/tasks",
            headers=auth_header,
            json={"target_url": "https://example.com"},
        )
        assert resp.status_code == 201


# ─── Skill 导出测试 ──────────────────────────────────────────────────────────────


class TestSkillExport:
    def test_export_skill_returns_zip(self, app, client):
        """导出 Skill 应返回 ZIP 文件。"""
        import zipfile
        import io

        client.post("/login", data={"username": "admin", "password": "admin123"})
        from geo_optimizer.web.portal.api.auth import generate_api_key
        from geo_optimizer.web.portal.models import User

        with app.app_context():
            user = User.query.filter_by(username="admin").first()
            api_key, raw_key = generate_api_key(user.id, name="skill-export")
            key_id = api_key.id

        resp = client.post(
            f"/api-keys/{key_id}/export-skill",
            data={"raw_key": raw_key},
        )
        assert resp.status_code == 200
        assert "zip" in resp.content_type

        # 导出包命名格式: geo-用户名-时间戳.zip
        import re
        disposition = resp.headers.get("Content-Disposition", "")
        assert re.search(r"geo-admin-\d{14}\.zip", disposition), disposition

        # 验证 ZIP 内容符合 ClawHub skill 规范（根目录名与 frontmatter name 一致）
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        names = zf.namelist()
        assert "geo-optimizer/SKILL.md" in names
        assert "geo-optimizer/.clawhubignore" in names
        assert "geo-optimizer/config.json" in names
        # 客户端拆分为多模块（单文件≤300行），全部打包进 scripts/
        assert "geo-optimizer/scripts/geo_skill_client.py" in names
        assert "geo-optimizer/scripts/geo_skill_api.py" in names
        assert "geo-optimizer/scripts/geo_skill_common.py" in names

        # SKILL.md frontmatter 声明 ClawHub 运行时元数据，且必须是合法 YAML
        # （非法 YAML 会导致导入平台报“缺少 YAML 头部信息块”）
        import yaml
        skill_md = zf.read("geo-optimizer/SKILL.md").decode("utf-8")
        assert skill_md.startswith("---")
        front = yaml.safe_load(skill_md.split("---", 2)[1])
        assert front["name"] == "geo-optimizer"
        assert front["version"]
        assert front["description"]
        assert "openclaw:" in skill_md
        assert "primaryEnv: GEO_API_KEY" in skill_md

        # 描述支持提示词直接评估网站（如“请评估网站 www.example.com”）
        assert "请评估网站" in skill_md
        assert "Prompt Triggers" in skill_md

        # .clawhubignore 排除 config.json，防止发布时泄露密钥
        assert "config.json" in zf.read("geo-optimizer/.clawhubignore").decode("utf-8")

        # 验证 config.json 包含明文密钥与默认轮询间隔
        import json
        config = json.loads(zf.read("geo-optimizer/config.json"))
        assert config["api_key"] == raw_key
        assert config["key_prefix"] == api_key.key_prefix
        assert config["poll_interval"] == 6
        # key_name 用当前登录用户名填充（便于识别归属）
        assert config["key_name"] == "admin"

    def test_export_mcp_returns_zip(self, app, client):
        """导出 MCP 应返回 ZIP：含 mcp_server 包、config.json、mcp-config.json、README。"""
        import zipfile
        import io
        import json
        import re

        client.post("/login", data={"username": "admin", "password": "admin123"})
        from geo_optimizer.web.portal.api.auth import generate_api_key
        from geo_optimizer.web.portal.models import User

        with app.app_context():
            user = User.query.filter_by(username="admin").first()
            api_key, raw_key = generate_api_key(user.id, name="mcp-export")
            key_id = api_key.id

        resp = client.post(f"/api-keys/{key_id}/export-mcp", data={"raw_key": raw_key})
        assert resp.status_code == 200
        assert "zip" in resp.content_type

        # 导出包命名格式: geo-mcp-用户名-时间戳.zip
        disposition = resp.headers.get("Content-Disposition", "")
        assert re.search(r"geo-mcp-admin-\d{14}\.zip", disposition), disposition

        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        names = zf.namelist()
        # MCP 服务端 6 个模块全部打包进 mcp_server/
        for mod in ("__init__.py", "__main__.py", "server.py",
                    "api_client.py", "config.py", "formatting.py"):
            assert f"geo-optimizer-mcp/mcp_server/{mod}" in names
        assert "geo-optimizer-mcp/config.json" in names
        assert "geo-optimizer-mcp/mcp-config.json" in names
        assert "geo-optimizer-mcp/README.md" in names
        assert "geo-optimizer-mcp/requirements.txt" in names

        # config.json 注入明文密钥（与 skill 同一把），key_name 用登录用户名
        config = json.loads(zf.read("geo-optimizer-mcp/config.json"))
        assert config["api_key"] == raw_key
        assert config["key_prefix"] == api_key.key_prefix
        assert config["key_name"] == "admin"

        # mcp-config.json 是 stdio 模式的 mcpServers 片段，env 注入同一密钥
        mcp_config = json.loads(zf.read("geo-optimizer-mcp/mcp-config.json"))
        server = mcp_config["mcpServers"]["geo-optimizer"]
        assert server["args"] == ["-m", "mcp_server", "--transport", "stdio"]
        assert server["env"]["GEO_API_KEY"] == raw_key

        # requirements.txt 声明 MCP SDK v2 依赖
        reqs = zf.read("geo-optimizer-mcp/requirements.txt").decode("utf-8")
        assert "mcp[cli]>=2.1" in reqs

    def test_export_mcp_shares_key_with_skill(self, app, client):
        """同一密钥分别导出 Skill 与 MCP，两者 config.json 的 api_key 必须一致（共用一把）。"""
        import zipfile
        import io
        import json

        client.post("/login", data={"username": "admin", "password": "admin123"})
        from geo_optimizer.web.portal.api.auth import generate_api_key
        from geo_optimizer.web.portal.models import User

        with app.app_context():
            user = User.query.filter_by(username="admin").first()
            api_key, raw_key = generate_api_key(user.id, name="shared-key")
            key_id = api_key.id

        # 均不传表单 raw_key，走 key.key_plaintext 回退路径
        skill_resp = client.post(f"/api-keys/{key_id}/export-skill")
        mcp_resp = client.post(f"/api-keys/{key_id}/export-mcp")
        assert skill_resp.status_code == 200
        assert mcp_resp.status_code == 200

        skill_cfg = json.loads(zipfile.ZipFile(io.BytesIO(skill_resp.data)).read("geo-optimizer/config.json"))
        mcp_cfg = json.loads(zipfile.ZipFile(io.BytesIO(mcp_resp.data)).read("geo-optimizer-mcp/config.json"))
        # 共用同一把密钥
        assert skill_cfg["api_key"] == mcp_cfg["api_key"] == raw_key

    def test_export_skill_without_raw_key(self, app, client):
        """历史密钥（未落明文）且不传 raw_key 时，自动重生成并默认写入可用密钥。"""
        import zipfile
        import io
        import json

        client.post("/login", data={"username": "admin", "password": "admin123"})
        from geo_optimizer.web.portal.api.auth import generate_api_key
        from geo_optimizer.web.portal.models import User

        with app.app_context():
            user = User.query.filter_by(username="admin").first()
            api_key, _ = generate_api_key(user.id, name="no-raw")
            key_id = api_key.id

        # 模拟历史密钥：清除落库明文
        from geo_optimizer.web.portal.extensions import db
        from geo_optimizer.web.portal.models import ApiKey
        with app.app_context():
            key = db.session.get(ApiKey, key_id)
            key.key_plaintext = None
            db.session.commit()

        resp = client.post(f"/api-keys/{key_id}/export-skill", data={})
        assert resp.status_code == 200

        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        config = json.loads(zf.read("geo-optimizer/config.json"))
        # 不再是占位符：导出时原地重生成，默认写入可用密钥
        assert config["api_key"].startswith("geo_")

        # 重生成后新明文已落库，且 config 与落库一致、前缀匹配
        with app.app_context():
            key = db.session.get(ApiKey, key_id)
            assert key.key_plaintext == config["api_key"]
            assert config["key_prefix"] == key.key_prefix

    def test_export_skill_uses_stored_plaintext(self, app, client):
        """不传 raw_key 但有落库明文时，config 使用落库明文。"""
        import zipfile
        import io
        import json

        client.post("/login", data={"username": "admin", "password": "admin123"})
        from geo_optimizer.web.portal.api.auth import generate_api_key
        from geo_optimizer.web.portal.models import User

        with app.app_context():
            user = User.query.filter_by(username="admin").first()
            api_key, raw_key = generate_api_key(user.id, name="stored-pt")
            key_id = api_key.id

        resp = client.post(f"/api-keys/{key_id}/export-skill", data={})
        assert resp.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        config = json.loads(zf.read("geo-optimizer/config.json"))
        assert config["api_key"] == raw_key

    def test_export_skill_other_user_404(self, app, client):
        """不能导出他人密钥的 Skill。"""
        client.post("/login", data={"username": "admin", "password": "admin123"})
        # 使用不存在的 key_id
        resp = client.post("/api-keys/99999/export-skill", data={})
        assert resp.status_code == 404
