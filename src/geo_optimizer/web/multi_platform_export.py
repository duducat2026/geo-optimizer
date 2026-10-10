#!/usr/bin/env python3
"""
multi_platform_export.py — 国内外平台内容导出
国内：微信公众号、知乎、头条号
国外：Medium、Quora、Reddit
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from geo_optimizer.config import load_config
from geo_optimizer.web.faq_generator import FAQ, format_faqs_to_markdown
from geo_optimizer.crawler import CrawledPage
from geo_optimizer.web.authority_builder import AuthorityProfile

logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    platform: str
    format: str
    file_path: str
    status: str  # success / skipped
    language: str


class MultiPlatformExporter:
    """多平台内容导出器"""

    def __init__(self, config: dict):
        self.config = config
        self.output_dir = config.get("output", {}).get("dir", "./output")
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def export_all(self, page: CrawledPage, faqs: list[FAQ], profile: Optional[AuthorityProfile] = None) -> list[ExportResult]:
        """导出到所有启用的平台"""
        results = []

        # 国内平台
        for plat in self.config.get("platforms", {}).get("cn", []):
            if plat.get("enabled", True):
                result = self._export_cn(plat, page, faqs, profile)
                results.append(result)

        # 国外平台
        for plat in self.config.get("platforms", {}).get("en", []):
            if plat.get("enabled", True):
                result = self._export_en(plat, page, faqs, profile)
                results.append(result)

        return results

    # ========== 国内平台 ==========

    def _export_cn(self, plat: dict, page: CrawledPage, faqs: list[FAQ], profile: Optional[AuthorityProfile]) -> ExportResult:
        fmt = plat["format"]
        zh_faqs = [f for f in faqs if f.language == "zh-CN"]

        if fmt == "wechat":
            content = self._format_wechat(page, zh_faqs, profile)
            filename = f"wechat_{self._slug(page.title)}.md"
        elif fmt == "zhihu":
            content = self._format_zhihu(page, zh_faqs, profile)
            filename = f"zhihu_{self._slug(page.title)}.md"
        elif fmt == "toutiao":
            content = self._format_toutiao(page, zh_faqs, profile)
            filename = f"toutiao_{self._slug(page.title)}.md"
        else:
            return ExportResult(plat["name"], fmt, "", "skipped", "zh-CN")

        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"📤 Exported {plat['name']}: {filepath}")
        return ExportResult(plat["name"], fmt, filepath, "success", "zh-CN")

    @staticmethod
    def _format_wechat(page: CrawledPage, faqs: list[FAQ], profile: Optional[AuthorityProfile]) -> str:
        """微信公众号格式"""
        lines = [
            f"# {page.title}\n",
            "",
            f"> {page.meta_desc}\n",
            "",
            "## 正文\n",
        ]

        # 提取页面主要内容（前500字）
        content = page.text[:500]
        lines.append(content)
        lines.append("")

        # 分隔线
        lines.append("---\n")
        lines.append("## 常见问题\n")

        for i, f in enumerate(faqs, 1):
            lines.append(f"**Q{i}. {f.question}**\n")
            lines.append(f"{f.answer}\n")

        if profile:
            lines.append("\n---\n")
            lines.append(f"**作者**: {profile.author_name or '本站编辑'}\n")
            if profile.credentials:
                lines.append(f"**资质**: {' | '.join(profile.credentials[:3])}\n")

        return "\n".join(lines)

    @staticmethod
    def _format_zhihu(page: CrawledPage, faqs: list[FAQ], profile: Optional[AuthorityProfile]) -> str:
        """知乎回答格式"""
        lines = [
            f"## {page.title}\n",
            "",
        ]

        # 知乎风格：先给结论
        lines.append("先说结论：\n")
        # 模拟从内容提取结论
        first_heading = page.headings[0][1] if page.headings else page.title
        lines.append(f"> {first_heading} 的核心要点如下：\n")
        lines.append("")

        # 结构化展开
        for level, heading in page.headings[:5]:
            indent = "  " * (level - 1)
            lines.append(f"{indent}**{heading}**")

        lines.append("\n---\n")
        lines.append("## 详细解答\n")

        for i, f in enumerate(faqs, 1):
            lines.append(f"**{f.question}**\n")
            lines.append(f"{f.answer}\n")

        return "\n".join(lines)

    @staticmethod
    def _format_toutiao(page: CrawledPage, faqs: list[FAQ], profile: Optional[AuthorityProfile]) -> str:
        """头条号格式（短平快）"""
        lines = [
            f"# {page.title}\n",
            "",
            # 头条风格：吸引眼球的开头
            f"你知道吗？{page.meta_desc or page.title} 背后有很多值得了解的信息。",
            "",
        ]

        # 要点列表
        lines.append("**核心要点：**\n")
        for _, heading in page.headings[:5]:
            lines.append(f"- {heading}")
        lines.append("")

        # 精简版FAQ
        lines.append("\n---\n")
        lines.append("## 快速问答\n")
        for f in faqs[:5]:  # 头条只放5个
            lines.append(f"**问：{f.question}**\n")
            lines.append(f"答：{f.answer}\n")

        return "\n".join(lines)

    # ========== 国外平台 ==========

    def _export_en(self, plat: dict, page: CrawledPage, faqs: list[FAQ], profile: Optional[AuthorityProfile]) -> ExportResult:
        fmt = plat["format"]
        en_faqs = [f for f in faqs if f.language == "en-US"]

        if fmt == "medium":
            content = self._format_medium(page, en_faqs, profile)
            filename = f"medium_{self._slug(page.title)}.md"
        elif fmt == "quora":
            content = self._format_quora(page, en_faqs, profile)
            filename = f"quora_{self._slug(page.title)}.md"
        elif fmt == "reddit":
            content = self._format_reddit(page, en_faqs, profile)
            filename = f"reddit_{self._slug(page.title)}.md"
        else:
            return ExportResult(plat["name"], fmt, "", "skipped", "en-US")

        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"📤 Exported {plat['name']}: {filepath}")
        return ExportResult(plat["name"], fmt, filepath, "success", "en-US")

    @staticmethod
    def _format_medium(page: CrawledPage, faqs: list[FAQ], profile: Optional[AuthorityProfile]) -> str:
        """Medium 文章格式"""
        lines = [
            f"# {page.title}\n",
            "",
            f"*{page.meta_desc}*\n",
            "",
            "## Introduction\n",
        ]

        # 英文开头
        intro = page.text[:300] if page.text else "This article explores the key aspects of this topic."
        lines.append(intro)
        lines.append("")

        # 正文
        lines.append("## Key Points\n")
        for _, heading in page.headings[:5]:
            lines.append(f"### {heading}\n")
        lines.append("")

        # FAQ as natural Q&A
        lines.append("## Common Questions\n")
        for i, f in enumerate(faqs, 1):
            lines.append(f"### {f.question}\n")
            lines.append(f"{f.answer}\n")

        # Author bio
        if profile and profile.author_name:
            lines.append("\n---\n")
            lines.append(f"*About the author: {profile.author_name}")
            if profile.author_bio:
                lines.append(f" — {profile.author_bio}")
            lines.append("*\n")

        return "\n".join(lines)

    @staticmethod
    def _format_quora(page: CrawledPage, faqs: list[FAQ], profile: Optional[AuthorityProfile]) -> str:
        """Quora 回答格式"""
        lines = [
            f"## {page.title}\n",
            "",
            "Here's a comprehensive answer based on the latest information:\n",
            "",
        ]

        # Direct answer first (Quora style)
        if page.headings:
            lines.append(f"**The short answer:** {page.headings[0][1]}.\n")
            lines.append("Now let me break this down:\n")
            lines.append("")

        # Structured explanation
        for _, heading in page.headings[:5]:
            lines.append(f"**{heading}**")
            lines.append("")

        lines.append("---\n")
        lines.append("## Related Questions\n")
        for f in faqs[:5]:
            lines.append(f"**Q: {f.question}**\n")
            lines.append(f"A: {f.answer}\n")

        return "\n".join(lines)

    @staticmethod
    def _format_reddit(page: CrawledPage, faqs: list[FAQ], profile: Optional[AuthorityProfile]) -> str:
        """Reddit 帖子格式（更随意）"""
        lines = [
            f"# {page.title}\n",
            "",
        ]

        # Reddit style: casual intro
        lines.append(f"So I've been looking into {page.title.lower()} and wanted to share what I found.\n")
        lines.append("")

        # Key findings
        lines.append("**Key takeaways:**\n")
        for _, heading in page.headings[:5]:
            lines.append(f"- {heading}")
        lines.append("")

        # TL;DR
        lines.append("**TL;DR:** " + (page.meta_desc or page.text[:100]) + "\n")
        lines.append("")

        # Discussion points
        lines.append("---\n")
        lines.append("## Some details\n")
        for f in faqs[:3]:
            lines.append(f"**{f.question}**\n")
            lines.append(f"{f.answer}\n")

        lines.append("\nHappy to answer any questions! 🙌\n")

        return "\n".join(lines)

    @staticmethod
    def _slug(title: str) -> str:
        import re
        slug = re.sub(r'[^\w\u4e00-\u9fff\s-]', '', title)
        slug = re.sub(r'\s+', '-', slug)
        return slug[:40] or "export"


def format_export_report(results: list[ExportResult]) -> str:
    """格式化导出报告"""
    lines = ["# 多平台导出报告\n"]
    for r in results:
        status_icon = "✅" if r.status == "success" else "⏭️"
        lines.append(f"{status_icon} **{r.platform}** ({r.format}, {r.language}) → `{r.file_path}`")
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
        text="智能空气净化器采用HEPA技术...",
        language="zh-CN",
        meta_desc="最佳空气净化器推荐",
        meta_keywords="",
        headings=[(1, "智能空气净化器"), (2, "技术原理"), (2, "选购指南")],
        links=[],
        word_count=500,
    )
    faqs = [
        FAQ("空气净化器怎么选？", "看HEPA等级...", "zh-CN", ["空气净化器"], []),
        FAQ("How to choose?", "Check HEPA...", "en-US", ["air purifier"], []),
    ]

    exporter = MultiPlatformExporter(config)
    results = exporter.export_all(page, faqs)
    print(format_export_report(results))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
