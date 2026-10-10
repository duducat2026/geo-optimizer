# -*- coding: utf-8 -*-
"""优化指导页内置双语内容：AI 搜索引擎 GEO 提交入口与国内模型收录机制。

结构化数据，值为 {"zh": ..., "en": ...}，模板按 current_locale 取值。
"""

# --- 有官方提交/管理平台 ---
PORTALS = [
    {
        "platform": {"zh": "Google", "en": "Google"},
        "entry": "Google Search Console",
        "url": "https://search.google.com/search-console",
        "note": {"zh": "提交 Sitemap，AI Overviews 依赖 Google 索引",
                 "en": "Submit sitemap; AI Overviews rely on Google index"},
    },
    {
        "platform": {"zh": "Bing / Copilot", "en": "Bing / Copilot"},
        "entry": "Bing Webmaster Tools",
        "url": "https://www.bing.com/webmasters",
        "note": {"zh": "一次提交同时覆盖 Bing 搜索和 Copilot AI",
                 "en": "One submission covers both Bing Search and Copilot AI"},
    },
    {
        "platform": {"zh": "Perplexity", "en": "Perplexity"},
        "entry": "Perplexity Publisher Portal",
        "url": "https://publisher.perplexity.ai",
        "note": {"zh": "专属发布者后台，可管理内容如何被引用、设置引用展示样式",
                 "en": "Publisher portal to manage how content is cited and displayed"},
    },
    {
        "platform": {"zh": "百度", "en": "Baidu"},
        "entry": {"zh": "百度搜索资源平台", "en": "Baidu Search Resource Platform"},
        "url": "https://ziyuan.baidu.com",
        "note": {"zh": "文心一言等国内 AI 依赖百度索引",
                 "en": "Ernie Bot and other domestic AI rely on Baidu index"},
    },
    {
        "platform": {"zh": "神马/夸克", "en": "Shenma / Quark"},
        "entry": {"zh": "神马站长", "en": "Shenma Webmaster"},
        "url": "https://zhanzhang.sm.cn",
        "note": {"zh": "国内移动端 AI 搜索", "en": "Domestic mobile AI search"},
    },
]

# --- 无直接提交，但有控制机制 ---
NO_PORTAL = [
    {
        "platform": {"zh": "ChatGPT Search", "en": "ChatGPT Search"},
        "mechanism": {"zh": "爬虫自动抓取", "en": "Auto crawling"},
        "note": {"zh": "通过 robots.txt 的 GPTBot 控制；无提交入口，靠自然索引",
                 "en": "Controlled via GPTBot in robots.txt; no submission portal"},
    },
    {
        "platform": {"zh": "Claude (Anthropic)", "en": "Claude (Anthropic)"},
        "mechanism": {"zh": "爬虫自动抓取", "en": "Auto crawling"},
        "note": {"zh": "通过 robots.txt 的 ClaudeBot 控制；无提交入口",
                 "en": "Controlled via ClaudeBot in robots.txt; no submission portal"},
    },
    {
        "platform": {"zh": "Kimi/文心/通义", "en": "Kimi / Ernie / Qwen"},
        "mechanism": {"zh": "依赖搜索引擎索引", "en": "Rely on search engine index"},
        "note": {"zh": "主要复用百度/Google 索引，做好基础站长提交即可",
                 "en": "Mostly reuse Baidu/Google index; basic webmaster submission suffices"},
    },
]

# --- robots.txt 技术控制示例 ---
ROBOTS_TXT = """# 允许所有 AI 爬虫抓取 / Allow all AI crawlers
User-agent: GPTBot
Allow: /

User-agent: CCBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /"""

