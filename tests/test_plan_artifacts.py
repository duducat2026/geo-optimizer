# -*- coding: utf-8 -*-
"""改进方案具体产出物测试：产出物目录一致性、sitemap/robots 规则生成、页面快照。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from geo_optimizer.web.portal.planitems import artifact_catalog  # noqa: E402
from geo_optimizer.web.portal.planitems.artifact_generator import (  # noqa: E402
    AI_BOTS,
    build_robots,
    build_sitemap,
)
from geo_optimizer.web.portal.planitems.catalog import ITEMS, get_item  # noqa: E402
from geo_optimizer.web.portal.tasks import snapshot  # noqa: E402


class TestArtifactCatalog:
    def test_specs_codes_exist_in_catalog(self):
        """产出物规格的条目 code 必须在条目目录中存在。"""
        for code in artifact_catalog.SPECS:
            assert get_item(code) is not None, f"{code} 不在 catalog.ITEMS 中"

    def test_llm_specs_have_instruction(self):
        for specs in artifact_catalog.SPECS.values():
            for spec in specs:
                assert spec["mode"] in ("rule", "llm")
                if spec["mode"] == "llm":
                    assert spec.get("instruction"), f"{spec['kind']} 缺少 instruction"
                assert spec["title"].get("zh") and spec["title"].get("en")

    def test_filenames_and_kinds_unique(self):
        kinds, files = [], []
        for specs in artifact_catalog.SPECS.values():
            for spec in specs:
                kinds.append(spec["kind"])
                files.append(spec["filename"])
        assert len(kinds) == len(set(kinds))
        assert len(files) == len(set(files))

    def test_get_spec(self):
        assert artifact_catalog.get_spec("sitemap_optimize", "sitemap_xml") is not None
        assert artifact_catalog.get_spec("sitemap_optimize", "nope") is None
        assert artifact_catalog.specs_for("unknown_code") == []


class TestNewCatalogItems:
    def test_new_items_present(self):
        codes = {item["code"] for item in ITEMS}
        assert {"faq_block", "authority_citation", "en_qa_community"} <= codes

    def test_authority_citation_targets_foreign_engines(self):
        item = get_item("authority_citation")
        assert item["priority"] == "mid"
        assert "Google AI Overviews" in item["engines"]
        assert "豆包" not in item["engines"]


class TestSitemapRobots:
    def test_sitemap_filters_and_dedupes(self):
        links = [
            "https://example.com/about",
            "https://example.com/about",          # 重复
            "https://example.com/about?utm=x",    # 去 query 后重复
            "https://other.com/page",             # 跨域
            "mailto:a@example.com",               # 非 http
        ]
        xml = build_sitemap("https://example.com/", links)
        assert xml.count("<loc>") == 2
        assert "<loc>https://example.com/</loc>" in xml
        assert "<loc>https://example.com/about</loc>" in xml
        assert "other.com" not in xml
        assert "<lastmod>" in xml

    def test_robots_allows_ai_bots_and_declares_sitemap(self):
        txt = build_robots("https://example.com/some/page")
        for bot in AI_BOTS:
            assert f"User-agent: {bot}" in txt
        assert "Sitemap: https://example.com/sitemap.xml" in txt


class TestSnapshot:
    def test_save_and_load_roundtrip(self, tmp_path=None):
        import tempfile

        class FakePage:
            url = "https://example.com/"
            title = "Example"
            language = "zh"
            meta_desc = "desc"
            meta_keywords = "kw"
            headings = [(1, "H1 标题"), (2, "H2 标题")]
            links = ["https://example.com/a"]
            word_count = 100
            text = "正文" * 10

        with tempfile.TemporaryDirectory() as d:
            snapshot.save_snapshot(d, FakePage())
            data = snapshot.load_snapshot(d)
            assert data["url"] == "https://example.com/"
            assert data["headings"] == [[1, "H1 标题"], [2, "H2 标题"]]
            assert data["text"].startswith("正文")

    def test_load_missing_returns_empty(self):
        assert snapshot.load_snapshot(None) == {}
        assert snapshot.load_snapshot("/nonexistent/path") == {}


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
