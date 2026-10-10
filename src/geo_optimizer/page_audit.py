#!/usr/bin/env python3
"""
page_audit.py — 页面技术体检：面向 GEO 的可抓取性/可引用性检测

对 CrawledPage 做规则检测，输出逐项体检结果、主要问题、已有优势、
优先级排序建议与预计提升区间。不依赖 LLM。
"""

import re
from urllib.parse import urlparse

from geo_optimizer.models import CrawledPage

# 检测项 -> 修复优先级（red 最高）
SEVERITY = {
    "https": "red",
    "headings": "red",
    "meta_desc": "red",
    "schema": "yellow",
    "faq": "yellow",
    "author_date": "green",
    "img_alt": "green",
}

# 各失败项对总分的大致提升权重（用于预计提升区间）
GAIN = {"red": 15, "yellow": 8, "green": 4}


def audit_page(page: CrawledPage, crawl_ms: int | None = None,
               overall_score: float | None = None) -> dict:
    """执行体检，返回可序列化 dict。"""
    html = page.html or ""
    text = page.text or ""
    low_html = html.lower()

    checks = []

    def add(key, ok, value):
        checks.append({
            "key": key,
            "ok": bool(ok),
            "severity": SEVERITY.get(key, "info"),
            "value": value,
        })

    # 1. HTTPS
    add("https", page.url.startswith("https://"), page.url.split(":", 1)[0].upper())

    # 2. 标题结构 H1/H2/H3
    h1 = sum(1 for lv, _ in page.headings if lv == 1)
    h2 = sum(1 for lv, _ in page.headings if lv == 2)
    h3 = sum(1 for lv, _ in page.headings if lv == 3)
    add("headings", h1 >= 1 and (h1 + h2 + h3) >= 3, f"H1:{h1} H2:{h2} H3:{h3}")

    # 3. meta description
    add("meta_desc", bool((page.meta_desc or "").strip()),
        (page.meta_desc or "")[:60] or "-")

    # 4. 结构化数据（JSON-LD / schema.org）
    has_schema = "application/ld+json" in low_html or "schema.org" in low_html
    add("schema", has_schema, "JSON-LD" if has_schema else "-")

    # 5. FAQ 区块
    faq_words = ["faq", "常见问题", "问答", "q&a", "frequently asked"]
    has_faq = any(w in low_html or w in text for w in faq_words)
    add("faq", has_faq, "FAQ" if has_faq else "-")

    # 6. 作者/日期信息（E-E-A-T 信号）
    author_words = ["author", "作者", "编辑", "written by", "发布于", "published"]
    has_author = any(w in low_html for w in author_words)
    has_date = bool(re.search(r"20\d{2}[-/年]\d{1,2}", text))
    add("author_date", has_author or has_date,
        f"author:{'Y' if has_author else 'N'} date:{'Y' if has_date else 'N'}")

    # 7. 图片 alt 覆盖
    total_imgs = len(page.images)
    missing_alt = sum(1 for img in page.images if not (img.get("alt") or "").strip())
    add("img_alt", total_imgs == 0 or missing_alt == 0, f"{missing_alt}/{total_imgs}")

    # --- 统计型信息（优势/中性，不参与优先级） ---
    stats = {
        "word_count": page.word_count,
        "text_len": len(text),
        "list_count": low_html.count("<ul") + low_html.count("<ol"),
        "internal_links": _internal_link_count(page),
        "image_count": total_imgs,
    }
    if crawl_ms is not None:
        stats["crawl_ms"] = int(crawl_ms)

    issues = [c for c in checks if not c["ok"]]
    strengths = _derive_strengths(checks, stats)

    # 优先级排序建议：red -> yellow -> green
    order = {"red": 0, "yellow": 1, "green": 2}
    priorities = sorted((c["key"] for c in issues),
                        key=lambda k: order.get(SEVERITY.get(k, "green"), 3))

    result = {
        "checks": checks,
        "stats": stats,
        "issues": [c["key"] for c in issues],
        "strengths": strengths,
        "priorities": priorities,
    }
    if overall_score is not None:
        result["estimate"] = _estimate(overall_score, issues)
    return result


def _internal_link_count(page: CrawledPage) -> int:
    host = urlparse(page.url).netloc
    count = 0
    for link in page.links:
        netloc = urlparse(link).netloc
        if not netloc or netloc == host:
            count += 1
    return count


def _derive_strengths(checks: list[dict], stats: dict) -> list[str]:
    """由通过项与统计信息推导优势 key 列表。"""
    strengths = [c["key"] for c in checks if c["ok"]]
    if stats["text_len"] >= 800 or stats["word_count"] >= 300:
        strengths.append("content_volume")
    if stats["list_count"] >= 3:
        strengths.append("rich_lists")
    if stats["internal_links"] >= 10:
        strengths.append("internal_links")
    if stats.get("crawl_ms") is not None and stats["crawl_ms"] < 3000:
        strengths.append("fast_load")
    return strengths


def _estimate(overall: float, issues: list[dict]) -> dict:
    """修复全部问题后的预计得分区间。"""
    gain = sum(GAIN.get(c["severity"], 0) for c in issues)
    est_min = min(90.0, round(overall + gain * 0.7, 0))
    est_max = min(95.0, round(overall + gain * 1.0, 0))
    return {"gain": gain, "min": max(est_min, overall), "max": max(est_max, overall)}
