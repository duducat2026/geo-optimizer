#!/usr/bin/env python3
"""
geo_crawler.py — 网站爬虫（Playwright 驱动，支持 JS 渲染）
"""

import hashlib
import logging
import os
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from geo_optimizer.models import CrawledPage

try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

logger = logging.getLogger(__name__)


class GEOCrawler:
    """GEO 网站爬虫"""

    def __init__(self, config: dict):
        self.config = config
        target = config.get("target", {})
        self.max_depth = target.get("crawl_depth", 3)
        self.max_pages = target.get("max_pages", 50)
        self.timeout_ms = config.get("playwright", {}).get("timeout_ms", 30000)
        self.headless = config.get("playwright", {}).get("headless", True)
        # 默认 domcontentloaded：重埋点站点（腾讯云/淘宝等）网络永不空闲，
        # networkidle 会直接超时导致抓取失败。
        self.wait_until = config.get("playwright", {}).get("wait_until", "domcontentloaded")
        # 主导航成功后，额外等待动态内容的短超时（毫秒）；超时不视为失败。
        self.settle_ms = config.get("playwright", {}).get("settle_ms", 3000)

        self._visited: set[str] = set()
        self._pages: list[CrawledPage] = []

    @staticmethod
    def _normalize_url(url: str) -> str:
        """规范化 URL（去 fragment、统一 trailing slash）"""
        parsed = urlparse(url)
        # 去掉 fragment
        url = url.split("#")[0]
        # 统一 trailing slash（只对 path 为空的加 /）
        if parsed.path == "":
            url = url.rstrip("/") + "/"
        return url.lower()

    @staticmethod
    def _extract_links(html: str, base_url: str) -> list[str]:
        """从 HTML 中提取同域链接"""
        domain = urlparse(base_url).netloc
        links = re.findall(r'<a\s+(?:[^>]*?\s+)?href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        result = []
        for link in links:
            if link.startswith(("javascript:", "mailto:", "tel:")):
                continue
            full_url = urljoin(base_url, link)
            full_url = full_url.split("#")[0]  # 去掉 fragment
            if urlparse(full_url).netloc == domain:
                result.append(full_url)
        return list(set(result))

    @staticmethod
    def _extract_text_from_html(html: str) -> str:
        """从 HTML 中提取纯文本（移除 script/style）"""
        # 移除 script 和 style
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        # 移除 HTML 标签
        text = re.sub(r"<[^>]+>", " ", text)
        # 合并空白
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _extract_headings(html: str) -> list[tuple[int, str]]:
        """提取 H1-H6 标题"""
        headings = []
        pattern = re.compile(r"<h([1-6])[^>]*>(.*?)</h\1>", re.DOTALL | re.IGNORECASE)
        for match in pattern.finditer(html):
            level = int(match.group(1))
            text = re.sub(r"<[^>]+>", "", match.group(2)).strip()
            if text:
                headings.append((level, text))
        return headings

    @staticmethod
    def _extract_images(html: str, base_url: str) -> list[dict]:
        """提取图片信息"""
        images = []
        pattern = re.compile(r"<img\s+([^>]+)>", re.IGNORECASE)
        for match in pattern.finditer(html):
            attrs = match.group(1)
            src_match = re.search(r'src=["\']([^"\']+)["\']', attrs)
            alt_match = re.search(r'alt=["\']([^"\']*)["\']', attrs)
            if src_match:
                src = src_match.group(1)
                if not src.startswith(("http://", "https://", "data:")):
                    src = urljoin(base_url, src)
                images.append({
                    "src": src,
                    "alt": alt_match.group(1) if alt_match else "",
                })
        return images

    @staticmethod
    def _detect_language(html: str) -> str:
        """检测页面语言"""
        # 尝试从 html lang 属性获取
        lang_match = re.search(r'<html[^>]*\slang=["\']([a-z\-]+)["\']', html, re.IGNORECASE)
        if lang_match:
            return lang_match.group(1)
        # 尝试从 meta 获取
        meta_match = re.search(
            r'<meta\s+http-equiv=["\']content-language["\']\s+content=["\']([a-z\-]+)["\']',
            html, re.IGNORECASE
        )
        if meta_match:
            return meta_match.group(1)
        # 默认
        return "zh-CN"

    async def _fetch_page(self, url: str) -> Optional[CrawledPage]:
        """使用 Playwright 抓取单个页面"""
        try:
            async with async_playwright() as pw:
                # 容器内以 root 运行时 Chromium sandbox 不可用，需附加 --no-sandbox；
                # 普通用户环境（含 Windows 无 geteuid）保持原生 sandbox 行为。
                launch_args = (
                    ["--no-sandbox"] if hasattr(os, "geteuid") and os.geteuid() == 0
                    else []
                )
                browser = await pw.chromium.launch(
                    headless=self.headless, args=launch_args)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (compatible; GEOCrawler/1.0; +https://example.com/bot)"
                )
                page = await context.new_page()
                await page.goto(url, wait_until=self.wait_until, timeout=self.timeout_ms)

                # 主导航成功后，再给动态内容一个短窗口；重埋点站点网络永不空闲，
                # 这里的 networkidle 超时仅记日志，不中断抓取。
                if self.settle_ms > 0:
                    try:
                        await page.wait_for_load_state(
                            "networkidle", timeout=self.settle_ms)
                    except Exception:  # noqa: BLE001
                        logger.debug("networkidle 等待超时，已按当前 DOM 继续: %s", url)

                html = await page.content()
                title = await page.title()

                # 提取数据
                text = self._extract_text_from_html(html)
                headings = self._extract_headings(html)
                links = self._extract_links(html, url)
                images = self._extract_images(html, url)
                language = self._detect_language(html)

                # meta 信息
                meta_desc = ""
                meta_keywords = ""
                desc_el = await page.query_selector('meta[name="description"]')
                if desc_el:
                    meta_desc = await desc_el.get_attribute("content") or ""
                kw_el = await page.query_selector('meta[name="keywords"]')
                if kw_el:
                    meta_keywords = await kw_el.get_attribute("content") or ""

                await browser.close()

                return CrawledPage(
                    url=url,
                    title=title,
                    html=html,
                    text=text,
                    language=language,
                    meta_desc=meta_desc,
                    meta_keywords=meta_keywords,
                    headings=headings,
                    links=links,
                    word_count=len(text.split()),
                    images=images,
                )

        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    async def crawl(self, urls: list[str] | None = None) -> list[CrawledPage]:
        """
        爬取网站
        :param urls: 指定 URL 列表，为空则从配置的 target.url 开始
        :return: CrawledPage 列表
        """
        target = self.config.get("target", {})

        if urls:
            start_urls = urls
        elif target.get("urls"):
            start_urls = target["urls"]
        elif target.get("url"):
            start_urls = [target["url"]]
        else:
            logger.warning("No target URL configured")
            return []

        # 初始化队列
        queue = []
        for url in start_urls:
            normalized = self._normalize_url(url)
            if normalized not in self._visited:
                queue.append((normalized, 0))  # (url, depth)
                self._visited.add(normalized)

        pages = []

        while queue and len(pages) < self.max_pages:
            url, depth = queue.pop(0)
            logger.info(f"Crawling [{depth}/{self.max_depth}]: {url}")

            page = await self._fetch_page(url)
            if page:
                pages.append(page)
                self._pages.append(page)
                logger.info(f"  → Title: {page.title}, Words: {page.word_count}, Links: {len(page.links)}")

                # 深度优先：加入新链接
                if depth < self.max_depth:
                    for link in page.links:
                        normalized = self._normalize_url(link)
                        if normalized not in self._visited:
                            self._visited.add(normalized)
                            queue.append((normalized, depth + 1))
            else:
                logger.warning(f"  → Failed to fetch {url}")

        logger.info(f"Crawling complete: {len(pages)} pages, {len(self._visited)} URLs visited")
        return pages

    def get_visited_urls(self) -> list[str]:
        """返回所有已访问的 URL"""
        return list(self._visited)


# --- 同步包装器（方便非异步调用） ---
def crawl_sync(config: dict, urls: list[str] | None = None) -> list[CrawledPage]:
    """同步版本的爬取函数"""
    import asyncio
    crawler = GEOCrawler(config)
    return asyncio.run(crawler.crawl(urls))


# --- 快捷测试 ---
async def main():
    from geo_optimizer.config import load_config
    logging.basicConfig(level=logging.INFO)

    config = load_config()
    crawler = GEOCrawler(config)
    pages = await crawler.crawl()

    for p in pages:
        print(f"\n{'='*60}")
        print(f"URL: {p.url}")
        print(f"Title: {p.title}")
        print(f"Language: {p.language}")
        print(f"Word count: {p.word_count}")
        print(f"Heading count: {len(p.headings)}")
        print(f"Link count: {len(p.links)}")
        print(f"Image count: {len(p.images)}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
