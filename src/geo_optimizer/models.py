#!/usr/bin/env python3
"""
geo_models.py — 公共数据模型（不依赖 playwright）
"""

from dataclasses import dataclass, field


@dataclass
class CrawledPage:
    """爬取后的页面数据"""
    url: str
    title: str
    html: str
    text: str
    language: str
    meta_desc: str
    meta_keywords: str
    headings: list[tuple[int, str]] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    word_count: int = 0
    images: list[dict] = field(default_factory=list)