# --- 实操优先级 ---
PRIORITY_STEPS = [
    {"zh": "Google Search Console — 提交 sitemap，确保收录（最高优先级）",
     "en": "Google Search Console — submit sitemap, ensure indexing (top priority)"},
    {"zh": "Bing Webmaster Tools — 顺带覆盖 Copilot",
     "en": "Bing Webmaster Tools — also covers Copilot"},
    {"zh": "Perplexity Publisher Portal — 注册并认领站点",
     "en": "Perplexity Publisher Portal — register and claim your site"},
    {"zh": "百度搜索资源平台 — 国内 AI 的索引基础",
     "en": "Baidu Search Resource Platform — index base for domestic AI"},
    {"zh": "检查 robots.txt — 确保 GPTBot、ClaudeBot 等未被屏蔽",
     "en": "Check robots.txt — make sure GPTBot, ClaudeBot etc. are not blocked"},
]

# --- 国内主流 AI 模型收录机制 ---
CN_MODELS = [
    {
        "name": {"zh": "千问（通义千问 / Qwen）", "en": "Qwen (Tongyi Qianwen)"},
        "company": {"zh": "阿里", "en": "Alibaba"},
        "index_source": {"zh": "神马搜索 + 自有爬虫 + 夸克搜索",
                         "en": "Shenma Search + own crawler + Quark Search"},
        "portal": {"zh": "无直接 AI 提交，走搜索引擎站长平台",
                   "en": "No direct AI submission; use search webmaster platforms"},
        "actions": [
            {"zh": "提交到神马站长 (zhanzhang.sm.cn)", "en": "Submit to Shenma Webmaster (zhanzhang.sm.cn)"},
            {"zh": "提交到夸克站长 (quark.sm.cn)", "en": "Submit to Quark Webmaster (quark.sm.cn)"},
            {"zh": "做好 Schema.org 结构化数据（千问首页本身就在用 JSON-LD）",
             "en": "Add Schema.org structured data (Qwen homepage itself uses JSON-LD)"},
        ],
        "crawler": {"zh": "暂无公开专属爬虫名，复用神马/夸克爬虫",
                    "en": "No public dedicated crawler; reuses Shenma/Quark crawlers"},
        "tip": None,
    },
    {
        "name": {"zh": "豆包（字节跳动）", "en": "Doubao (ByteDance)"},
        "company": {"zh": "字节跳动", "en": "ByteDance"},
        "index_source": {"zh": "今日头条/抖音内容生态 + 自有爬虫",
                         "en": "Toutiao/Douyin content ecosystem + own crawler"},
        "portal": {"zh": "无公开站长提交入口", "en": "No public webmaster submission portal"},
        "actions": [
            {"zh": "内容发布到今日头条/头条号（豆包优先引用头条生态内容）",
             "en": "Publish content on Toutiao (Doubao prefers Toutiao ecosystem content)"},
            {"zh": "做好基础 SEO，确保被爬虫抓取", "en": "Solid basic SEO so crawlers can fetch"},
            {"zh": "robots.txt 不屏蔽", "en": "Do not block in robots.txt"},
        ],
        "crawler": {"zh": "暂无公开专属爬虫名", "en": "No public dedicated crawler name"},
        "tip": {"zh": "豆包对头条号/抖音发布的内容有明显偏好，建议把内容同步发到头条号",
                "en": "Doubao clearly prefers Toutiao/Douyin content; sync your content there"},
    },
    {
        "name": {"zh": "腾讯混元", "en": "Tencent Hunyuan"},
        "company": {"zh": "腾讯", "en": "Tencent"},
        "index_source": {"zh": "微信公众号 + 搜狗搜索 + 腾讯内容生态",
                         "en": "WeChat Official Accounts + Sogou Search + Tencent ecosystem"},
        "portal": {"zh": "无直接 AI 提交", "en": "No direct AI submission"},
        "actions": [
            {"zh": "运营微信公众号（混元优先引用公众号内容）",
             "en": "Run a WeChat Official Account (Hunyuan prefers its content)"},
            {"zh": "提交到搜狗站长 (zhanzhang.sogou.com)", "en": "Submit to Sogou Webmaster (zhanzhang.sogou.com)"},
            {"zh": "确保在微信生态有内容存在", "en": "Ensure presence in the WeChat ecosystem"},
        ],
        "crawler": {"zh": "复用搜狗爬虫", "en": "Reuses Sogou crawler"},
        "tip": {"zh": "混元对微信公众号文章有明显偏好，建议开通公众号",
                "en": "Hunyuan clearly prefers WeChat articles; open an Official Account"},
    },
    {
        "name": {"zh": "文心一言（百度）", "en": "Ernie Bot (Baidu)"},
        "company": {"zh": "百度", "en": "Baidu"},
        "index_source": {"zh": "百度搜索索引", "en": "Baidu search index"},
        "portal": {"zh": "百度搜索资源平台 (ziyuan.baidu.com)",
                   "en": "Baidu Search Resource Platform (ziyuan.baidu.com)"},
        "actions": [
            {"zh": "注册百度站长，提交 sitemap", "en": "Register Baidu Webmaster and submit sitemap"},
            {"zh": "使用百度天级收录接口", "en": "Use Baidu daily-inclusion API"},
            {"zh": "做好百度 site 验证", "en": "Complete Baidu site verification"},
        ],
        "crawler": {"zh": "Baiduspider", "en": "Baiduspider"},
        "tip": None,
    },
]

