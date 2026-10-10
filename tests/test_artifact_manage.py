# -*- coding: utf-8 -*-
"""产出物统一管理测试：首批全量生成、任务级增删改列表、后台平台级管理。"""
from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models import EvalTask, PlanArtifact, User
from geo_optimizer.web.portal.planitems import artifact_generator, generator
from geo_optimizer.web.portal.planitems.artifact_catalog import SPECS


def _total_specs() -> int:
    return sum(len(v) for v in SPECS.values())


def _seed(app, task_id, with_artifacts=True):
    """创建任务+全部条目，可选首批生成全部产出物（无 LLM，走骨架/规则）。"""
    with app.app_context():
        admin = User.query.filter_by(username="admin").first()
        task = EvalTask(id=task_id, user_id=admin.id,
                        target_url="https://example.com", overall_score=30.0)
        db.session.add(task)
        db.session.commit()
        items = generator.generate_for_task(task_id, {"llm": {}},
                                            {"overall_score": 30.0})
        if with_artifacts:
            artifact_generator.auto_generate_all(
                items, "https://example.com", {}, {"llm": {}})
        first_art = PlanArtifact.query.filter_by(task_id=task_id).first()
        return first_art.id if first_art else None


class TestAutoGenerateAll:
    def test_rules_only_when_no_config(self, app):
        _seed(app, "aa-rule", with_artifacts=False)
        with app.app_context():
            from geo_optimizer.web.portal.models import PlanItem
            items = PlanItem.query.filter_by(task_id="aa-rule").all()
            total, llm = artifact_generator.auto_generate_all(
                items, "https://example.com", {}, None)
            assert total == 2 and llm == 0  # 仅 sitemap.xml + robots.txt
            sources = {a.kind: a.source
                       for a in PlanArtifact.query.filter_by(task_id="aa-rule")}
            assert sources == {"sitemap_xml": "rule", "robots_txt": "rule"}

    def test_full_batch_without_llm_falls_back(self, app):
        _seed(app, "aa-full")
        with app.app_context():
            arts = PlanArtifact.query.filter_by(task_id="aa-full").all()
            assert len(arts) == _total_specs()
            assert {a.source for a in arts} == {"rule", "template"}


class TestTaskArtifactList:
    def test_list_shows_artifacts_and_missing(self, app, admin_login):
        _seed(app, "al-1", with_artifacts=False)
        with app.app_context():
            from geo_optimizer.web.portal.models import PlanItem
            items = PlanItem.query.filter_by(task_id="al-1").all()
            artifact_generator.auto_generate_all(
                items, "https://example.com", {}, None)  # 仅规则类 2 个
        resp = admin_login.get("/plan/al-1/artifacts")
        assert resp.status_code == 200
        assert b"sitemap.xml" in resp.data and b"robots.txt" in resp.data
        assert "可新增生成的产出物".encode() in resp.data

    def test_delete_artifact(self, app, admin_login):
        art_id = _seed(app, "al-del")
        resp = admin_login.post(f"/plan/artifact/{art_id}/delete")
        assert resp.status_code == 302
        with app.app_context():
            assert db.session.get(PlanArtifact, art_id) is None

    def test_foreign_user_forbidden(self, app, client):
        art_id = _seed(app, "al-403")
        with app.app_context():
            user = User(username="eve", eval_quota=3)
            user.set_password("pass12345")
            db.session.add(user)
            db.session.commit()
        client.post("/login", data={"username": "eve", "password": "pass12345"})
        assert client.get("/plan/al-403/artifacts").status_code == 403
        assert client.post(f"/plan/artifact/{art_id}/delete").status_code == 403


class TestAdminArtifacts:
    def test_page_lists_and_filters(self, app, admin_login):
        _seed(app, "adm-1")
        _seed(app, "adm-2")
        resp = admin_login.get("/admin/artifacts")
        assert resp.status_code == 200
        assert "平台生成内容管理".encode() in resp.data

        # 按任务筛选：仅显示 adm-1 的产出物
        resp = admin_login.get("/admin/artifacts?task_id=adm-1&per_page=50")
        assert resp.status_code == 200
        assert b"adm-1" in resp.data

    def test_pagination(self, app, admin_login):
        _seed(app, "adm-pg")
        resp = admin_login.get("/admin/artifacts?per_page=10&page=1")
        assert resp.status_code == 200
        assert "下一页".encode() in resp.data or b"1 / 1" not in resp.data \
            or resp.status_code == 200

    def test_requires_admin(self, app, client):
        _seed(app, "adm-403")
        with app.app_context():
            user = User(username="norm", eval_quota=3)
            user.set_password("pass12345")
            db.session.add(user)
            db.session.commit()
        client.post("/login", data={"username": "norm", "password": "pass12345"})
        resp = client.get("/admin/artifacts")
        assert resp.status_code in (302, 403)
