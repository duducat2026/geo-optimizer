# -*- coding: utf-8 -*-
"""增强版 Markdown 分析报告：总分 + 技术体检 + 每引擎独立小节。

支持单语输出：build_markdown(result, lang="zh" | "en")，供打包时生成
zh/ 与 en/ 两套报告文件。维度名/引擎名/厂商名/focus 词均为固定术语，
用内置中英映射表翻译，不消耗 LLM 调用。
"""

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

# 评分维度中英标签（与 analyzer.CN_DIMENSIONS / EN_DIMENSIONS 的键一致）
DIMENSION_LABELS = {
    "结构化": ("结构化", "Structure"),
    "口语化": ("口语化", "Conversational tone"),
    "权威性": ("权威性", "Authoritativeness"),
    "关键词覆盖": ("关键词覆盖", "Keyword coverage"),
    "生活场景": ("生活场景", "Everyday scenarios"),
    "技术深度": ("技术深度", "Technical depth"),
    "E-E-A-T": ("E-E-A-T", "E-E-A-T"),
    "引用标注": ("引用标注", "Citations & sourcing"),
    "内容深度": ("内容深度", "Content depth"),
    "可读性": ("可读性", "Readability"),
}

# 引擎展示名（国外引擎本已是英文，国内引擎补英文名）
ENGINE_LABELS = {
    "豆包": ("豆包", "Doubao"),
    "通义千问": ("通义千问", "Tongyi Qianwen (Qwen)"),
    "混元": ("混元", "Tencent Hunyuan"),
    "智谱清言": ("智谱清言", "ChatGLM (Zhipu)"),
    "DeepSeek": ("DeepSeek", "DeepSeek"),
    "Google AI Overviews": ("Google AI Overviews", "Google AI Overviews"),
    "ChatGPT Search": ("ChatGPT Search", "ChatGPT Search"),
    "Perplexity": ("Perplexity", "Perplexity"),
    "Claude": ("Claude", "Claude"),
    "Copilot": ("Copilot", "Copilot"),
    "Gemini": ("Gemini", "Gemini"),
}

VENDOR_LABELS = {
    "字节跳动": ("字节跳动", "ByteDance"),
    "阿里巴巴": ("阿里巴巴", "Alibaba"),
    "腾讯": ("腾讯", "Tencent"),
    "智谱AI": ("智谱AI", "Zhipu AI"),
    "深度求索": ("深度求索", "High-Flyer AI"),
    "Google": ("Google", "Google"),
    "OpenAI": ("OpenAI", "OpenAI"),
    "Perplexity AI": ("Perplexity AI", "Perplexity AI"),
    "Anthropic": ("Anthropic", "Anthropic"),
    "Microsoft": ("Microsoft", "Microsoft"),
}

# 引擎 focus 词（来自 geo_config.yaml engines_*.focus）
FOCUS_LABELS = {
    "结构化": ("结构化", "structured content"),
    "口语化": ("口语化", "conversational phrasing"),
    "生活场景": ("生活场景", "everyday scenarios"),
    "权威来源": ("权威来源", "authoritative sources"),
    "数据支撑": ("数据支撑", "data backing"),
    "微信生态": ("微信生态", "WeChat ecosystem"),
    "公众号格式": ("公众号格式", "official-account format"),
    "学术引用": ("学术引用", "academic citations"),
    "专业深度": ("专业深度", "professional depth"),
    "精准回答": ("精准回答", "precise answers"),
    "代码块": ("代码块", "code blocks"),
    "E-E-A-T": ("E-E-A-T", "E-E-A-T"),
    "Schema": ("Schema", "schema markup"),
    "权威引用": ("权威引用", "authoritative citations"),
    "自然对话体": ("自然对话体", "natural conversational style"),
    "长尾问答": ("长尾问答", "long-tail Q&A"),
    "来源链接": ("来源链接", "source links"),
    "引用标注": ("引用标注", "explicit attribution"),
    "深度分析": ("深度分析", "in-depth analysis"),
    "结构化输出": ("结构化输出", "structured output"),
    "Bing索引": ("Bing索引", "Bing indexing"),
    "权威背书": ("权威背书", "expert endorsement"),
    "多模态": ("多模态", "multimodality"),
    "Google生态": ("Google生态", "Google ecosystem"),
}

_PRIO_MARK = {"red": ("[高]", "[High]"), "yellow": ("[中]", "[Medium]"),
              "green": ("[低]", "[Low]")}

_LANG_IDX = {"zh": 0, "en": 1}

# 报告固定文案
_T = {
    "title": ("GEO 适配分析报告", "GEO Analysis Report"),
    "url": ("URL", "URL"),
    "language": ("页面语言", "Page language"),
    "overall": ("综合得分", "Overall Score"),
    "audit": ("页面技术体检", "Page Technical Audit"),
    "issues": ("主要问题", "Key Issues"),
    "strengths": ("已有优势", "Existing Strengths"),
    "priorities": ("优先级排序建议", "Priority Order"),
    "estimate": ("优化后预计可提升到 **{min:.0f}-{max:.0f} 分**",
                 "Estimated score after fixes: **{min:.0f}-{max:.0f}**"),
    "engines": ("分引擎评估", "Per-Engine Evaluation"),
    "dim_header": ("维度", "Dimension"),
    "score_header": ("得分", "Score"),
    "suggestions": ("改进建议", "Suggestions"),
    "no_suggestions": ("无显著短板", "No major gaps detected"),
    "score_of": ("/100", "/100"),
    "sug_tpl": ("提升「{dim}」（当前 {score} 分），重点关注：{focus}",
                 "Improve {dim} (currently {score}/100); focus on: {focus}"),
}


