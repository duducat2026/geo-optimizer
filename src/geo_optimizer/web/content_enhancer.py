#!/usr/bin/env python3
"""
content_enhancer.py — 双语内容注入
将 FAQ、Schema、权威性内容注入原始 HTML，输出优化后页面
"""

import logging
import os
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from geo_optimizer.config import load_config
from geo_optimizer.crawler import CrawledPage
from geo_optimizer.web.faq_generator import FAQ
from geo_optimizer.web.schema_generator import SchemaGenerator
from geo_optimizer.web.authority_builder import AuthorityBuilder, AuthorityProfile

logger = logging.getLogger(__name__)


class ContentEnhancer:
    """双语内容增强器"""

    def __init__(self, config: dict):
        self.config = config
        self.output_dir = config.get("output", {}).get("dir", "./output")
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.schema_gen = SchemaGenerator()
        self.auth_builder = AuthorityBuilder()

    def enhance(self, page: CrawledPage, faqs: list[FAQ]) -> dict:
        """增强单页内容，返回优化结果"""
        # 1. 生成 Schema
        schemas = self.schema_gen.generate(page, faqs, self.config)
        jsonld_script = self.schema_gen.render_jsonld(schemas)

        # 2. 构建权威性
        profile = self.auth_builder.build(page, faqs, self.config)

        # 3. 注入内容
        enhanced_html = self._inject(page.html, jsonld_script, faqs, profile)

        # 4. 生成 FAQ Markdown
        from geo_optimizer.web.faq_generator import format_faqs_to_markdown
        faq_md = format_faqs_to_markdown(faqs)

        # 5. 保存输出
        self._save_outputs(page, enhanced_html, faq_md, schemas, profile)

        return {
            "url": page.url,
            "enhanced_html_path": os.path.join(self.output_dir, f"{self._slug(page.title)}.html"),
            "faq_md_path": os.path.join(self.output_dir, f"{self._slug(page.title)}_faq.md"),
            "schema_json": schemas,
            "authority_profile": profile,
            "faq_count": len(faqs),
        }

    def _inject(self, html: str, jsonld_script: str, faqs: list[FAQ], profile: AuthorityProfile) -> str:
        """将优化内容注入 HTML"""
        if not html:
            return self._build_minimal_page(jsonld_script, faqs, profile)

        soup = BeautifulSoup(html, "html.parser")

        # 1. 注入 Schema（head 中）
        head = soup.find("head")
        if head:
            head.append(BeautifulSoup(jsonld_script, "html.parser"))

        # 2. 注入 FAQ 区块（body 末尾）
        body = soup.find("body")
        if body:
            faq_html = self._render_faqs_as_html(faqs)
            body.append(BeautifulSoup(faq_html, "html.parser"))

            # 3. 注入作者信息
            author_box = self.auth_builder.generate_author_box(profile, "zh-CN")
            body.append(BeautifulSoup(author_box, "html.parser"))

            # 4. 注入参考文献
            ref_section = self.auth_builder.generate_reference_section(profile)
            body.append(BeautifulSoup(ref_section, "html.parser"))

        return str(soup)

    def _build_minimal_page(self, jsonld_script: str, faqs: list[FAQ], profile: AuthorityProfile) -> str:
        """无原始HTML时，构建最小化页面"""
        faq_html = self._render_faqs_as_html(faqs)
        author_box = self.auth_builder.generate_author_box(profile, "zh-CN")
        ref_section = self.auth_builder.generate_reference_section(profile, "zh-CN")

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GEO Optimized Page</title>
  {jsonld_script}
</head>
<body>
  <main>
    {faq_html}
    {author_box}
    {ref_section}
  </main>
