#!/usr/bin/env python3
"""
geo_report.py — GEO 分析报告生成模块
生成 Markdown 和 HTML 格式的综合分析报告
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from geo_optimizer.analyzer import GEOAnalysisReport
from geo_optimizer.crawler import CrawledPage
from geo_optimizer.generators.content import OptimizedContent
from geo_optimizer.generators.faq import FAQItem

logger = logging.getLogger(__name__)


@dataclass
class ReportResult:
    """报告生成结果"""
    markdown: str
    html: str = ""
    summary: str = ""


class GEOReportGenerator:
    """GEO 分析报告生成器"""

    def __init__(self, config: dict):
        self.config = config

    def generate(
        self,
        page: CrawledPage,
        analysis: GEOAnalysisReport,
        optimized: list[OptimizedContent],
        faqs: list[FAQItem],
    ) -> ReportResult:
        """生成完整的分析报告"""
        md = self._build_markdown(page, analysis, optimized, faqs)
        html = self._build_html(page, analysis, optimized, faqs)
        summary = self._build_summary(analysis)
        return ReportResult(markdown=md, html=html, summary=summary)

    # ─────────── Markdown 报告 ───────────

    def _build_markdown(
        self,
        page: CrawledPage,
        analysis: GEOAnalysisReport,
        optimized: list[OptimizedContent],
        faqs: list[FAQItem],
    ) -> str:
        lines = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines.append(f"# GEO 分析报告")
        lines.append(f"")
        lines.append(f"**生成时间**: {now}")
        lines.append(f"**目标 URL**: {page.url}")
        lines.append(f"**页面标题**: {page.title}")
        lines.append(f"")

        # 概览
        lines.append("## 📊 综合评分")
        lines.append("")
        lines.append(f"| 指标 | 得分 |")
        lines.append(f"|------|------|")
        lines.append(f"| **总分** | **{analysis.total_score}/100** |")
        for engine, score in analysis.engine_scores_dict.items():
            lines.append(f"| {engine} | {score}/100 |")
        lines.append("")

        # 优势
        if analysis.strengths:
            lines.append("## ✅ 优势")
            lines.append("")
            for s in analysis.strengths:
                lines.append(f"- {s}")
            lines.append("")

        # 建议
        if analysis.suggestions:
            lines.append("## 🔧 改进建议")
            lines.append("")
            for s in analysis.suggestions:
                lines.append(f"- {s}")
            lines.append("")

        # 各引擎详情
        lines.append("## 🔍 各引擎详细评分")
        lines.append("")
        for s in analysis.engine_scores:
            lines.append(f"### {s.engine} ({s.score}/100)")
            lines.append("")
            if s.details:
                for k, v in s.details.items():
                    lines.append(f"- **{k}**: {v}")
                lines.append("")
            if s.suggestions:
                lines.append("**建议**: ")
                for sug in s.suggestions:
                    lines.append(f"  - {sug}")
                lines.append("")

        # 优化内容统计
        if optimized:
            lines.append("## 📝 优化内容")
            lines.append("")
            for oc in optimized:
                lines.append(f"### {oc.language}")
                lines.append(f"- 优化段落数: {len(oc.optimized_paragraphs)}")
                lines.append(f"- 新增 FAQ: {oc.faq_count}")
                lines.append(f"- 优化后词数: {oc.word_count_after}")
                lines.append("")

        # FAQ
        if faqs:
            lines.append("## ❓ 生成的 FAQ")
            lines.append("")
            for i, faq in enumerate(faqs, 1):
                lines.append(f"**Q{i}: {faq.question}**")
                lines.append(f"  {faq.answer}")
                lines.append("")

        # 行动清单
        lines.append("## 🎯 优先行动清单")
        lines.append("")
        priority = self._get_priority_actions(analysis)
        for i, action in enumerate(priority, 1):
            lines.append(f"{i}. {action}")
        lines.append("")

        return "\n".join(lines)

    # ─────────── HTML 报告 ───────────

    def _build_html(
        self,
        page: CrawledPage,
        analysis: GEOAnalysisReport,
        optimized: list[OptimizedContent],
        faqs: list[FAQItem],
    ) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GEO 分析报告 - {page.title}</title>
<style>
  body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; max-width: 900px; margin: 0 auto; padding: 2rem; color: #333; line-height: 1.6; }}
  h1 {{ color: #1a1a2e; border-bottom: 3px solid #4361ee; padding-bottom: 0.5rem; }}
  h2 {{ color: #16213e; margin-top: 2rem; }}
  h3 {{ color: #0f3460; }}
  .score {{ font-size: 3rem; font-weight: bold; color: #4361ee; text-align: center; margin: 1rem 0; }}
  .score-good {{ color: #2dc653; }}
  .score-warn {{ color: #f9a825; }}
  .score-bad {{ color: #e63946; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #ddd; padding: 0.75rem; text-align: left; }}
  th {{ background: #f0f0f5; }}
  tr:nth-child(even) {{ background: #fafafa; }}
  .card {{ background: #f8f9fa; border-radius: 8px; padding: 1.5rem; margin: 1rem 0; border-left: 4px solid #4361ee; }}
  .suggestion {{ padding: 0.5rem 0; border-bottom: 1px solid #eee; }}
  .faq-q {{ font-weight: bold; color: #16213e; }}
  .footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #ddd; color: #888; font-size: 0.85rem; }}
</style>
</head>
<body>

<h1>🔬 GEO 分析报告</h1>
<p>生成时间: {now} | 目标: <a href="{page.url}">{page.url}</a></p>

<div class="score {self._score_class(analysis.total_score)}">
  {analysis.total_score}/100
</div>
<p style="text-align:center; color:#666;">综合 GEO 就绪度评分</p>

<h2>📊 各引擎评分</h2>
<table>
  <tr><th>引擎</th><th>得分</th><th>评级</th></tr>
"""
        for s in analysis.engine_scores:
            grade = "优秀" if s.score >= 80 else "良好" if s.score >= 60 else "需改进"
            cls = "score-good" if s.score >= 80 else "score-warn" if s.score >= 60 else "score-bad"
            html += f'  <tr><td>{s.engine}</td><td class="{cls}">{s.score}/100</td><td>{grade}</td></tr>\n'

        html += """</table>

<h2>✅ 优势</h2>
<div class="card">
"""
        for s in analysis.strengths:
            html += f"<div class='suggestion'>✅ {s}</div>\n"
        html += "</div>\n"

        html += """<h2>🔧 改进建议</h2>
<div class="card">
"""
        for s in analysis.suggestions:
            html += f"<div class='suggestion'>🔧 {s}</div>\n"
        html += "</div>\n"

        # FAQ
        if faqs:
            html += """<h2>❓ 推荐 FAQ</h2>
<div class="card">
"""
            for i, faq in enumerate(faqs, 1):
                html += f"<p class='faq-q'>Q{i}: {faq.question}</p><p>{faq.answer}</p>\n"
            html += "</div>\n"

        # 行动清单
        html += """<h2>🎯 优先行动清单</h2>
<ol>
"""
        for action in self._get_priority_actions(analysis):
            html += f"<li>{action}</li>\n"
        html += """</ol>

<div class="footer">
  <p>由 GEO-Optimizer 自动生成 | """ + now + """</p>
</div>

</body>
</html>"""

        return html

    # ─────────── 辅助方法 ───────────

    def _build_summary(self, analysis: GEOAnalysisReport) -> str:
        """生成简短摘要"""
        score = analysis.total_score
        if score >= 80:
            level = "优秀"
        elif score >= 60:
            level = "良好"
        elif score >= 40:
            level = "一般"
        else:
            level = "需大幅改进"

        cited = sum(1 for s in analysis.engine_scores if s.score >= 70)
        total = len(analysis.engine_scores)

        return (
            f"GEO 综合评分: {score}/100 ({level})\n"
            f"{cited}/{total} 个引擎可达良好水平\n"
            f"建议: {' 优先处理' if score < 60 else ' 持续优化' if score < 80 else ' 保持现状'}"
        )

    def _get_priority_actions(self, analysis: GEOAnalysisReport) -> list[str]:
        """生成优先行动清单"""
        actions = []
        for s in analysis.engine_scores:
            if s.score < 60:
                actions.append(f"【紧急】{s.engine} 评分仅 {s.score}，{s.suggestions[0] if s.suggestions else '需要全面优化'}")
            elif s.score < 80:
                if s.suggestions:
                    actions.append(f"【建议】{s.engine}: {s.suggestions[0]}")

        # 通用建议
        if analysis.total_score < 50:
            actions.insert(0, "🚨 综合评分低于 50，建议全面重构页面内容结构")

        if not actions:
            actions.append("当前状态良好，建议定期监控各引擎引用情况")

        return actions[:10]  # 最多 10 条

    @staticmethod
    def _score_class(score: int) -> str:
        if score >= 80:
            return "score-good"
        elif score >= 60:
            return "score-warn"
        return "score-bad"
