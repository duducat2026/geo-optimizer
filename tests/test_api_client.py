# -*- coding: utf-8 -*-
"""Python 客户端全流程测试：使用 Flask test_client 模拟服务端。"""
import json
import threading
from unittest.mock import patch

import pytest

import sys
from pathlib import Path

# 确保 client 目录可导入
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "client"))

from geo_api_client import GeoApiClient, GeoApiError


@pytest.fixture()
def api_key(app, client):
    """为管理员生成 API 密钥。"""
    client.post("/login", data={"username": "admin", "password": "admin123"})
    from geo_optimizer.web.portal.api.auth import generate_api_key
    from geo_optimizer.web.portal.models import User

    with app.app_context():
        user = User.query.filter_by(username="admin").first()
        _, raw_key = generate_api_key(user.id, name="client-test", expires_days=365)
    return raw_key


@pytest.fixture()
def live_server(app, api_key):
    """启动一个真实的本地 HTTP 服务器供客户端调用。"""
    import socket

    # 找可用端口
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    from werkzeug.serving import make_server

    server = make_server("127.0.0.1", port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://127.0.0.1:{port}", api_key

    server.shutdown()


class TestGeoApiClient:
    """使用真实 HTTP 服务器测试客户端全流程。"""

    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_full_flow(self, mock_start, live_server, tmp_path):
        """完整流程：提交 -> 查询 -> 获取结果 -> 统计。"""
        base_url, api_key = live_server

        with GeoApiClient(base_url, api_key) as client:
            # 1. 提交任务
            task_id = client.submit_task("https://example.com", task_type="plan")
            assert task_id
            assert isinstance(task_id, str)

            # 2. 查询状态
            status = client.get_task_status(task_id)
            assert status["task_id"] == task_id
            assert status["status"] == "pending"
            assert status["source"] == "api"

            # 3. 获取结果（未完成时）
            result = client.get_task_result(task_id)
            assert result["status"] == "pending"

            # 4. 用量统计
            usage = client.get_usage()
            assert usage["total_calls"] >= 3  # submit + status + result
            assert len(usage["keys"]) >= 1

    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_submit_and_poll(self, mock_start, live_server, app):
        """提交后手动标记完成，验证 wait_for_completion。"""
        base_url, api_key = live_server

        with GeoApiClient(base_url, api_key) as client:
            task_id = client.submit_task("https://example.com")

            # 模拟后台完成任务
            with app.app_context():
                from geo_optimizer.web.portal.extensions import db
                from geo_optimizer.web.portal.models import EvalTask
                task = db.session.get(EvalTask, task_id)
                task.status = "completed"
                task.progress = 100
                task.overall_score = 82.0
                task.set_result({"overall_score": 82.0, "url": "https://example.com"})
                db.session.commit()

            # wait_for_completion 应立即返回
            result = client.wait_for_completion(task_id, timeout=10, poll_interval=0.5)
            assert result["status"] == "completed"
            assert result["overall_score"] == 82.0

    def test_invalid_key_raises(self, live_server):
        """无效密钥应抛出 GeoApiError。"""
        base_url, _ = live_server
        with GeoApiClient(base_url, "geo_invalid_key") as client:
            with pytest.raises(GeoApiError) as exc_info:
                client.get_usage()
            assert exc_info.value.status_code == 401

    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_download_no_package(self, mock_start, live_server):
        """无下载包时应抛出 404 异常。"""
        base_url, api_key = live_server

        with GeoApiClient(base_url, api_key) as client:
            task_id = client.submit_task("https://example.com")
            with pytest.raises(GeoApiError) as exc_info:
                client.download(task_id, "/tmp/test_no_pkg.zip")
            assert exc_info.value.status_code == 404

    @patch("geo_optimizer.web.portal.api.routes.runner.start")
    def test_task_failed_raises(self, mock_start, live_server, app):
        """任务失败时 wait_for_completion 应抛出异常。"""
        base_url, api_key = live_server

        with GeoApiClient(base_url, api_key) as client:
            task_id = client.submit_task("https://example.com")

            # 模拟任务失败
            with app.app_context():
                from geo_optimizer.web.portal.extensions import db
                from geo_optimizer.web.portal.models import EvalTask
                task = db.session.get(EvalTask, task_id)
                task.status = "failed"
                task.error = "crawl failed"
                db.session.commit()

            with pytest.raises(GeoApiError) as exc_info:
                client.wait_for_completion(task_id, timeout=10, poll_interval=0.5)
            assert exc_info.value.error == "task_failed"