def _pair(mapping: dict, key: str, lang: str) -> str:
    zh, en = mapping.get(key, (key, key))
    return zh if lang == "zh" else en


def label(key: str, lang: str | None = None) -> str:
    """体检项标签。lang 为 None 时返回既有的「中文 / English」双语形式。"""
    zh, en = AUDIT_LABELS.get(key, (key, key))
    if lang is None:
        return f"{zh} / {en}"
    return zh if lang == "zh" else en


def dimension_label(dim: str, lang: str) -> str:
    return _pair(DIMENSION_LABELS, dim, lang)


def engine_label(engine: str, lang: str) -> str:
    return _pair(ENGINE_LABELS, engine, lang)


def build_markdown(result: dict, lang: str = "zh") -> str:
    """由序列化任务结果生成单语 Markdown 报告（lang: zh / en）。"""
    lang = lang if lang in _LANG_IDX else "zh"
    idx = _LANG_IDX[lang]
    lines = [
        f"# {_T['title'][idx]}",
        "",
        f"**{_T['url'][idx]}:** {result.get('url', '')}",
        f"**{_T['language'][idx]}:** {result.get('language', '')}",
        f"**{_T['overall'][idx]}:** {result.get('overall_score', 0)}"
        f"{_T['score_of'][idx]}",
        "",
    ]
    lines += _audit_section(result.get("page_audit") or {}, lang, idx)
    lines += _engine_sections(result.get("engine_scores") or [], lang, idx)
    return "\n".join(lines)


def _audit_section(audit: dict, lang: str, idx: int) -> list:
    if not audit:
        return []
    lines = [f"## {_T['audit'][idx]}", ""]

    issues = [c for c in audit.get("checks", []) if not c["ok"]]
    if issues:
        lines.append(f"### {_T['issues'][idx]}")
        for c in issues:
            mark = _PRIO_MARK.get(c["severity"], ("", ""))[idx]
            lines.append(f"- {mark} {label(c['key'], lang)}（{c['value']}）"
                         if lang == "zh"
                         else f"- {mark} {label(c['key'], lang)} ({c['value']})")
        lines.append("")

    strengths = audit.get("strengths", [])
    if strengths:
        lines.append(f"### {_T['strengths'][idx]}")
        for key in strengths:
            lines.append(f"- {label(key, lang)}")
        lines.append("")

    if audit.get("priorities"):
        lines.append(f"### {_T['priorities'][idx]}")
        for i, key in enumerate(audit["priorities"], 1):
            lines.append(f"{i}. {label(key, lang)}")
        lines.append("")

    est = audit.get("estimate")
    if est and est.get("gain"):
        lines.append(_T["estimate"][idx].format(min=est["min"], max=est["max"]))
        lines.append("")
    return lines


def _engine_sections(engine_scores: list, lang: str, idx: int) -> list:
    if not engine_scores:
        return []
    lines = [f"## {_T['engines'][idx]}", ""]
    for es in engine_scores:
        engine = engine_label(es.get("engine", ""), lang)
        vendor = _pair(VENDOR_LABELS, es.get("vendor", ""), lang)
        lines.append(f"### {engine}（{vendor}）— {es['score']}{_T['score_of'][idx]}"
                     if lang == "zh"
                     else f"### {engine} ({vendor}) — {es['score']}{_T['score_of'][idx]}")
        breakdown = es.get("breakdown") or {}
        if breakdown:
            lines.append("")
            lines.append(f"| {_T['dim_header'][idx]} | {_T['score_header'][idx]} |")
            lines.append("|------|------|")
            for dim, score in breakdown.items():
                lines.append(f"| {dimension_label(dim, lang)} | {score} |")
        suggestions = _suggestions(es, lang, idx)
        if suggestions:
            lines.append("")
            lines.append(f"{_T['suggestions'][idx]}:")
            for sug in suggestions:
                lines.append(f"- {sug}")
        lines.append("")
    return lines


def _suggestions(es: dict, lang: str, idx: int) -> list:
    """按维度短板与引擎 focus 重排建议，使中英两份报告口径一致。

    引擎原始 suggestions 只带单一语言（国内引擎中文、国外引擎英文），直接沿用会
    让报告出现混语；这里统一由 breakdown + focus 映射生成。无 focus 数据时
    回退原始建议。
    """
    focus_terms = es.get("focus") or []
    if not focus_terms:
        return list(es.get("suggestions") or [])

    focus = ", ".join(_pair(FOCUS_LABELS, f, lang) for f in focus_terms)
    out = []
    for dim, score in (es.get("breakdown") or {}).items():
        if score < 50:
            out.append(_T["sug_tpl"][idx].format(dim=dimension_label(dim, lang),
                                                 score=score, focus=focus))
    return out
