# -*- coding: utf-8 -*-
"""改进方案条目：catalog 完整性 / 模板兜底 / 路由权限 / 编辑与下载。"""
import io
import zipfile

from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models import EvalTask, PlanItem, User
from geo_optimizer.web.portal.planitems import generator
from geo_optimizer.web.portal.planitems.catalog import ITEMS, get_item


class TestCatalog:
    def test_item_count(self):
        assert len(ITEMS) == 13
        assert len({i["code"] for i in ITEMS}) == 13

    def test_priority_distribution(self):
        counts = {"high": 0, "mid": 0, "low": 0}
        for item in ITEMS:
            counts[item["priority"]] += 1
        assert counts == {"high": 5, "mid": 5, "low": 3}

    def test_bilingual_and_steps(self):
        for item in ITEMS:
            assert item["title"]["zh"] and item["title"]["en"]
            assert item["goal"]["zh"] and item["goal"]["en"]
            assert item["steps"], item["code"]
            for step in item["steps"]:
                assert step["zh"] and step["en"]

    def test_engines_field(self):
        """每项均声明适配模型，sitemap 覆盖全部 11 引擎。"""
        for item in ITEMS:
            assert item.get("engines"), f"{item['code']} missing engines"
        sitemap = get_item("sitemap_optimize")
        assert len(sitemap["engines"]) == 11

    def test_get_item(self):
        assert get_item("baidu_webmaster")["priority"] == "high"
        assert get_item("__nope__") is None


class TestFallbackTemplate:
    def test_render_fallback(self):
        spec = ITEMS[0]
        ctx = {"url": "https://example.com", "domain": "example.com",
               "score": 29.0, "issues": "HTTPS"}
        zh_text, en_text = generator.render_fallback(spec, ctx)
        assert spec["title"]["zh"] in zh_text
        assert spec["title"]["en"] in en_text
        assert "https://example.com" in zh_text and "https://example.com" in en_text
        assert "1. " in zh_text and "验收标准" in zh_text
        assert "1. " in en_text and "## Acceptance" in en_text
        # 两段各自单语：中文稿不含英文小节标题，反之亦然
        assert "## Acceptance" not in zh_text
        assert "验收标准" not in en_text


def _make_task(task_id="pt-1", user_id=None, score=29.0):
    task = EvalTask(id=task_id, user_id=user_id,
                    target_url="https://example.com", overall_score=score)
    db.session.add(task)
    db.session.commit()
    return task


class TestGenerateForTask:
    def test_no_llm_falls_back_to_template(self, app):
        """无 LLM 配置时全部条目走内置模板并落库。"""
        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            _make_task("pt-gen", admin.id)
            result = {"overall_score": 29.0,
                      "page_audit": {"issues": ["https", "schema"]}}
            items = generator.generate_for_task("pt-gen", {"llm": {}}, result)
            assert len(items) == 13
            assert all(i.source == "template" for i in items)
            assert PlanItem.query.filter_by(task_id="pt-gen").count() == 13

    def test_write_to_dir(self, app, tmp_path):
        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            _make_task("pt-dir", admin.id)
            items = generator.generate_for_task(
                "pt-dir", {"llm": {}}, {"overall_score": 40.0})
            out = tmp_path / "plan_items"
            generator.write_to_dir(items, out)
            files = sorted(p.name for p in out.glob("*.md"))
            # 每个条目中英两份
            assert len(files) == 26
            assert "high_baidu_webmaster.md" in files
            assert "high_baidu_webmaster.en.md" in files


def _seed_items(app, task_id="pt-web"):
    """以 admin 身份创建任务与全部条目，返回首个条目 id。"""
    with app.app_context():
        admin = User.query.filter_by(username="admin").first()
        _make_task(task_id, admin.id)
        items = generator.generate_for_task(
            task_id, {"llm": {}}, {"overall_score": 29.0})
        return items[0].id


class TestPlanRoutes:
    def test_item_list_and_edit_save(self, app, admin_login):
        item_id = _seed_items(app)
        resp = admin_login.get("/plan/pt-web")
        assert resp.status_code == 200
        assert "改进方案".encode() in resp.data

        resp = admin_login.post(f"/plan/item/{item_id}",
                                data={"content": "# 已编辑内容"})
        assert resp.status_code == 302
        with app.app_context():
            assert db.session.get(PlanItem, item_id).content == "# 已编辑内容"
            # 未提交 content_en 时保持原英文稿不变
            assert "Acceptance" in db.session.get(PlanItem, item_id).content_en

        resp = admin_login.post(f"/plan/item/{item_id}",
                                data={"content": "# 中", "content_en": "# EN"})
        assert resp.status_code == 302
        with app.app_context():
            item = db.session.get(PlanItem, item_id)
            assert (item.content, item.content_en) == ("# 中", "# EN")

    def test_item_download_uses_latest_content(self, app, admin_login):
        item_id = _seed_items(app, "pt-dl")
        admin_login.post(f"/plan/item/{item_id}", data={"content": "EDITED-MD"})
        resp = admin_login.get(f"/plan/item/{item_id}/download")
        assert resp.status_code == 200
        assert resp.data == b"EDITED-MD"
        assert ".md" in resp.headers["Content-Disposition"]

    def test_bundle_zip_download(self, app, admin_login):
        _seed_items(app, "pt-zip")
        resp = admin_login.get("/plan/pt-zip/download")
        assert resp.status_code == 200
        with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
            # 13 条 × 中英两份 + 根目录双语 README
            assert len(zf.namelist()) == 27
            assert "README.md" in zf.namelist()

    def test_foreign_item_forbidden(self, app, client):
        item_id = _seed_items(app, "pt-403")
        with app.app_context():
            user = User(username="mallory", eval_quota=3)
            user.set_password("pass12345")
            db.session.add(user)
            db.session.commit()
        client.post("/login", data={"username": "mallory",
                                    "password": "pass12345"})
        assert client.get("/plan/pt-403").status_code == 403
        assert client.get(f"/plan/item/{item_id}").status_code == 403
        assert client.get(f"/plan/item/{item_id}/download").status_code == 403

    def test_missing_returns_404(self, admin_login):
        assert admin_login.get("/plan/no-such-task").status_code == 404
        assert admin_login.get("/plan/item/99999").status_code == 404


