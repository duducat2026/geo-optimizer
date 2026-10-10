#!/usr/bin/env python3
"""
geo_schema.py — Schema 结构化数据生成模块
根据页面内容自动生成 JSON-LD 结构化数据
"""

import json
import logging
from typing import Optional

from geo_optimizer.crawler import CrawledPage

logger = logging.getLogger(__name__)


class GEOSchemaGenerator:
    """GEO Schema 结构化数据生成器"""

    @staticmethod
    def generate_all(page: CrawledPage, config: dict) -> list[dict]:
        """生成所有适用的 Schema 类型"""
        schemas = []

        # Article / WebPage
        article_schema = GEOSchemaGenerator._article_schema(page, config)
        if article_schema:
            schemas.append(article_schema)

        # FAQPage
        faq_schema = GEOSchemaGenerator._detect_faq_and_schema(page)
        if faq_schema:
            schemas.append(faq_schema)

        # Organization
        org_schema = GEOSchemaGenerator._organization_schema(config)
        if org_schema:
            schemas.append(org_schema)

        # BreadcrumbList
        breadcrumb_schema = GEOSchemaGenerator._breadcrumb_schema(page)
        if breadcrumb_schema:
            schemas.append(breadcrumb_schema)

        return schemas

    @staticmethod
    def _article_schema(page: CrawledPage, config: dict) -> Optional[dict]:
        """Article / WebPage Schema"""
        if not page.title:
            return None

        schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": page.title,
            "description": page.meta_desc or page.text[:200],
            "url": page.url,
            "inLanguage": page.language,
            "wordCount": page.word_count,
            "datePublished": "",  # 需要额外信息
            "dateModified": "",
        }

        # 如果有图片
        if page.images:
            schema["image"] = [img["src"] for img in page.images[:3]]

        # 关键词
        if page.meta_keywords:
            schema["keywords"] = [k.strip() for k in page.meta_keywords.split(",")]

        return schema

    @staticmethod
    def _detect_faq_and_schema(page: CrawledPage) -> Optional[dict]:
        """检测页面是否包含 FAQ 内容，生成 FAQPage Schema"""
        import re

        # 检测是否有问答模式
        faq_pattern = re.compile(
            r"(问题|问答|faq|FAQ|Q&A|常见|如何|什么|为什么)\s*[:：]?\s*([^\n]{10,})",
            re.IGNORECASE,
        )

        questions = faq_pattern.findall(page.text)
        if not questions:
            return None

        if len(questions) < 2:
            return None

        entities = []
        for q, a in questions[:10]:  # 最多取 10 个
            entities.append({
                "@type": "Question",
                "name": q.strip(),
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": a.strip(),
                },
            })

        if not entities:
            return None

        return {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": entities,
        }

    @staticmethod
    def _organization_schema(config: dict) -> Optional[dict]:
        """Organization Schema（从配置中提取）"""
        profile = config.get("business_profile", {})
        if not profile.get("name"):
            return None

        schema = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": profile.get("name", ""),
            "url": config.get("target", {}).get("url", ""),
            "description": profile.get("description", ""),
        }

        if profile.get("logo"):
            schema["logo"] = profile.get("logo")

        if profile.get("sameAs"):
            schema["sameAs"] = profile["sameAs"]

        if profile.get("contact"):
            schema["contactPoint"] = {
                "@type": "ContactPoint",
                "telephone": profile["contact"].get("phone", ""),
                "email": profile["contact"].get("email", ""),
            }

        if profile.get("address"):
            schema["address"] = {
                "@type": "PostalAddress",
                "addressLocality": profile["address"].get("city", ""),
                "addressRegion": profile["address"].get("province", ""),
                "addressCountry": profile["address"].get("country", ""),
            }

        return schema

    @staticmethod
    def _breadcrumb_schema(page: CrawledPage) -> Optional[dict]:
        """BreadcrumbList Schema（从 URL 路径推断）"""
        from urllib.parse import urlparse

        parsed = urlparse(page.url)
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]

        if len(path_parts) < 1:
            return None

        elements = [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": f"{parsed.scheme}://{parsed.netloc}/",
            }
        ]

        for i, part in enumerate(path_parts):
            url = f"{parsed.scheme}://{parsed.netloc}/{'/'.join(path_parts[:i+1])}/"
            elements.append({
                "@type": "ListItem",
                "position": i + 2,
                "name": part.replace("-", " ").replace("_", " ").title(),
                "item": url,
            })

        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": elements,
        }

    @staticmethod
    def to_json_ld(schema: dict) -> str:
        """将 Schema dict 转为 JSON-LD 字符串（可直接嵌入 HTML）"""
        return f'<script type="application/ld+json">\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n</script>'

    @staticmethod
    def combine_all(schemas: list[dict]) -> str:
        """将所有 Schema 合并为一个 @graph"""
        if not schemas:
            return ""
        if len(schemas) == 1:
            return GEOSchemaGenerator.to_json_ld(schemas[0])

        graph = {
            "@context": "https://schema.org",
            "@graph": schemas,
        }
        return GEOSchemaGenerator.to_json_ld(graph)


# --- 快捷测试 ---
def main():
    from geo_optimizer.config import load_config
    logging.basicConfig(level=logging.INFO)

    config = load_config()
    page = CrawledPage(
        url="https://example.com/products/cleaner-robot",
        title="智能清洁机器人 - 自动清扫拖地",
        html="",
        text="我们的智能清洁机器人可以自动清扫和拖地。\n\n问题：续航多久？\n答：120分钟。\n\n问题：支持多大面积？\n答：200平米以内。",
        language="zh-CN",
        meta_desc="智能清洁机器人",
        meta_keywords="清洁机器人,扫地机器人",
        headings=[(1, "智能清洁机器人"), (2, "功能介绍")],
        links=[],
        word_count=30,
        images=[{"src": "https://example.com/robot.jpg", "alt": "清洁机器人"}],
    )

    generator = GEOSchemaGenerator()
    schemas = generator.generate_all(page, config)

    for s in schemas:
        print(f"Type: {s.get('@type', 'unknown')}")
        print(GEOSchemaGenerator.to_json_ld(s))
        print()

    print("--- Combined ---")
    print(generator.combine_all(schemas))


if __name__ == "__main__":
    main()
