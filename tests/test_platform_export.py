# -*- coding: utf-8 -*-
"""按平台导出 Skill/MCP 变体包的单元测试与路由测试。"""
import io
import json
import re
import zipfile

import pytest


# ─── 单元测试：变体构建 ──────────────────────────────────────────────────────


def _zip_entries(data: bytes):
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert zf.testzip() is None
        return sorted(zf.namelist())


def _zip_read(data: bytes, name: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return zf.read(name)


class TestSkillVariants:
    def test_modelscope_matches_source(self):
        from pathlib import Path

        from geo_optimizer.web.portal.user import platform_export as pe

        data = pe.build_skill_zip("modelscope")
        assert _zip_entries(data) == ["SKILL.md"] + [
            f"scripts/{n}" for n in sorted(pe.SCRIPT_FILES)]
        src = Path("docs/geo-skill/SKILL.md").read_text(encoding="utf-8")
        assert _zip_read(data, "SKILL.md").decode("utf-8") == src

    @pytest.mark.parametrize("platform", ["qianwen", "bailian"])
    def test_qianwen_compliant_frontmatter(self, platform):
        from geo_optimizer.web.portal.user import platform_export as pe

        data = pe.build_skill_zip(platform)
        fm = pe.frontmatter_of(_zip_read(data, "SKILL.md").decode("utf-8"))
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", fm["name"])
        assert len(fm["name"]) <= 64
        desc = fm["description"]
        assert "<" not in desc and ">" not in desc
        assert len(desc) <= 1024

    def test_workbuddy_extra_fields(self):
        from geo_optimizer.web.portal.user import platform_export as pe

        data = pe.build_skill_zip("workbuddy")
        fm = pe.frontmatter_of(_zip_read(data, "SKILL.md").decode("utf-8"))
        for key, expected in pe.WORKBUDDY_FIELDS.items():
            assert fm.get(key) == expected, f"字段 {key} 不符: {fm.get(key)!r}"

    def test_no_plaintext_key_in_variants(self):
        from geo_optimizer.web.portal.user import platform_export as pe

        full_key = re.compile(r"geo_[A-Za-z0-9_-]{20,}")
        for platform in pe.SUPPORTED_PLATFORMS:
            data = pe.build_skill_zip(platform)
            assert "config.json" not in _zip_entries(data)
            assert not full_key.search(_zip_read(data, "SKILL.md").decode("utf-8"))

    def test_invalid_platform_raises(self):
        from geo_optimizer.web.portal.user import platform_export as pe

        with pytest.raises(ValueError):
            pe.build_skill_zip("clawhub")
        with pytest.raises(ValueError):
            pe.build_mcp_zip("")

    def test_zip_name_pattern(self):
        from geo_optimizer.web.portal.user import platform_export as pe

        assert re.fullmatch(r"geoskill-(modelscope|qianwen|bailian|workbuddy)-\d{8}\.zip",
                            pe.zip_name("modelscope"))


class TestMcpVariants:
    def test_modelscope_package(self):
        from geo_optimizer.web.portal.user import platform_export as pe

        data = pe.build_mcp_zip("modelscope")
        assert sorted(_zip_entries(data)) == ["config.json", "icon.svg", "readme.md"]
        cfg = json.loads(_zip_read(data, "config.json"))
        server = cfg["mcpServers"]["geo-optimizer"]
        assert server["url"] == pe.MCP_ENDPOINT
        assert server["headers"]["Authorization"] == "Bearer ${GEO_API_KEY}"

    @pytest.mark.parametrize("platform", ["qianwen", "bailian"])
    def test_qianwen_package(self, platform):
        from geo_optimizer.web.portal.user import platform_export as pe

        data = pe.build_mcp_zip(platform)
        assert _zip_entries(data) == ["config.json"]
        cfg = json.loads(_zip_read(data, "config.json"))
        server = cfg["mcpServers"]["geo-optimizer"]
        assert server["type"] == "streamableHttp"
        assert server["url"] == pe.MCP_ENDPOINT

    def test_workbuddy_connector_five_pieces(self):
        from geo_optimizer.web.portal.user import platform_export as pe

        data = pe.build_mcp_zip("workbuddy")
        entries = _zip_entries(data)
        for required in ("connector-meta.json", "mcp.json", "icon.svg",
                         "token-schema.json", "skills/geo-optimizer/SKILL.md"):
            assert required in entries, f"缺少 {required}"
        # 关键 JSON 均可解析
        for name in ("connector-meta.json", "mcp.json", "token-schema.json"):
            json.loads(_zip_read(data, name))
        meta = json.loads(_zip_read(data, "connector-meta.json"))
        assert meta["description_zh"] and meta["description_en"]

    def test_no_plaintext_key_anywhere(self):
        from geo_optimizer.web.portal.user import platform_export as pe

        full_key = re.compile(r"geo_[A-Za-z0-9_-]{20,}")
        for platform in pe.SUPPORTED_PLATFORMS:
            data = pe.build_mcp_zip(platform)
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for info in zf.infolist():
                    if info.filename.endswith((".json", ".md")):
                        text = zf.read(info).decode("utf-8", "ignore")
                        assert not full_key.search(text), f"{platform}/{info.filename} 含明文密钥"


# ─── 路由测试：/export-skill 与 /export-mcp 的 platform 参数 ─────────────────


@pytest.fixture()
def key_id(client, app):
    """登录 admin 并生成一把带明文的密钥，返回 (key_id, 明文)。"""
    client.post("/login", data={"username": "admin", "password": "admin123"})
    from geo_optimizer.web.portal.api.auth import generate_api_key
    from geo_optimizer.web.portal.models import User

    with app.app_context():
        user = User.query.filter_by(username="admin").first()
        api_key, raw_key = generate_api_key(user.id, name="export-test")
        return api_key.id, raw_key


def _filename(resp) -> str:
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)\"?", cd)
    return m.group(1) if m else ""