</body>
</html>"""

    @staticmethod
    def _render_faqs_as_html(faqs: list[FAQ]) -> str:
        """渲染 FAQ 为 HTML 区块"""
        zh_faqs = [f for f in faqs if f.language == "zh-CN"]
        en_faqs = [f for f in faqs if f.language == "en-US"]

        parts = []

        if zh_faqs:
            parts.append('<section class="faq-section" itemscope itemtype="https://schema.org/FAQPage">')
            parts.append('<h2>常见问题</h2>')
            for f in zh_faqs:
                parts.append(f'<details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">')
                parts.append(f'  <summary itemprop="name">{f.question}</summary>')
                parts.append(f'  <div itemprop="acceptedAnswer" itemscope itemtype="https://schema.org/Answer">')
                parts.append(f'    <p itemprop="text">{f.answer}</p>')
                parts.append(f'  </div>')
                parts.append(f'</details>')
            parts.append('</section>')

        if en_faqs:
            parts.append('<section class="faq-section faq-en" itemscope itemtype="https://schema.org/FAQPage">')
            parts.append('<h2>Frequently Asked Questions</h2>')
            for f in en_faqs:
                parts.append(f'<details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">')
                parts.append(f'  <summary itemprop="name">{f.question}</summary>')
                parts.append(f'  <div itemprop="acceptedAnswer" itemscope itemtype="https://schema.org/Answer">')
                parts.append(f'    <p itemprop="text">{f.answer}</p>')
                parts.append(f'  </div>')
                parts.append(f'</details>')
            parts.append('</section>')

        return "\n".join(parts)

    def _save_outputs(self, page: CrawledPage, enhanced_html: str, faq_md: str, schemas: dict, profile: AuthorityProfile):
        """保存所有输出"""
        slug = self._slug(page.title)

        # HTML
        html_path = os.path.join(self.output_dir, f"{slug}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(enhanced_html)
        logger.info(f"📄 Saved: {html_path}")

        # FAQ Markdown
        faq_path = os.path.join(self.output_dir, f"{slug}_faq.md")
        with open(faq_path, "w", encoding="utf-8") as f:
            f.write(faq_md)
        logger.info(f"📝 Saved: {faq_path}")

        # Schema JSON
        schema_path = os.path.join(self.output_dir, f"{slug}_schema.json")
        with open(schema_path, "w", encoding="utf-8") as f:
            import json
            json.dump(schemas, f, ensure_ascii=False, indent=2)
        logger.info(f"🔗 Saved: {schema_path}")

        # Authority report
        from geo_optimizer.web.authority_builder import format_authority_report
        auth_path = os.path.join(self.output_dir, f"{slug}_authority.md")
        with open(auth_path, "w", encoding="utf-8") as f:
            f.write(format_authority_report(profile))
        logger.info(f"🏆 Saved: {auth_path}")

    @staticmethod
    def _slug(title: str) -> str:
        """生成安全的文件名"""
        import re
        slug = re.sub(r'[^\w\u4e00-\u9fff\s-]', '', title)
        slug = re.sub(r'\s+', '-', slug)
        return slug[:50] or "page"


def format_enhance_report(results: list[dict]) -> str:
    """格式化增强报告"""
    lines = ["# 内容增强报告\n"]
    for r in results:
        lines.append(f"## {r['url']}")
        lines.append(f"- 增强HTML: `{r['enhanced_html_path']}`")
        lines.append(f"- FAQ Markdown: `{r['faq_md_path']}`")
        lines.append(f"- FAQ数量: {r['faq_count']}")
        lines.append(f"- Schema类型: {', '.join(r['schema_json'].keys())}")
        lines.append("")
    return "\n".join(lines)


# --- 快捷测试 ---
def main():
    config = load_config()
    from geo_optimizer.crawler import CrawledPage
    from geo_optimizer.web.faq_generator import FAQ

    page = CrawledPage(
        url="https://example.com",
        title="智能空气净化器",
        html="<html><head><title>Test</title></head><body><h1>智能空气净化器</h1><p>这是一款好产品。</p></body></html>",
        text="智能空气净化器，HEPA滤网...",
        language="zh-CN",
        meta_desc="最好的空气净化器",
        meta_keywords="",
        headings=[(1, "智能空气净化器")],
        links=[],
        word_count=500,
    )
    faqs = [
        FAQ("空气净化器怎么选？", "看HEPA等级...", "zh-CN", ["空气净化器"], ["通义千问"]),
        FAQ("How to choose?", "Check HEPA...", "en-US", ["air purifier"], ["Google"]),
    ]

    enhancer = ContentEnhancer(config)
    result = enhancer.enhance(page, faqs)
    print(format_enhance_report([result]))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
