# -*- coding: utf-8 -*-
"""portal 测试共享 fixture：SQLite 内存库 + app factory。"""
import pytest


@pytest.fixture()
def app(monkeypatch, tmp_path):
    """基于 SQLite 的测试应用（不依赖 MySQL）。"""
    from geo_optimizer.web.portal import settings as deploy_settings

    db_file = tmp_path / "portal_test.db"
    monkeypatch.setattr(deploy_settings, "sqlalchemy_uri", lambda: f"sqlite:///{db_file}")

    # 测试中不启动日志清理/任务监控后台线程
    from geo_optimizer.web.portal.tasks import log_cleaner, task_monitor

    monkeypatch.setattr(log_cleaner, "start", lambda app: None)
    monkeypatch.setattr(task_monitor, "start", lambda app: None)

    from geo_optimizer.web.portal.app import create_app

    application = create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def admin_login(client):
    """以默认管理员登录后的 client。"""
    client.post("/login", data={"username": "admin", "password": "admin123"})
    return client
