# -*- coding: utf-8 -*-
"""改进方案目录：code/优先级/双语标题/目标/操作步骤/适配模型（兖底模板用）。"""

ITEMS = [
    # --- 高优先级 ---
    {
        "code": "sitemap_optimize",
        "priority": "high",
        "title": {"zh": "创建并提交 Sitemap（全引擎索引基础）",
                  "en": "Create & Submit Sitemap (indexing foundation for all engines)"},
        "goal": {"zh": "让所有 AI 引擎快速发现并索引站点内容，是 GEO 收录的前提",
                 "en": "Enable all AI engines to discover and index site content; prerequisite for GEO"},
        "engines": ["豆包", "通义千问", "混元", "智谱清言", "DeepSeek",
                    "Google AI Overviews", "ChatGPT Search", "Perplexity", "Claude", "Copilot", "Gemini"],
        "steps": [
            {"zh": "生成包含所有重要页面的 sitemap.xml（含 lastmod 日期）", "en": "Generate sitemap.xml covering all important pages (with lastmod dates)"},
            {"zh": "在 robots.txt 中声明 Sitemap: https://域名/sitemap.xml", "en": "Declare Sitemap: https://domain/sitemap.xml in robots.txt"},
            {"zh": "分别提交到百度站长、Bing 站长、Google Search Console", "en": "Submit to Baidu Webmaster, Bing Webmaster, and Google Search Console"},
            {"zh": "确保 AI 爬虫（GPTBot/ClaudeBot/PerplexityBot）未被 robots.txt 禁止", "en": "Ensure AI crawlers (GPTBot/ClaudeBot/PerplexityBot) are not blocked in robots.txt"},
            {"zh": "设置自动更新（新增/修改页面后重新生成）", "en": "Set up auto-regeneration when pages are added or modified"},
        ],
    },
    {
        "code": "baidu_webmaster",
        "priority": "high",
        "title": {"zh": "注册百度站长平台（DNS 验证，不改代码）",
                  "en": "Register Baidu Webmaster (DNS verification, no code change)"},
        "goal": {"zh": "让站点进入百度索引，成为文心一言等国内 AI 的可引用来源",
                 "en": "Get indexed by Baidu so Ernie Bot and other domestic AI can cite you"},
        "engines": ["豆包", "通义千问", "智谱清言", "DeepSeek"],
        "steps": [
            {"zh": "访问 ziyuan.baidu.com，用百度账号登录并添加站点", "en": "Visit ziyuan.baidu.com, sign in and add your site"},
            {"zh": "选择 DNS（CNAME）验证方式，在域名服务商处添加验证记录", "en": "Choose DNS (CNAME) verification and add the record at your DNS provider"},
            {"zh": "提交 sitemap.xml，并开通普通收录/天级收录接口", "en": "Submit sitemap.xml and enable normal/daily inclusion API"},
            {"zh": "在「抓取诊断」中确认 Baiduspider 可正常抓取", "en": "Confirm Baiduspider can fetch pages via Crawl Diagnosis"},
        ],
    },
    {
        "code": "bing_webmaster",
        "priority": "high",
        "title": {"zh": "注册 Bing 站长（DNS 验证）",
                  "en": "Register Bing Webmaster Tools (DNS verification)"},
        "goal": {"zh": "一次提交同时覆盖 Bing 搜索与 Copilot AI",
                 "en": "One submission covers both Bing Search and Copilot AI"},
        "engines": ["Copilot", "ChatGPT Search", "Perplexity"],
        "steps": [
            {"zh": "访问 bing.com/webmasters，用 Microsoft 账号登录", "en": "Visit bing.com/webmasters and sign in with a Microsoft account"},
            {"zh": "添加站点，选择 DNS CNAME 验证", "en": "Add your site and choose DNS CNAME verification"},
            {"zh": "提交 sitemap.xml，开启 IndexNow 即时推送", "en": "Submit sitemap.xml and enable IndexNow instant push"},
            {"zh": "在「URL 检查」确认页面可被 Bingbot 抓取", "en": "Verify pages are crawlable by Bingbot via URL Inspection"},
        ],
    },
    {
        "code": "wechat_mp",
        "priority": "high",
        "title": {"zh": "微信公众号发布 3-5 篇内容",
                  "en": "Publish 3-5 articles on WeChat Official Account"},
        "goal": {"zh": "建立微信生态存在，腾讯混元优先引用公众号文章",
                 "en": "Build WeChat presence; Tencent Hunyuan prefers Official Account articles"},
        "engines": ["混元"],
        "steps": [
            {"zh": "在 mp.weixin.qq.com 注册公众号（订阅号即可）", "en": "Register an Official Account at mp.weixin.qq.com (subscription type is fine)"},
            {"zh": "围绕核心业务撰写 3-5 篇原创文章，标题包含目标关键词", "en": "Write 3-5 original articles on your core business with target keywords in titles"},
            {"zh": "文章内注明品牌名与官网地址，保持署名与发布日期", "en": "Mention brand name and website URL, keep byline and publish date"},
            {"zh": "每周至少更新 1 篇，保持活跃度", "en": "Publish at least one article per week to stay active"},
        ],
    },
    {
        "code": "faq_block",
        "priority": "high",
        "title": {"zh": "站内 FAQ 区块建设（含 FAQPage 结构化数据）",
                  "en": "Build on-site FAQ section (with FAQPage structured data)"},
        "goal": {"zh": "FAQ 是 AI 引擎最易引用的内容形态，直接提升被引用概率",
                 "en": "FAQ is the most citable content format for AI engines"},
        "engines": ["豆包", "通义千问", "混元", "智谱清言", "DeepSeek",
                    "Google AI Overviews", "ChatGPT Search", "Perplexity", "Claude", "Copilot", "Gemini"],
        "steps": [
            {"zh": "提炼用户高频问题 5-8 个（结合搜索词与客服记录）", "en": "Collect 5-8 frequent user questions (search terms, support logs)"},
            {"zh": "为每个问题撰写 50-150 字直接回答（先结论后展开）", "en": "Write 50-150 word direct answers (conclusion first)"},
            {"zh": "将 FAQ 区块嵌入首页或产品页，并注入 FAQPage JSON-LD", "en": "Embed the FAQ section on homepage/product pages with FAQPage JSON-LD"},
            {"zh": "在站长平台提交页面重新抓取", "en": "Request re-crawl in webmaster tools"},
        ],
    },
    # --- 中优先级 ---
    {
        "code": "authority_citation",
        "priority": "mid",
        "title": {"zh": "海外权威引用建设（Wikipedia/新闻稿/行业目录）",
                  "en": "Build overseas authority citations (Wikipedia/PR/directories)"},
        "goal": {"zh": "国外 AI 模型高度依赖权威第三方引用源，缺失则几乎不会引用你的品牌",
                 "en": "Foreign AI models rely heavily on authoritative third-party sources"},
        "engines": ["Google AI Overviews", "ChatGPT Search", "Perplexity", "Claude", "Copilot", "Gemini"],
        "steps": [
            {"zh": "创建/完善 Wikipedia 与 Wikidata 品牌词条（客观中立、附引用）", "en": "Create/improve Wikipedia & Wikidata entries (neutral, cited)"},
            {"zh": "入驻 Crunchbase、G2、Product Hunt 等行业目录并完善资料", "en": "List on Crunchbase, G2, Product Hunt and complete profiles"},
            {"zh": "通过 PR Newswire/Business Wire 发布英文新闻稿", "en": "Publish English press releases via PR Newswire/Business Wire"},
            {"zh": "通过 Featured(HARO)/Qwoted 回应记者，获得媒体引用", "en": "Respond to journalists via Featured (HARO)/Qwoted for media citations"},
            {"zh": "争取 .edu/.org/行业协会外链，提升 E-E-A-T 权威信号", "en": "Earn .edu/.org/association backlinks to boost E-E-A-T signals"},
        ],
    },
    {
        "code": "en_qa_community",
        "priority": "mid",
        "title": {"zh": "英文问答与内容社区布局（Quora/Reddit/Medium）",
                  "en": "Seed English Q&A and content communities (Quora/Reddit/Medium)"},
        "goal": {"zh": "Quora/Reddit/Medium 是 ChatGPT、Perplexity 等的高频引用源",
                 "en": "Quora/Reddit/Medium are frequently cited by ChatGPT and Perplexity"},
        "engines": ["ChatGPT Search", "Perplexity", "Claude", "Copilot", "Gemini"],
        "steps": [
            {"zh": "在 Quora 回答 3-5 个与业务相关的英文问题", "en": "Answer 3-5 business-related questions on Quora"},
            {"zh": "参与相关 subreddit 讨论，提供专业价值后自然提及品牌", "en": "Join relevant subreddits, add value first, mention brand naturally"},
            {"zh": "在 Medium 发布 1-2 篇英文深度文章并回链官网", "en": "Publish 1-2 in-depth English articles on Medium linking back"},
            {"zh": "在 LinkedIn 发布公司页文章，积累专业背书", "en": "Post company-page articles on LinkedIn for professional endorsement"},
        ],
    },
    {
        "code": "toutiao_sync",
        "priority": "mid",
        "title": {"zh": "百家号/头条号注册并同步内容",
                  "en": "Register Baijiahao/Toutiao and sync content"},
        "goal": {"zh": "进入头条内容生态，豆包优先引用头条系内容",
                 "en": "Enter the Toutiao ecosystem; Doubao prefers Toutiao content"},
        "engines": ["豆包"],
        "steps": [
            {"zh": "注册百家号 (baijiahao.baidu.com) 与头条号 (mp.toutiao.com)", "en": "Register Baijiahao (baijiahao.baidu.com) and Toutiao (mp.toutiao.com)"},
            {"zh": "完成企业/个人认证，提高账号权重", "en": "Complete business/personal verification to raise account weight"},
            {"zh": "将官网核心内容改写后同步发布（避免纯复制）", "en": "Rewrite and sync core website content (avoid pure copy)"},
            {"zh": "文末标注品牌与官网，引导 AI 关联站点", "en": "Credit brand and website at the end so AI links back to your site"},
        ],
    },
    {
        "code": "baidu_baike",
        "priority": "mid",
        "title": {"zh": "百度百科创建词条", "en": "Create a Baidu Baike entry"},
        "goal": {"zh": "建立权威背书，AI 回答品牌类问题时优先引用百科",
                 "en": "Build authority; AI prefers Baike when answering brand questions"},
        "engines": ["豆包", "通义千问", "混元", "智谱清言", "DeepSeek"],
        "steps": [
            {"zh": "准备工商信息/官网/新闻报道等权威参考资料", "en": "Prepare business registration, website and news coverage as references"},
            {"zh": "在 baike.baidu.com 创建品牌词条，客观描述业务", "en": "Create a brand entry at baike.baidu.com with objective descriptions"},
            {"zh": "每个关键信息附参考资料链接，提高通过率", "en": "Attach a reference link to each key claim to pass review"},
            {"zh": "词条通过后定期维护更新", "en": "Maintain and update the entry regularly after approval"},
        ],
    },
    {
        "code": "zhihu_qa",
        "priority": "mid",
        "title": {"zh": "知乎回答 3-5 个相关问题", "en": "Answer 3-5 related questions on Zhihu"},
        "goal": {"zh": "知乎内容被多家 AI 引用，是高质量引用源",
                 "en": "Zhihu content is cited by many AI models as a high-quality source"},
        "engines": ["豆包", "通义千问", "混元", "智谱清言", "DeepSeek", "Kimi"],
        "steps": [
            {"zh": "搜索与业务相关的高关注度问题", "en": "Search for high-traffic questions related to your business"},
            {"zh": "以专业身份撰写结构化回答（分点、数据、案例）", "en": "Write structured expert answers (bullets, data, cases)"},
            {"zh": "个人主页与回答中自然带出品牌与官网", "en": "Naturally mention brand and website in profile and answers"},
            {"zh": "保持每月 1-2 条更新，积累赞同数", "en": "Post 1-2 answers monthly and accumulate upvotes"},
        ],
    },
    # --- 低优先级 ---
    {
        "code": "map_poi",
        "priority": "low",
        "title": {"zh": "高德/腾讯地图标注商户", "en": "Register POI on Amap/Tencent Maps"},
        "goal": {"zh": "补全本地实体信息，AI 回答位置类问题时可引用",
                 "en": "Complete local business info so AI can cite for location queries"},
        "engines": ["豆包", "混元", "通义千问"],
        "steps": [
            {"zh": "在高德地图商户中心 (amap.com) 提交商户标注", "en": "Submit business listing at Amap merchant center (amap.com)"},
            {"zh": "在腾讯地图商户标注平台提交同样信息", "en": "Submit the same info to Tencent Maps business platform"},
            {"zh": "保持名称/地址/电话与官网一致（NAP 一致性）", "en": "Keep name/address/phone consistent with website (NAP consistency)"},
        ],
    },
    {
        "code": "geo_subpage",
        "priority": "low",
        "title": {"zh": "建设 GEO 专页（如 geo 子域名）", "en": "Build a dedicated GEO page (e.g. geo subdomain)"},
        "goal": {"zh": "集中呈现 FAQ/结构化数据/权威信息，方便 AI 抓取引用",
                 "en": "Concentrate FAQ/structured data/authority signals for AI crawling"},
        "engines": ["Google AI Overviews", "ChatGPT Search", "Perplexity", "Claude", "Copilot", "Gemini"],
        "steps": [
            {"zh": "创建专页聚合品牌介绍、FAQ、数据与引用来源", "en": "Create a page aggregating brand intro, FAQ, data and citations"},
            {"zh": "注入 FAQPage/Organization JSON-LD 结构化数据", "en": "Inject FAQPage/Organization JSON-LD structured data"},
            {"zh": "确保 robots.txt 对 GPTBot/ClaudeBot 等 AI 爬虫开放", "en": "Ensure robots.txt allows GPTBot/ClaudeBot and other AI crawlers"},
            {"zh": "在站内首页与 sitemap 中加入该专页链接", "en": "Link the page from homepage and sitemap"},
        ],
    },
    {
        "code": "baidu_zhidao",
        "priority": "low",
        "title": {"zh": "百度知道布局", "en": "Seed Q&A on Baidu Zhidao"},
        "goal": {"zh": "占位品牌相关问答，为文心一言提供可引用素材",
                 "en": "Occupy brand Q&A so Ernie Bot has citable material"},
        "engines": ["豆包", "通义千问", "智谱清言"],
        "steps": [
            {"zh": "整理用户最常问的 5-10 个问题", "en": "Collect the 5-10 most frequent user questions"},
            {"zh": "在 zhidao.baidu.com 搜索并认领/回答相关问题", "en": "Search and answer related questions at zhidao.baidu.com"},
            {"zh": "回答保持客观中立，避免广告用语", "en": "Keep answers objective and avoid ad language"},
        ],
    },
]


def get_item(code: str) -> dict | None:
    for item in ITEMS:
        if item["code"] == code:
            return item
    return None


def engines_for(code: str) -> list:
    """返回条目适配的 AI 引擎列表。"""
    item = get_item(code)
    return item.get("engines", []) if item else []


def engines_map() -> dict:
    """返回 {code: [engines]} 映射，供模板展示。"""
    return {item["code"]: item.get("engines", []) for item in ITEMS}