class TestExportRoutes:
    @pytest.mark.parametrize("platform", ["modelscope", "qianwen", "bailian", "workbuddy"])
    def test_export_skill_variant(self, client, key_id, platform):
        kid, _ = key_id
        resp = client.post(f"/api-keys/{kid}/export-skill", data={"platform": platform})
        assert resp.status_code == 200
        assert re.match(rf"geoskill-{platform}-\d{{8}}\.zip", _filename(resp))
        with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
            assert "config.json" not in zf.namelist()

    @pytest.mark.parametrize("platform", ["modelscope", "qianwen", "workbuddy"])
    def test_export_mcp_variant(self, client, key_id, platform):
        kid, _ = key_id
        resp = client.post(f"/api-keys/{kid}/export-mcp", data={"platform": platform})
        assert resp.status_code == 200
        assert re.match(rf"geoskill-{platform}-\d{{8}}\.zip", _filename(resp))

    def test_export_skill_invalid_platform_400(self, client, key_id):
        kid, _ = key_id
        assert client.post(f"/api-keys/{kid}/export-skill",
                           data={"platform": "bogus"}).status_code == 400
        assert client.post(f"/api-keys/{kid}/export-mcp",
                           data={"platform": "bogus"}).status_code == 400

    def test_export_generic_keeps_plaintext_key(self, client, key_id):
        kid, raw = key_id
        resp = client.post(f"/api-keys/{kid}/export-skill", data={})
        assert resp.status_code == 200
        with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
            cfg = json.loads(zf.read("geo-optimizer/config.json"))
        assert cfg["api_key"] == raw

    def test_variant_export_does_not_regenerate(self, client, app, key_id):
        """平台变体导出不触碰密钥（不重生成、不改明文）。"""
        from geo_optimizer.web.portal.extensions import db
        from geo_optimizer.web.portal.models import ApiKey

        kid, raw = key_id
        client.post(f"/api-keys/{kid}/export-skill", data={"platform": "modelscope"})
        with app.app_context():
            assert db.session.get(ApiKey, kid).key_plaintext == raw

    def test_variant_uses_public_endpoint(self, client):
        """变体包中的服务地址固定为云端公开域名而非本地导出来源。"""
        from geo_optimizer.web.portal.user import platform_export as pe

        assert pe.MCP_ENDPOINT == "https://geo.tool.jiuchongju.com/mcp"
