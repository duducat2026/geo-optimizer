#!/usr/bin/env python3
"""
schema_generator.py — JSON-LD Schema 标记生成器
支持中英文多语言、FAQPage / Article / WebPage 等类型
"""

import json
import logging
from datetime import datetime
from typing import Optional

from geo_optimizer.config import load_config
from geo_optimizer.crawler import CrawledPage
from geo_optimizer.web.faq_generator import FAQ

logger = logging.getLogger(__name__)


class SchemaGenerator:
    """多语言 JSON-LD Schema 生成"""

    def generate(self, page: CrawledPage, faqs: list[FAQ], config: dict,
                 lang: Optional[str] = None) -> dict:
        """为单页生成完整 Schema（多类型组合）。

        lang 指定时只保留该语言的 FAQ 并显式声明 inLanguage，供双语包按
        zh/ 与 en/ 各出一份；None 时保持既有行为（全部 FAQ，双语 inLanguage）。
        WebPage/Article 的 name/description 取自抓取快照，只能保持站点原始语言。
        """
        schemas = {}

        # 1. WebPage 基础
        schemas["WebPage"] = self._webpage_schema(page)

        # 2. Article（如果有足够内容）
        if page.word_count > 200:
            schemas["Article"] = self._article_schema(page)

        # 3. FAQPage（如果有 FAQ）
        picked = self._filter_faqs(faqs, lang)
        if picked:
            schemas["FAQPage"] = self._faqpage_schema(picked, lang=lang)

        # 4. Organization（站点信息）
        schemas["Organization"] = self._organization_schema(config)

        # 5. BreadcrumbList（如果有标题层级）
        if len(page.headings) >= 2:
            schemas["BreadcrumbList"] = self._breadcrumb_schema(page)

        return schemas

    @staticmethod
    def _filter_faqs(faqs: list[FAQ], lang: Optional[str]) -> list[FAQ]:
        if lang == "zh":
            return [f for f in faqs if f.language == "zh-CN"] or faqs
        if lang == "en":
            return [f for f in faqs if f.language == "en-US"]
        return faqs

    def render_jsonld(self, schemas: dict) -> str:
        """渲染为可注入的 <script> 标签"""
        blocks = []
        for schema_type, data in schemas.items():
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            blocks.append(f'<script type="application/ld+json">\n{json_str}\n</script>')
        return "\n\n".join(blocks)

    @staticmethod
    def _webpage_schema(page: CrawledPage) -> dict:
        return {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": page.title,
            "description": page.meta_desc or page.text[:200],
            "url": page.url,
            "inLanguage": page.language,
            "datePublished": datetime.now().strftime("%Y-%m-%d"),
            "dateModified": datetime.now().strftime("%Y-%m-%d"),
        }

    @staticmethod
    def _article_schema(page: CrawledPage) -> dict:
        return {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": page.title,
            "description": page.meta_desc or page.text[:200],
            "url": page.url,
            "inLanguage": page.language,
            "datePublished": datetime.now().strftime("%Y-%m-%d"),
            "dateModified": datetime.now().strftime("%Y-%m-%d"),
            "wordCount": page.word_count,
            "articleSection": page.headings[0][1] if page.headings else "",
        }

    @staticmethod
    def _faqpage_schema(faqs: list[FAQ], lang: Optional[str] = None) -> dict:
        """FAQPage schema（按语言分组）"""
        faq_items = []
        for f in faqs:
            faq_items.append({
                "@type": "Question",
                "name": f.question,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f.answer,
                },
            })

        schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faq_items,
        }

        # 多语言支持：单语输出时显式声明该语言，混合输出时列出两种
        if lang == "zh":
            schema["inLanguage"] = "zh-CN"
        elif lang == "en":
            schema["inLanguage"] = "en-US"
        else:
            zh_faqs = [f for f in faqs if f.language == "zh-CN"]
            en_faqs = [f for f in faqs if f.language == "en-US"]
            if zh_faqs and en_faqs:
                schema["inLanguage"] = ["zh-CN", "en-US"]

        return schema

    @staticmethod
    def _organization_schema(config: dict) -> dict:
        target = config.get("target", {})
        url = target.get("url", "https://example.com")
        return {
            "@context": "https://schema.org",
            "@type": "Organization",
            "url": url,
            "name": "Organization Name",  # TODO: 从页面或配置提取
            "sameAs": [],                  # TODO: 社交媒体链接
        }

    @staticmethod
    def _breadcrumb_schema(page: CrawledPage) -> dict:
        """基于标题层级生成面包屑"""
        items = []
        for i, (level, text) in enumerate(page.headings[:5], 1):
            items.append({
                "@type": "ListItem",
                "position": i,
                "name": text,
            })

        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": items,
        }


def format_schema_report(schemas: dict) -> str:
    """格式化 Schema 报告"""
    lines = ["# JSON-LD Schema 报告\n"]
    for schema_type, data in schemas.items():
        lines.append(f"## {schema_type}\n")
        lines.append("```json")
        lines.append(json.dumps(data, ensure_ascii=False, indent=2))
        lines.append("```\n")
    return "\n".join(lines)


# --- 快捷测试 ---
def main():
    config = load_config()
    from geo_optimizer.crawler import CrawledPage
    from geo_optimizer.web.faq_generator import FAQ

    page = CrawledPage(
        url="https://example.com",
        title="智能空气净化器",
        html="",
        text="这是一款智能空气净化器...",
        language="zh-CN",
        meta_desc="最好的智能空气净化器",
        meta_keywords="空气净化器",
        headings=[(1, "智能空气净化器"), (2, "产品特点"), (3, "HEPA滤网")],
        links=[],
        word_count=500,
    )
    faqs = [
        FAQ("空气净化器怎么选？", "选择HEPA滤网...", "zh-CN", ["空气净化器"], ["通义千问"]),
        FAQ("How to choose an air purifier?", "Look for HEPA...", "en-US", ["air purifier"], ["Google AI Overviews"]),
    ]

    generator = SchemaGenerator()
    schemas = generator.generate(page, faqs, config)
    print(format_schema_report(schemas))
    print("\n--- Injectable Script Tags ---\n")
    print(generator.render_jsonld(schemas))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
