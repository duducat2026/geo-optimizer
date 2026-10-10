# -*- coding: utf-8 -*-
"""产出物目录：定义每个改进方案条目可生成的具体文件（规则/LLM）与生成指令。"""

# mode: rule=规则即时生成（sitemap/robots）；llm=结合站点实际内容由 LLM 生成
SPECS: dict[str, list[dict]] = {
    "sitemap_optimize": [
        {
            "kind": "sitemap_xml", "filename": "sitemap.xml", "mode": "rule",
            "title": {"zh": "sitemap.xml（基于实际爬取链接）",
                      "en": "sitemap.xml (from crawled links)"},
        },
        {
            "kind": "robots_txt", "filename": "robots.txt", "mode": "rule",
            "title": {"zh": "robots.txt（放行 AI 爬虫 + Sitemap 声明）",
                      "en": "robots.txt (AI crawlers allowed + Sitemap line)"},
        },
    ],
    "faq_block": [
        {
            "kind": "faq_html", "filename": "faq_section.html", "mode": "llm",
            "title": {"zh": "FAQ 区块 HTML（含 FAQPage JSON-LD，可直接嵌入）",
                      "en": "FAQ section HTML (with FAQPage JSON-LD, embeddable)"},
            "instruction": ("生成一个可直接嵌入网页的 FAQ 区块：包含 5-8 组该网站业务相关的"
                            "常见问题与直接回答（HTML 结构，中文），并在末尾附上对应的 "
                            "FAQPage JSON-LD <script> 标签。只输出 HTML 代码。"),
        },
    ],
    "zhihu_qa": [
        {
            "kind": "zhihu_article", "filename": "zhihu_article.md", "mode": "llm",
            "title": {"zh": "知乎回答/文章草稿（中文，可直接发布）",
                      "en": "Zhihu answer/article draft (Chinese, ready to post)"},
            "instruction": ("撰写一篇可直接发布的知乎专业回答（中文，Markdown）：先给出一个该"
                            "业务领域用户常搜的问题作为标题，然后以专业身份分点作答（含数据、"
                            "案例），结尾自然提及品牌名与官网地址，800 字左右。"),
        },
    ],
    "wechat_mp": [
        {
            "kind": "wechat_article", "filename": "wechat_article.md", "mode": "llm",
            "title": {"zh": "公众号文章草稿（中文）",
                      "en": "WeChat article draft (Chinese)"},
            "instruction": ("撰写一篇微信公众号原创文章草稿（中文，Markdown）：标题包含核心业务"
                            "关键词，正文分小节介绍业务价值与使用场景，文末注明品牌名与官网，"
                            "900 字左右。"),
        },
    ],
    "toutiao_sync": [
        {
            "kind": "toutiao_article", "filename": "toutiao_article.md", "mode": "llm",
            "title": {"zh": "百家号/头条号文章草稿（改写自官网内容）",
                      "en": "Baijiahao/Toutiao article draft (rewritten)"},
            "instruction": ("基于该网站内容改写一篇适合百家号/头条号发布的文章（中文，Markdown，"
                            "避免与原文重复表述），资讯化叙述风格，文末标注品牌与官网，800 字左右。"),
        },
    ],
    "baidu_baike": [
        {
            "kind": "baike_entry", "filename": "baike_entry.md", "mode": "llm",
            "title": {"zh": "百度百科词条草稿（客观中立 + 参考资料位）",
                      "en": "Baidu Baike entry draft (neutral + references)"},
            "instruction": ("撰写百度百科品牌词条草稿（中文，Markdown）：包含概述、发展历程、"
                            "主要产品/服务、参考资料四节；措辞客观中立无广告语，每个关键信息"
                            "后标注 [参考资料待补] 占位。"),
        },
    ],
    "baidu_zhidao": [
        {
            "kind": "zhidao_qa", "filename": "zhidao_qa.md", "mode": "llm",
            "title": {"zh": "百度知道问答素材（5 组问答）",
                      "en": "Baidu Zhidao Q&A material (5 pairs)"},
            "instruction": ("生成 5 组适合百度知道的问答素材（中文，Markdown）：问题贴近用户"
                            "真实搜索意图，回答客观中立、80-150 字、避免广告用语，其中 1-2 条"
                            "自然提及品牌名。"),
        },
    ],
    "authority_citation": [
        {
            "kind": "wiki_draft_en", "filename": "wikipedia_draft_en.md", "mode": "llm",
            "title": {"zh": "Wikipedia 英文词条草稿（中立百科体 + 引用占位）",
                      "en": "English Wikipedia entry draft (neutral + citation slots)"},
            "instruction": ("Write an English Wikipedia-style entry draft (Markdown) for this "
                            "brand: neutral encyclopedic tone, sections for Overview, History, "
                            "Products/Services and References; mark each claim with [citation "
                            "needed] placeholders. Output English only."),
        },
        {
            "kind": "press_release_en", "filename": "press_release_en.md", "mode": "llm",
            "title": {"zh": "英文新闻稿草稿（PR Newswire 格式）",
                      "en": "English press release draft (PR Newswire style)"},
            "instruction": ("Write an English press release draft (Markdown, PR Newswire style) "
                            "based on this site's business: headline, dateline placeholder, lead "
                            "paragraph, body with a quote placeholder, boilerplate 'About' section "
                            "with the website URL. Output English only."),
        },
    ],
    "en_qa_community": [
        {
            "kind": "medium_article_en", "filename": "medium_article_en.md", "mode": "llm",
            "title": {"zh": "Medium 英文深度文章草稿",
                      "en": "Medium in-depth article draft (English)"},
            "instruction": ("Write an in-depth English Medium article draft (Markdown, ~700 words) "
                            "about the problem this site solves: practical insights, subheadings, "
                            "a natural mention of the brand with a link back to the site. "
                            "Output English only."),
        },
        {
            "kind": "quora_answers_en", "filename": "quora_answers_en.md", "mode": "llm",
            "title": {"zh": "Quora 英文回答素材（3 组）",
                      "en": "Quora answer material (3 pairs, English)"},
            "instruction": ("Write 3 English Quora question-and-answer pairs relevant to this "
                            "site's business (Markdown): expert tone, concrete advice, one answer "
                            "naturally mentions the brand and website. Output English only."),
        },
    ],
    "geo_subpage": [
        {
            "kind": "geo_page_html", "filename": "geo_page.html", "mode": "llm",
            "title": {"zh": "GEO 专页 HTML（品牌介绍 + FAQ + Organization JSON-LD）",
                      "en": "GEO landing page HTML (intro + FAQ + Organization JSON-LD)"},
            "instruction": ("生成一个完整的 GEO 专页 HTML（中文，单文件）：包含品牌/业务介绍、"
                            "核心优势列表、5 组 FAQ，以及 Organization 与 FAQPage 两段 JSON-LD "
                            "<script>。只输出 HTML 代码。"),
        },
    ],
}


def specs_for(code: str) -> list[dict]:
    """返回条目可生成的产出物规格列表（无则为空列表）。"""
    return SPECS.get(code, [])


def get_spec(code: str, kind: str) -> dict | None:
    for spec in specs_for(code):
        if spec["kind"] == kind:
            return spec
    return None
