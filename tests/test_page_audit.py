# -*- coding: utf-8 -*-
"""page_audit 页面技术体检测试（合成 CrawledPage，不依赖网络）。"""
from geo_optimizer.models import CrawledPage
from geo_optimizer.page_audit import GAIN, SEVERITY, audit_page


def _page(**overrides) -> CrawledPage:
    base = dict(
        url="https://example.com/",
        title="Example",
        html="<html><body></body></html>",
        text="",
        language="zh",
        meta_desc="",
        meta_keywords="",
        headings=[],
        links=[],
        word_count=0,
        images=[],
    )
    base.update(overrides)
    return CrawledPage(**base)


def _check(result: dict, key: str) -> dict:
    return next(c for c in result["checks"] if c["key"] == key)


class TestChecks:
    def test_good_page_all_pass(self):
        html = (
            '<html><script type="application/ld+json">{}</script>'
            "<h1>T</h1><ul></ul><ul></ul><ul></ul>"
            "<p>FAQ 常见问题 author 发布于</p></html>"
        )
        page = _page(
            html=html,
            text="常见问题 " + "内容" * 500 + " 2024-05-01",
            meta_desc="一段描述",
            headings=[(1, "T"), (2, "A"), (3, "B")],
            images=[{"alt": "logo"}],
            links=["https://example.com/a", "/b"],
            word_count=800,
        )
        result = audit_page(page, crawl_ms=1200, overall_score=60.0)
        assert result["issues"] == []
        assert result["priorities"] == []
        for key in SEVERITY:
            assert _check(result, key)["ok"], key
        # 统计推导优势
        assert "content_volume" in result["strengths"]
        assert "rich_lists" in result["strengths"]
        assert "fast_load" in result["strengths"]
        assert result["stats"]["crawl_ms"] == 1200
        assert result["stats"]["internal_links"] == 2

    def test_bad_page_all_fail(self):
        page = _page(
            url="http://example.com/",
            images=[{"alt": ""}, {"alt": "x"}],
        )
        result = audit_page(page)
        failed = set(result["issues"])
        assert failed == set(SEVERITY.keys())
        assert _check(result, "img_alt")["value"] == "1/2"

    def test_priorities_red_first(self):
        page = _page(url="http://example.com/")
        result = audit_page(page)
        sevs = [SEVERITY[k] for k in result["priorities"]]
        order = {"red": 0, "yellow": 1, "green": 2}
        assert sevs == sorted(sevs, key=order.get)
        assert sevs[0] == "red" and sevs[-1] == "green"

    def test_headings_require_h1(self):
        page = _page(headings=[(2, "A"), (2, "B"), (3, "C")])
        result = audit_page(page)
        assert not _check(result, "headings")["ok"]

    def test_no_images_alt_ok(self):
        result = audit_page(_page(images=[]))
        assert _check(result, "img_alt")["ok"]


class TestEstimate:
    def test_estimate_range(self):
        page = _page(url="http://example.com/")
        result = audit_page(page, overall_score=30.0)
        est = result["estimate"]
        # 无图片时 img_alt 视为通过，gain 按实际失败项累加
        gain = sum(GAIN[SEVERITY[k]] for k in result["issues"])
        assert est["gain"] == gain
        assert 30.0 <= est["min"] <= est["max"] <= 95.0

    def test_estimate_capped(self):
        page = _page(url="http://example.com/")
        result = audit_page(page, overall_score=88.0)
        assert result["estimate"]["min"] <= 90.0
        assert result["estimate"]["max"] <= 95.0

    def test_no_score_no_estimate(self):
        assert "estimate" not in audit_page(_page())