class TestAnonymousDownload:
    """下载方案链接免登录（task_id 为 UUID，链接即凭证）。"""

    def test_bundle_download_without_login(self, app, client):
        _seed_items(app, "pt-anon")
        resp = client.get("/plan/pt-anon/download")
        assert resp.status_code == 200
        with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
            assert len(zf.namelist()) == 27   # 中英各 13 份 + README

    def test_eval_download_without_login(self, app, client, tmp_path):
        """任务详情页「下载方案」链接免登录可下。"""
        from geo_optimizer.web.portal.models import GeoPlan

        zip_path = tmp_path / "geo_plan_pt-anon-eval.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("report.md", "# report")

        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            _make_task("pt-anon-eval", admin.id)
            plan = GeoPlan(task_id="pt-anon-eval", user_id=admin.id,
                           target_url="https://example.com", zip_path=str(zip_path))
            db.session.add(plan)
            db.session.commit()

        resp = client.get("/eval/pt-anon-eval/download")
        assert resp.status_code == 200
        assert "zip" in resp.content_type

    def test_anonymous_download_unknown_task_404(self, client):
        assert client.get("/plan/no-such/download").status_code == 404
        assert client.get("/eval/no-such/download").status_code == 404

    def test_item_and_artifact_download_still_require_login(self, app, client):
        """自增 id 的单条目/产出物下载仍需登录（可枚举，不公开）。"""
        item_id = _seed_items(app, "pt-keep-auth")
        resp = client.get(f"/plan/item/{item_id}/download")
        assert resp.status_code == 302  # 重定向登录页


class TestDownloadLimit:
    """分享链接单链接下载次数限制（系统配置 download_limit，默认 20）。"""

    @staticmethod
    def _set_limit(app, value):
        from geo_optimizer.web.portal.models import SystemConfig
        with app.app_context():
            SystemConfig.set("download_limit", str(value))
            db.session.commit()

    def test_anonymous_download_blocked_after_limit(self, app, client):
        self._set_limit(app, 2)
        _seed_items(app, "pt-limit")
        assert client.get("/plan/pt-limit/download").status_code == 200
        assert client.get("/plan/pt-limit/download").status_code == 200
        # 第 3 次超限
        assert client.get("/plan/pt-limit/download").status_code == 403
        with app.app_context():
            task = db.session.get(EvalTask, "pt-limit")
            assert task.bundle_download_count == 2

    def test_owner_download_not_counted(self, app, admin_login):
        """属主（管理员）下载不计数不受限。"""
        self._set_limit(app, 1)
        _seed_items(app, "pt-owner")
        assert admin_login.get("/plan/pt-owner/download").status_code == 200
        assert admin_login.get("/plan/pt-owner/download").status_code == 200
        with app.app_context():
            task = db.session.get(EvalTask, "pt-owner")
            assert task.bundle_download_count == 0

    def test_zero_means_unlimited(self, app, client):
        self._set_limit(app, 0)
        _seed_items(app, "pt-nolimit")
        for _i in range(3):
            assert client.get("/plan/pt-nolimit/download").status_code == 200

    def test_eval_download_limited_separately(self, app, client, tmp_path):
        """eval_download 与 bundle_download 各自独立计数。"""
        import zipfile as _zf
        from geo_optimizer.web.portal.models import GeoPlan

        self._set_limit(app, 1)
        zip_path = tmp_path / "geo_plan_pt-limit-eval.zip"
        with _zf.ZipFile(zip_path, "w") as zf:
            zf.writestr("report.md", "# report")
        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            _make_task("pt-limit-eval", admin.id)
            db.session.add(GeoPlan(task_id="pt-limit-eval", user_id=admin.id,
                                   target_url="https://example.com",
                                   zip_path=str(zip_path)))
            db.session.commit()
        assert client.get("/eval/pt-limit-eval/download").status_code == 200
        assert client.get("/eval/pt-limit-eval/download").status_code == 403
        with app.app_context():
            task = db.session.get(EvalTask, "pt-limit-eval")
            assert task.eval_download_count == 1
            assert task.bundle_download_count == 0

    def test_default_limit_is_20(self, app):
        """未配置时默认上限 20。"""
        from geo_optimizer.web.portal.tasks import service
        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            task = _make_task("pt-default-limit", admin.id)
            for _i in range(20):
                assert service.consume_download_quota(task, "bundle_download_count")
            assert not service.consume_download_quota(task, "bundle_download_count")
            assert task.bundle_download_count == 20

    def test_admin_can_update_limit_via_config_page(self, app, admin_login):
        """后台系统配置页可修改单链接下载次数上限。"""
        from geo_optimizer.web.portal.models import SystemConfig

        html = admin_login.get("/admin/config").data.decode()
        assert 'name="download_limit"' in html
        resp = admin_login.post("/admin/config", data={"download_limit": "5"})
        assert resp.status_code == 302
        with app.app_context():
            assert SystemConfig.get("download_limit") == "5"

