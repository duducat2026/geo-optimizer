# -*- coding: utf-8 -*-
"""增强版 Markdown 分析报告：总分 + 技术体检 + 每引擎独立小节。"""

# 体检项双语标签
AUDIT_LABELS = {
    "https": ("HTTPS 加密", "HTTPS"),
    "headings": ("标题结构 (H1/H2/H3)", "Heading structure (H1/H2/H3)"),
    "meta_desc": ("Meta Description", "Meta description"),
    "schema": ("结构化数据 (JSON-LD)", "Structured data (JSON-LD)"),
    "faq": ("FAQ 区块", "FAQ section"),
    "author_date": ("作者/日期信息 (E-E-A-T)", "Author/date info (E-E-A-T)"),
    "img_alt": ("图片 alt 文本", "Image alt text"),
    "content_volume": ("内容量充足", "Sufficient content volume"),
    "rich_lists": ("列表结构丰富", "Rich list structure"),
    "internal_links": ("内链充足", "Sufficient internal links"),
    "fast_load": ("加载速度快", "Fast loading"),
}

_PRIO_MARK = {"red": "[高]", "yellow": "[中]", "green": "[低]"}


def label(key: str) -> str:
    zh, en = AUDIT_LABELS.get(key, (key, key))
    return f"{zh} / {en}"


def build_markdown(result: dict) -> str:
    """由序列化任务结果生成双语 Markdown 报告。"""
    lines = [
        "# GEO 适配分析报告 / GEO Analysis Report",
        "",
        f"**URL:** {result.get('url', '')}",
        f"**语言 / Language:** {result.get('language', '')}",
        f"**综合得分 / Overall Score:** {result.get('overall_score', 0)}/100",
        "",
    ]
    lines += _audit_section(result.get("page_audit") or {})
    lines += _engine_sections(result.get("engine_scores") or [])
    return "\n".join(lines)


def _audit_section(audit: dict) -> list:
    if not audit:
        return []
    lines = ["## 页面技术体检 / Page Technical Audit", ""]

    issues = [c for c in audit.get("checks", []) if not c["ok"]]
    if issues:
        lines.append("### 主要问题 / Key Issues")
        for c in issues:
            lines.append(f"- {_PRIO_MARK.get(c['severity'], '')} {label(c['key'])}"
                         f"（{c['value']}）")
        lines.append("")

    strengths = audit.get("strengths", [])
    if strengths:
        lines.append("### 已有优势 / Existing Strengths")
        for key in strengths:
            lines.append(f"- {label(key)}")
        lines.append("")

    if audit.get("priorities"):
        lines.append("### 优先级排序建议 / Priority Order")
        for i, key in enumerate(audit["priorities"], 1):
            lines.append(f"{i}. {label(key)}")
        lines.append("")

    est = audit.get("estimate")
    if est and est.get("gain"):
        lines.append(f"优化后预计可提升到 **{est['min']:.0f}-{est['max']:.0f} 分** / "
                     f"Estimated score after fixes: **{est['min']:.0f}-{est['max']:.0f}**")
        lines.append("")
    return lines


def _engine_sections(engine_scores: list) -> list:
    if not engine_scores:
        return []
    lines = ["## 分引擎评估 / Per-Engine Evaluation", ""]
    for es in engine_scores:
        lines.append(f"### {es['engine']}（{es['vendor']}）— {es['score']}/100")
        breakdown = es.get("breakdown") or {}
        if breakdown:
            lines.append("")
            lines.append("| 维度 / Dimension | 得分 / Score |")
            lines.append("|------|------|")
            for dim, score in breakdown.items():
                lines.append(f"| {dim} | {score} |")
        suggestions = es.get("suggestions") or []
        if suggestions:
            lines.append("")
            lines.append("改进建议 / Suggestions:")
            for sug in suggestions:
                lines.append(f"- {sug}")
        lines.append("")
    return lines
