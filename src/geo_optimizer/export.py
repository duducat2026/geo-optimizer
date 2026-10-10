#!/usr/bin/env python3
"""
geo_export.py — 多平台内容导出模块
将优化后的内容导出为各平台可使用的格式
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from geo_optimizer.generators.content import OptimizedContent
from geo_optimizer.generators.faq import FAQItem, format_faqs_schema_json_ld

logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    platform: str
    filename: str
    content: str
    format: str


class GEOExporter:
    """GEO 多平台导出器"""

    def __init__(self, config: dict):
        self.config = config
        output = config.get("output", {})
        self.output_dir = Path(output.get("dir", "./output"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(
        self,
        optimized_contents: list[OptimizedContent],
        faqs: list[FAQItem] | None = None,
        schema_json: str = "",
    ) -> list[ExportResult]:
        """导出所有内容到各平台"""
        results = []
        platforms = self.config.get("platforms", {})

        # 中文平台
        for plat in platforms.get("cn", []):
            if not plat.get("enabled", True):
                continue
            for oc in optimized_contents:
                exported = self._export_cn_platform(plat, oc, faqs, schema_json)
                results.append(exported)

        # 英文平台
        for plat in platforms.get("en", []):
            if not plat.get("enabled", True):
                continue
            for oc in optimized_contents:
                exported = self._export_en_platform(plat, oc, faqs, schema_json)
                results.append(exported)

        # 导出综合报告
        report = self._export_report(optimized_contents, faqs, schema_json)
        results.append(report)

        return results

    def _export_cn_platform(
        self,
        plat: dict,
        oc: OptimizedContent,
        faqs: list[FAQItem] | None,
        schema_json: str,
    ) -> ExportResult:
        """导出到中文平台"""
        name = plat.get("name", "unknown")
        fmt = plat.get("format", "markdown")

        content = self._format_cn_content(plat, oc, faqs, schema_json)

        safe_name = name.replace(" ", "_")
        filename = f"{safe_name}_{oc.target_engine.replace(' ', '_')}.md"
        filepath = self.output_dir / filename
        filepath.write_text(content, encoding="utf-8")

        logger.info(f"Exported to {filepath}")
        return ExportResult(
            platform=name,
            filename=filename,
            content=content,
            format=fmt,
        )

    def _export_en_platform(
        self,
        plat: dict,
        oc: OptimizedContent,
        faqs: list[FAQItem] | None,
        schema_json: str,
    ) -> ExportResult:
        """导出到英文平台"""
        name = plat.get("name", "unknown")
        fmt = plat.get("format", "markdown")

        content = self._format_en_content(plat, oc, faqs, schema_json)

        safe_name = name.replace(" ", "_")
        filename = f"{safe_name}_{oc.target_engine.replace(' ', '_')}.md"
        filepath = self.output_dir / filename
        filepath.write_text(content, encoding="utf-8")

        logger.info(f"Exported to {filepath}")
        return ExportResult(
            platform=name,
            filename=filename,
            content=content,
            format=fmt,
        )

    @staticmethod
    def _format_cn_content(
        plat: dict,
        oc: OptimizedContent,
        faqs: list[FAQItem] | None,
        schema_json: str,
    ) -> str:
        """格式化中文平台内容"""
        name = plat.get("name", "")

        lines = [
            f"# {oc.optimized_title}",
            f"",
            f"> 针对 {oc.target_engine} 优化",
            f"",
            oc.optimized_text,
        ]

        # FAQ 部分
        if faqs:
            zh_faqs = [f for f in faqs if f.language.startswith("zh")]
            if zh_faqs:
                lines.append(f"\n---\n")
                lines.append(f"## 常见问题")
                lines.append(f"")
                for i, faq in enumerate(zh_faqs, 1):
                    lines.append(f"### Q{i}: {faq.question}")
                    lines.append(f"")
                    lines.append(faq.answer)
                    lines.append(f"")

        # Schema 部分
        if schema_json:
            lines.append(f"\n---\n")
            lines.append(f"## 结构化数据 (JSON-LD)")
            lines.append(f"")
            lines.append(f"```json")
            lines.append(schema_json)
            lines.append(f"```")

        # 改进说明
        if oc.improvements:
            lines.append(f"\n---\n")
            lines.append(f"## 优化说明")
            lines.append(f"")
            for imp in oc.improvements:
                lines.append(f"- {imp}")

        if name == "微信公众号":
            return _format_wechat("\n".join(lines))
        elif name == "知乎":
            return _format_zhihu("\n".join(lines))
        elif name == "头条号":
            return _format_toutiao("\n".join(lines))

        return "\n".join(lines)

    @staticmethod
    def _format_en_content(
        plat: dict,
        oc: OptimizedContent,
        faqs: list[FAQItem] | None,
        schema_json: str,
    ) -> str:
        """格式化英文平台内容"""
        name = plat.get("name", "")

        lines = [
            f"# {oc.optimized_title}",
            f"",
            f"> Optimized for {oc.target_engine}",
            f"",
            oc.optimized_text,
        ]

        if faqs:
            en_faqs = [f for f in faqs if not f.language.startswith("zh")]
            if en_faqs:
                lines.append(f"\n---\n")
                lines.append(f"## Frequently Asked Questions")
                lines.append(f"")
                for i, faq in enumerate(en_faqs, 1):
                    lines.append(f"### Q{i}: {faq.question}")
                    lines.append(f"")
                    lines.append(faq.answer)
                    lines.append(f"")

        if schema_json:
            lines.append(f"\n---\n")
            lines.append(f"## Structured Data (JSON-LD)")
            lines.append(f"")
            lines.append(f"```json")
            lines.append(schema_json)
            lines.append(f"```")

        if name == "Medium":
            return _format_medium("\n".join(lines))
        elif name == "Quora":
            return _format_quora("\n".join(lines))
        elif name == "Reddit":
            return _format_reddit("\n".join(lines))

        return "\n".join(lines)

    def _export_report(
        self,
        optimized_contents: list[OptimizedContent],
        faqs: list[FAQItem] | None,
        schema_json: str,
    ) -> ExportResult:
        """导出综合报告"""
        lines = [
            "# GEO 优化综合报告",
            f"",
            f"## 概览",
            f"",
            f"优化引擎数量: {len(optimized_contents)}",
            f"FAQ 数量: {len(faqs) if faqs else 0}",
            f"",
            f"## 各引擎优化结果",
            f"",
        ]

        for oc in optimized_contents:
            lines.append(f"### {oc.target_engine}")
            lines.append(f"- 优化标题: {oc.optimized_title}")
            lines.append(f"- Meta 描述: {oc.optimized_meta_desc}")
            lines.append(f"- 改进点: {', '.join(oc.improvements)}")
            lines.append(f"")

        if faqs:
            lines.append(f"## FAQ 列表")
            lines.append(f"")
            for faq in faqs:
                lines.append(f"- **Q:** {faq.question}")
                lines.append(f"  **A:** {faq.answer[:100]}...")
                lines.append(f"")

        content = "\n".join(lines)
        filename = "geo_optimization_report.md"
        filepath = self.output_dir / filename
        filepath.write_text(content, encoding="utf-8")

        return ExportResult(
            platform="Report",
            filename=filename,
            content=content,
            format="markdown",
        )


# --- 平台特定格式化 ---

def _format_wechat(content: str) -> str:
    """微信公众号格式：去除 markdown 标题标记，加粗用 **"""
    lines = content.split("\n")
    formatted = []
    for line in lines:
        if line.startswith("### "):
            formatted.append(f"\n**{line[4:]}**\n")
        elif line.startswith("## "):
            formatted.append(f"\n**{line[3:]}**\n")
        elif line.startswith("# "):
            formatted.append(f"\n**{line[2:]}**\n")
        else:
            formatted.append(line)
    return "\n".join(formatted)


def _format_zhihu(content: str) -> str:
    """知乎格式：保留 markdown，添加专业引用提示"""
    return content + "\n\n---\n*以上内容基于数据分析自动生成，仅供参考。*"


def _format_toutiao(content: str) -> str:
    """头条号格式：更口语化，加引导"""
    lines = content.split("\n")
    # 在开头加引导
    lines.insert(0, "【今日分享】")
    lines.insert(1, "")
    return "\n".join(lines)


def _format_medium(content: str) -> str:
    """Medium 格式：保留 markdown"""
    return content


def _format_quora(content: str) -> str:
    """Quora 格式：转为问答体"""
    return f"## {content}\n\n---\n*Answer based on research and analysis.*"


def _format_reddit(content: str) -> str:
    """Reddit 格式：简洁，纯文本为主"""
    # 去除图片引用和复杂格式
    import re
    text = re.sub(r"!\[.*?\]\(.*?\)", "", content)
    return text


# --- 快捷测试 ---
def main():
    from geo_optimizer.config import load_config
    from geo_optimizer.generators.content import OptimizedContent
    from geo_optimizer.generators.faq import FAQItem
    logging.basicConfig(level=logging.INFO)

    config = load_config()
    oc = OptimizedContent(
        original_url="https://example.com",
        target_engine="豆包",
        optimized_title="2024年最佳清洁机器人推荐",
        optimized_meta_desc="帮你找到最适合的智能清洁机器人",
        optimized_text="智能清洁机器人已经成为现代家庭的标配...",
        faq_items=[FAQItem("清洁机器人好用吗？", "非常好用，特别是对于忙碌的上班族。", "zh-CN")],
        schema_json_ld="",
        improvements=["提升权威性", "增加场景词"],
    )

    exporter = GEOExporter(config)
    results = exporter.export_all([oc], [oc.faq_items[0]])

    for r in results:
        print(f"Exported: {r.platform} -> {r.filename}")


if __name__ == "__main__":
    main()
