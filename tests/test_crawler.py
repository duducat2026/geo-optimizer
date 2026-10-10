# -*- coding: utf-8 -*-
"""爬虫测试：URL 规范化/链接提取等纯函数 + 重埋点站点（腾讯云）真实抓取回归。"""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from geo_optimizer.crawler import GEOCrawler  # noqa: E402


class TestPureFunctions:
    def test_normalize_url(self):
        assert GEOCrawler._normalize_url("https://A.com") == "https://a.com/"
        assert GEOCrawler._normalize_url("https://a.com/x#frag") == "https://a.com/x"

    def test_extract_links_same_domain_only(self):
        html = ('<a href="/about">a</a><a href="https://other.com/x">b</a>'
                '<a href="mailto:a@b.com">c</a><a href="https://a.com/p?q=1">d</a>')
        links = GEOCrawler._extract_links(html, "https://a.com/")
        assert "https://a.com/about" in links
        assert "https://a.com/p?q=1" in links
        assert all("other.com" not in l for l in links)
        assert all("mailto" not in l for l in links)

    def test_extract_text_and_headings(self):
        html = "<script>x=1</script><h1>标题</h1><p>正文 内容</p><style>.a{}</style>"
        text = GEOCrawler._extract_text_from_html(html)
        assert "x=1" not in text and "正文 内容" in text
        assert GEOCrawler._extract_headings(html) == [(1, "标题")]

    def test_default_wait_until_is_domcontentloaded(self):
        crawler = GEOCrawler({})
        assert crawler.wait_until == "domcontentloaded"
        assert crawler.settle_ms == 3000


class TestHeavyTelemetrySite:
    """回归：腾讯云首页因持续埋点请求，networkidle 会超时，修复后应可抓取。"""

    @pytest.mark.integration
    def test_crawl_tencent_cloud(self):
        config = {"target": {"url": "https://cloud.tencent.com.cn/",
                             "max_pages": 1, "crawl_depth": 0},
                  "playwright": {"timeout_ms": 30000,
                                 "wait_until": "domcontentloaded",
                                 "settle_ms": 3000}}
        pages = asyncio.run(GEOCrawler(config).crawl())
        assert pages, "腾讯云首页抓取失败（修复回归）"
        assert pages[0].title
        assert pages[0].word_count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
