#!/usr/bin/env python3
"""
geo_faq.py — FAQ 问答对生成模块
从关键词和场景词生成结构化 FAQ，适合 Schema 标记
"""

import json
import logging
from dataclasses import dataclass

from openai import OpenAI

from geo_optimizer.config import load_config
from geo_optimizer.crawler import CrawledPage

logger = logging.getLogger(__name__)


@dataclass
class FAQItem:
    question: str
    answer: str
    language: str  # zh-CN / en-US
    keywords: list[str] = None


class GEOFAQGenerator:
    """GEO FAQ 生成器"""

    def __init__(self, config: dict):
        self.config = config
        llm = config.get("llm", {})
        self.client = OpenAI(
            api_key=llm.get("api_key", ""),
            base_url=llm.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        )
        self.model = llm.get("model", "qwen-plus")
        self.temperature = llm.get("temperature", 0.7)
        self.max_tokens = llm.get("max_tokens", 4096)
        # 明确标识算力来源
        source_label = llm.get("_source_label", "CLI/配置文件")
        logger.info(
            "[FAQ生成器] 调用接口: %s | model=%s, base_url=%s",
            source_label, self.model, llm.get("base_url", "default"),
        )

    def generate(
        self,
        page: CrawledPage,
        language: str = "zh-CN",
        count: int | None = None,
    ) -> list[FAQItem]:
        """
        生成 FAQ 问答对
        :param page: 爬取的页面
        :param language: 语言 (zh-CN / en-US)
        :param count: 生成数量，默认从配置读取
        :return: FAQItem 列表
        """
        if count is None:
            if language.startswith("zh"):
                count = self.config.get("output", {}).get("faq_count_zh", 10)
            else:
                count = self.config.get("output", {}).get("faq_count_en", 10)

        is_zh = language.startswith("zh")
        lang_key = "zh" if is_zh else "en"

        keywords = self.config.get("keywords", {}).get(lang_key, {})
        primary_kw = keywords.get("primary", [])
        longtail_kw = keywords.get("longtail", [])
        scenarios = keywords.get("scenarios", [])

        system_prompt = self._build_system_prompt(is_zh)
        user_prompt = self._build_user_prompt(
            page=page,
            count=count,
            primary_kw=primary_kw,
            longtail_kw=longtail_kw,
            scenarios=scenarios,
            is_zh=is_zh,
        )

        result = self._call_llm(system_prompt, user_prompt)

        if not result:
            logger.warning("FAQ generation returned empty result")
            return []

        return self._parse_result(result, language)

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM API call failed for FAQ: {e}")
            return ""

    @staticmethod
    def _build_system_prompt(is_zh: bool) -> str:
        if is_zh:
            return (
                "你是一个 SEO/GEO 专家，擅长生成高质量的 FAQ 问答对。"
                "问答应该自然、有信息量、适合在 AI 搜索引擎中获得好的展示。"
                "请只返回 JSON 数组，不要其他文字。"
            )
        else:
            return (
                "You are an SEO/GEO expert skilled at creating high-quality FAQ pairs. "
                "Questions and answers should be natural, informative, and suitable for "
                "AI search engines. Return only a JSON array, no other text."
            )

    @staticmethod
    def _build_user_prompt(
        page: CrawledPage,
        count: int,
        primary_kw: list[str],
        longtail_kw: list[str],
        scenarios: list[str],
        is_zh: bool,
    ) -> str:
        lang = "中文" if is_zh else "English"
        prompt = f"""请生成 {count} 个{lang} FAQ 问答对，基于以下内容：

## 页面信息
- 标题: {page.title}
- 描述: {page.meta_desc}
- 内容摘要: {page.text[:800]}

## 目标关键词
- 核心词: {', '.join(primary_kw)}
- 长尾词: {', '.join(longtail_kw)}
- 场景词: {', '.join(scenarios)}

## 要求
1. 问题应该是用户真实会搜索的查询形式（口语化、自然）
2. 答案应该详细但简洁（100-300字），包含具体信息
3. 覆盖核心词、长尾词和场景词
4. 包含常见的疑问词（如何、什么、为什么、哪里、什么时候/ how, what, why, where, when）

## 输出格式
返回 JSON 数组：
[
  {{"question": "...", "answer": "...", "keywords": ["..."]}},
  ...
]
"""
        return prompt

    @staticmethod
    def _parse_result(result: str, language: str) -> list[FAQItem]:
        try:
            json_str = result
            if "```json" in result:
                json_str = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                json_str = result.split("```")[1].split("```")[0].strip()

            items = json.loads(json_str)
            return [
                FAQItem(
                    question=item.get("question", ""),
                    answer=item.get("answer", ""),
                    language=language,
                    keywords=item.get("keywords", []),
                )
                for item in items
            ]
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"Failed to parse FAQ result: {e}")
            return []

    def generate_both_languages(
        self,
        page: CrawledPage,
        zh_count: int | None = None,
        en_count: int | None = None,
    ) -> dict[str, list[FAQItem]]:
        """同时生成中英文 FAQ"""
        zh_faqs = self.generate(page, language="zh-CN", count=zh_count)
        en_faqs = self.generate(page, language="en-US", count=en_count)
        return {"zh-CN": zh_faqs, "en-US": en_faqs}


# --- 格式化输出 ---
def format_faqs(faqs: list[FAQItem], language: str = "zh-CN") -> str:
    """格式化 FAQ 为可读文本"""
    is_zh = language.startswith("zh")
    lines = [
        f"# FAQ {'问答' if is_zh else 'Questions & Answers'}",
        f"",
    ]
    for i, faq in enumerate(faqs, 1):
        lines.append(f"## Q{i}: {faq.question}")
        lines.append(f"")
        lines.append(faq.answer)
        lines.append(f"")

    return "\n".join(lines)


def format_faqs_schema_json_ld(faqs: list[FAQItem]) -> str:
    """将 FAQ 转为 FAQPage Schema JSON-LD"""
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": faq.question,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": faq.answer,
                },
            }
            for faq in faqs
        ],
    }
    return json.dumps(schema, ensure_ascii=False, indent=2)


# --- 快捷测试 ---
def main():
    config = load_config()
    from geo_optimizer.crawler import CrawledPage
    page = CrawledPage(
        url="https://example.com/product",
        title="智能清洁机器人",
        html="",
        text="我们的智能清洁机器人可以自动清扫、拖地，支持 App 控制和语音指令。适合各种户型，续航时间 120 分钟。",
        language="zh-CN",
        meta_desc="智能清洁机器人，自动清扫拖地一体",
        meta_keywords="清洁机器人,扫地机器人",
        headings=[(1, "智能清洁机器人")],
        links=[],
        word_count=30,
    )

    generator = GEOFAQGenerator(config)
    faqs = generator.generate(page, language="zh-CN", count=5)

    for faq in faqs:
        print(f"Q: {faq.question}")
        print(f"A: {faq.answer}")
        print()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