# --- 国内 AI 收录实操清单 ---
CHECKLIST = [
    {"level": "high", "platform": {"zh": "百度", "en": "Baidu"},
     "action": {"zh": "注册站长平台，提交 sitemap", "en": "Register webmaster platform, submit sitemap"},
     "effect": {"zh": "文心一言可引用", "en": "Citable by Ernie Bot"}},
    {"level": "high", "platform": {"zh": "微信公众号", "en": "WeChat Official Account"},
     "action": {"zh": "发布内容，建立微信生态存在", "en": "Publish content, build WeChat presence"},
     "effect": {"zh": "混元优先引用", "en": "Preferred by Hunyuan"}},
    {"level": "high", "platform": {"zh": "头条号", "en": "Toutiao Account"},
     "action": {"zh": "同步发布内容", "en": "Sync publish content"},
     "effect": {"zh": "豆包优先引用", "en": "Preferred by Doubao"}},
    {"level": "mid", "platform": {"zh": "神马站长", "en": "Shenma Webmaster"},
     "action": {"zh": "提交 sitemap", "en": "Submit sitemap"},
     "effect": {"zh": "千问可引用", "en": "Citable by Qwen"}},
    {"level": "mid", "platform": {"zh": "搜狗站长", "en": "Sogou Webmaster"},
     "action": {"zh": "提交 sitemap", "en": "Submit sitemap"},
     "effect": {"zh": "混元补充索引", "en": "Extra index for Hunyuan"}},
    {"level": "low", "platform": {"zh": "夸克站长", "en": "Quark Webmaster"},
     "action": {"zh": "提交 sitemap", "en": "Submit sitemap"},
     "effect": {"zh": "千问补充索引", "en": "Extra index for Qwen"}},
]

CORE_LOGIC = {
    "zh": "国内 AI 没有独立的「AI 内容提交平台」，它们都依赖传统搜索引擎的索引，"
          "但各有内容生态偏好：豆包偏好头条系内容、混元偏好微信/搜狗系内容、"
          "千问偏好神马/夸克系内容、文心偏好百度搜索内容。"
          "建议：百度站长 + 微信公众号 + 头条号三管齐下。",
    "en": "Domestic AI models have no standalone content submission platform; they all rely on "
          "traditional search engine indexes, each with its own ecosystem preference: Doubao "
          "prefers Toutiao content, Hunyuan prefers WeChat/Sogou content, Qwen prefers "
          "Shenma/Quark content and Ernie prefers Baidu content. "
          "Recommendation: Baidu Webmaster + WeChat Official Account + Toutiao, all three.",
}
