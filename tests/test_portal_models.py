# -*- coding: utf-8 -*-
"""portal 数据模型测试（SQLite 内存库）。"""
from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models import (
    ROLE_ADMIN,
    EvalTask,
    GeoPlan,
    SystemConfig,
    User,
)


class TestUserModel:
    def test_password_hashing(self, app):
        with app.app_context():
            user = User(username="alice", eval_quota=5)
            user.set_password("secret123")
            assert user.password_hash != "secret123"
            assert user.check_password("secret123")
            assert not user.check_password("wrong")

    def test_quota_left(self, app):
        from datetime import date
        with app.app_context():
            # 配额按自然日重置：今日计数需携带 quota_date
            user = User(username="bob", eval_quota=3, eval_used=1,
                        quota_date=date.today())
            assert user.quota_left == 2
            # 历史计数跨天后不再占用配额
            stale = User(username="bob2", eval_quota=3, eval_used=3)
            assert stale.quota_left == 3
            admin = User(username="root2", role=ROLE_ADMIN, eval_quota=0)
            assert admin.quota_left > 10000  # 管理员不限

    def test_seed_admin_exists(self, app):
        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            assert admin is not None
            assert admin.is_admin
            assert admin.check_password("admin123")


class TestSystemConfig:
    def test_set_and_get(self, app):
        with app.app_context():
            SystemConfig.set("model", "qwen-max")
            db.session.commit()
            assert SystemConfig.get("model") == "qwen-max"

    def test_llm_defaults_seeded(self, app):
        with app.app_context():
            assert SystemConfig.get("api_host", "") != ""
            assert "compatible-mode" in SystemConfig.get("openai_base_url", "")


class TestEvalTask:
    def test_result_roundtrip(self, app):
        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            task = EvalTask(id="t-1", user_id=admin.id, target_url="https://example.com")
            task.set_result({"overall_score": 66.5, "engine_scores": []})
            db.session.add(task)
            db.session.commit()

            loaded = db.session.get(EvalTask, "t-1")
            assert loaded.result()["overall_score"] == 66.5
            assert loaded.to_dict()["target_url"] == "https://example.com"

    def test_geo_plan_link(self, app):
        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            task = EvalTask(id="t-2", user_id=admin.id, target_url="https://example.com")
            db.session.add(task)
            db.session.commit()

            plan = GeoPlan(task_id="t-2", user_id=admin.id,
                           target_url="https://example.com", zip_path="/tmp/x.zip")
            db.session.add(plan)
            db.session.commit()
            assert GeoPlan.query.filter_by(task_id="t-2").count() == 1
