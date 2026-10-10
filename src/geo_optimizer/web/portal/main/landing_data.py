# -*- coding: utf-8 -*-
"""平台首页（Landing）内置双语内容：覆盖引擎、平台 FAQ 等。

结构化数据，值为 {"zh": ..., "en": ...}，模板按 current_locale 取值。
"""

# --- 覆盖的 AI 引擎（跑马灯展示） ---
ENGINES = [
    "ChatGPT", "Claude", "Perplexity", "Gemini", "AI Overviews", "Copilot",
    "Kimi", "豆包", "千问", "文心一言", "腾讯混元", "DeepSeek",
]

# --- 平台 FAQ ---
FAQ_ITEMS = [
    {
        "q": {"zh": "什么是 GEO（生成式引擎优化）？",
              "en": "What is GEO (Generative Engine Optimization)?"},
        "a": {"zh": "GEO 是面向 AI 搜索引擎（如 ChatGPT、Claude、Perplexity、Kimi、豆包等）的可见性优化。"
                  "与传统 SEO 关注网页排名不同，GEO 关注你的内容是否会被 AI 引擎抓取、理解并在回答中引用。"
                  "本平台通过爬取站点、多引擎评分、技术体检与改进方案，帮助你系统性地提升 AI 引用率。",
              "en": "GEO optimizes your visibility in AI search engines (ChatGPT, Claude, Perplexity, Kimi, Doubao, etc.). "
                    "Unlike traditional SEO which targets rankings, GEO focuses on whether AI engines crawl, understand "
                    "and cite your content. This platform crawls your site, scores it across engines, audits technical "
                    "issues and generates improvement plans to raise your AI citation rate."},
    },
    {
        "q": {"zh": "平台覆盖哪些 AI 引擎？",
              "en": "Which AI engines are covered?"},
        "a": {"zh": "覆盖 ChatGPT、Claude、Perplexity、Gemini、AI Overviews、Copilot 等海外引擎，"
                  "以及 Kimi、豆包、千问、文心一言、腾讯混元等国内主流模型，共 10+ 个引擎的评分与收录机制分析。",
              "en": "Overseas engines including ChatGPT, Claude, Perplexity, Gemini, AI Overviews and Copilot, "
                    "plus domestic models such as Kimi, Doubao, Qwen, Ernie Bot and Hunyuan — 10+ engines "
                    "with scoring and indexing-mechanism analysis."},
    },
    {
        "q": {"zh": "如何开始第一次评估？",
              "en": "How do I run my first evaluation?"},
        "a": {"zh": "登录控制台后，在「新建评估」中填入目标网站 URL，选择「仅评估」或「评估 + 生成方案」，"
                  "点击开始即可。系统会自动爬取页面、逐引擎评分、执行技术体检，并生成可下载的分析报告；"
                  "选择生成方案时还会产出改进条目与多平台内容产出物（ZIP 打包下载）。",
              "en": "Sign in, go to New Evaluation, enter your target URL and choose Evaluation only or "
                    "Evaluation + Plan. The system crawls the page, scores it per engine, runs a technical audit "
                    "and produces a downloadable report; plan mode additionally generates action items and "
                    "multi-platform deliverables (ZIP download)."},
    },
    {
        "q": {"zh": "评估报告包含哪些内容？",
              "en": "What does the evaluation report contain?"},
        "a": {"zh": "包含综合得分与各引擎评分、页面技术体检结果（HTTPS、标题结构、结构化数据、FAQ 区块、"
                  "E-E-A-T 信号等 20+ 检查项）、优势与待改进分析、优先级排序建议，以及改进方案条目和"
                  "结合站点实际内容生成的产出物（sitemap、robots.txt、Schema 标记、多平台文案等）。",
              "en": "Overall and per-engine scores, a technical audit (HTTPS, heading structure, structured data, "
                    "FAQ section, E-E-A-T signals and 20+ more checks), strengths/weaknesses analysis, prioritized "
                    "suggestions, plus action items and deliverables generated from your actual site content "
                    "(sitemap, robots.txt, Schema markup, multi-platform copy, etc.)."},
    },
    {
        "q": {"zh": "如何通过 API 调用平台？",
              "en": "How do I use the Open API?"},
        "a": {"zh": "在「API 密钥」页面生成密钥（geo_ 前缀）后，请求时在 Header 中携带 "
                  "Authorization: Bearer <密钥> 即可调用 /api/v1 下的接口：提交任务、查询状态、获取结果、"
                  "下载报告与用量统计。控制台「API 文档」页提供完整接口说明与示例。",
              "en": "Generate a key (geo_ prefix) on the API Keys page, then send Authorization: Bearer <key> "
                    "with requests to /api/v1 endpoints: submit tasks, query status, fetch results, download "
                    "reports and check usage. Full reference with examples is on the API Docs page in the console."},
    },
    {
        "q": {"zh": "什么是 GEO-Skill？",
              "en": "What is GEO-Skill?"},
        "a": {"zh": "GEO-Skill 是遵循 Agent Skill 规范的能力包，让 AI 编程助手可以直接调用本平台提交评估任务、"
                  "轮询进度并取回结果。文件公开托管在 /geo-skill 路径下，无需登录即可获取。",
              "en": "GEO-Skill is an Agent-Skill-spec package that lets AI coding assistants submit evaluation tasks, "
                    "poll progress and retrieve results from this platform directly. Files are publicly hosted "
                    "under /geo-skill — no login required."},
    },
    {
        "q": {"zh": "算力（LLM）如何配置？",
              "en": "How is the LLM computing power configured?"},
        "a": {"zh": "支持三种方案：百炼按量付费（sk- 前缀）、Token Plan 团队版（sk-sp- 前缀）与自定义 "
                  "OpenAI 兼容端点。如果平台未提供统一算力，您需要在「我的算力」自行配置并激活；"
                  "若平台已开通算力权限，系统会自动使用，无需额外配置。详见控制台「算力方案」指引。",
              "en": "Three options: Bailian pay-as-you-go (sk- prefix), Token Plan Team (sk-sp- prefix) and any custom "
                    "OpenAI-compatible endpoint. If the platform does not provide unified computing power, configure "
                    "your own under My LLM Config and activate it; if platform access is granted, it is used "
                    "automatically. See the LLM Setup guide in the console."},
    },
    {
        "q": {"zh": "我的数据安全吗？",
              "en": "Is my data secure?"},
        "a": {"zh": "API 密钥以 SHA-256 哈希存储，原文仅在生成时展示一次；平台记录完整操作审计日志；"
                  "评估产物仅本人可见，管理员仅可查看站点级总览。处理日志保留 3 天后自动清理。",
              "en": "API keys are stored as SHA-256 hashes and the plaintext is shown only once at creation. "
                    "Full operation audit logs are kept; evaluation artifacts are private to the owner while admins "
                    "only see site-level overviews. Processing logs are auto-purged after 3 days."},
    },
]
