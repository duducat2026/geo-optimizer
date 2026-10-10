#!/usr/bin/env python3
"""
faq_generator.py — 中英文 FAQ 生成
调用 LLM（百炼兼容 OpenAI API）基于页面内容生成问答对
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from geo_optimizer.config import load_config
from geo_optimizer.crawler import CrawledPage

logger = logging.getLogger(__name__)


@dataclass
class FAQ:
    """单个问答对"""
    question: str
    answer: str
    language: str       # zh-CN / en-US
    keywords: list      # 关联关键词
    engine_tags: list   # 针对哪些引擎优化


class FAQGenerator:
    """基于 LLM 的 FAQ 生成器"""

    # 中文 Prompt 模板
    ZH_PROMPT = """你是一位 SEO/GEO 专家，请基于以下网页内容生成 {count} 组中文问答对（FAQ）。

要求：
1. 问题要口语化、自然，模拟真实用户搜索时的提问方式
2. 答案要准确、简洁、结构化，适合被 AI 搜索引擎直接引用
3. 包含生活场景类问题（如"怎么用"、"多少钱"、"哪家好"）
4. 每个答案控制在 200 字以内
5. 标注关联关键词和目标引擎

网页标题：{title}
网页内容：
{text}

请严格按以下 JSON 格式返回（不要添加其他文字）：
[
  {{
    "question": "用户会怎么问这个问题？",
    "answer": "简洁准确的回答",
    "keywords": ["关键词1", "关键词2"],
    "engine_tags": ["豆包", "通义千问", "混元"]
  }}
]
"""

    # 英文 Prompt 模板
    EN_PROMPT = """You are an SEO/GEO expert. Based on the following webpage content, generate {count} FAQ pairs in English.

Requirements:
1. Questions should be natural, conversational, matching real user search behavior
2. Answers should be accurate, concise, structured — ideal for AI search engine direct citation
3. Include long-tail questions (how-to, comparison, best practices)
4. Keep each answer under 200 words
5. Include related keywords and target engine tags

Page title: {title}
Page content:
{text}

Return ONLY valid JSON in this format:
[
  {{
    "question": "How would a user naturally ask this?",
    "answer": "Clear, concise answer",
    "keywords": ["keyword1", "keyword2"],
    "engine_tags": ["Google AI Overviews", "ChatGPT Search", "Perplexity"]
  }}
]
"""

    def __init__(self, config: dict):
        llm = config.get("llm", {})
        self.client = OpenAI(
            api_key=llm.get("api_key", ""),
            base_url=llm.get("base_url", ""),
            timeout=60,       # 避免端点无响应时挂起导致任务被卡死巡检误杀
            max_retries=1,
        )
        self.model = llm.get("model", "qwen-plus")
        self.temperature = llm.get("temperature", 0.7)
        self.max_tokens = llm.get("max_tokens", 4096)
        self.config = config

    def generate(self, page: CrawledPage) -> list[FAQ]:
        """为单页生成中英双语 FAQ"""
        all_faqs = []

        # 中文 FAQ
        if page.language.startswith("zh") or self._has_chinese(page):
            count = self.config.get("output", {}).get("faq_count_zh", 10)
            faqs = self._generate_zh(page, count)
            all_faqs.extend(faqs)

        # 英文 FAQ
        if page.language.startswith("en") or self._has_english(page):
            count = self.config.get("output", {}).get("faq_count_en", 10)
            faqs = self._generate_en(page, count)
            all_faqs.extend(faqs)

        # 如果检测到的是中文，也生成英文版本（双语覆盖）
        if page.language.startswith("zh"):
            count_en = self.config.get("output", {}).get("faq_count_en", 10)
            faqs_en = self._generate_en(page, count_en)
            all_faqs.extend(faqs_en)

        # 如果检测到的是英文，也生成中文版本
        if page.language.startswith("en"):
            count_zh = self.config.get("output", {}).get("faq_count_zh", 10)
            faqs_zh = self._generate_zh(page, count_zh)
            all_faqs.extend(faqs_zh)

        logger.info(f"✅ Generated {len(all_faqs)} FAQs for {page.url}")
        return all_faqs

    def _generate_zh(self, page: CrawledPage, count: int) -> list[FAQ]:
        """生成中文 FAQ"""
        prompt = self.ZH_PROMPT.format(
            count=count,
            title=page.title,
            text=page.text[:4000],  # 截断到4000字
        )
        raw = self._call_llm(prompt)
        return self._parse_faqs(raw, "zh-CN")

    def _generate_en(self, page: CrawledPage, count: int) -> list[FAQ]:
        """生成英文 FAQ"""
        prompt = self.EN_PROMPT.format(
            count=count,
            title=page.title,
            text=page.text[:8000],  # 英文截断到8000词
        )
        raw = self._call_llm(prompt)
        return self._parse_faqs(raw, "en-US")

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a GEO optimization expert."},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return "[]"

    @staticmethod
    def _parse_faqs(raw: str, language: str) -> list[FAQ]:
        """解析 LLM 返回的 JSON"""
        # 清理 markdown 代码块
        raw = raw.strip()
        if raw.startswith("```"):
            # 去掉 ```json ... ```
            lines = raw.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            raw = "\n".join(lines)

        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                return []
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse FAQ JSON: {raw[:200]}")
            return []

        faqs = []
        for item in data:
            if not isinstance(item, dict):
                continue
            faqs.append(FAQ(
                question=item.get("question", ""),
                answer=item.get("answer", ""),
                language=language,
                keywords=item.get("keywords", []),
                engine_tags=item.get("engine_tags", []),
            ))
        return faqs

    @staticmethod
    def _has_chinese(page: CrawledPage) -> bool:
        sample = page.text[:1000]
        chinese_ratio = sum(1 for c in sample if '\u4e00' <= c <= '\u9fff') / max(len(sample), 1)
        return chinese_ratio > 0.1

    @staticmethod
    def _has_english(page: CrawledPage) -> bool:
        sample = page.text[:1000]
        english_ratio = sum(1 for c in sample if c.isascii() and c.isalpha()) / max(len(sample), 1)
        return english_ratio > 0.3


def format_faqs_to_markdown(faqs: list[FAQ]) -> str:
    """格式化 FAQ 为 Markdown"""
    lines = ["# FAQ (Generated by GEO Optimizer)\n"]

    zh_faqs = [f for f in faqs if f.language == "zh-CN"]
    en_faqs = [f for f in faqs if f.language == "en-US"]

    if zh_faqs:
        lines.append("## 中文 FAQ\n")
        for i, f in enumerate(zh_faqs, 1):
            lines.append(f"### Q{i}. {f.question}\n")
            lines.append(f"{f.answer}\n")
            if f.keywords:
                lines.append(f"*关键词: {', '.join(f.keywords)}*\n")
            lines.append("")

    if en_faqs:
        lines.append("## English FAQ\n")
        for i, f in enumerate(en_faqs, 1):
            lines.append(f"### Q{i}. {f.question}\n")
            lines.append(f"{f.answer}\n")
            if f.keywords:
                lines.append(f"*Keywords: {', '.join(f.keywords)}*\n")
            lines.append("")

    return "\n".join(lines)


# --- 快捷测试 ---
def main():
    config = load_config()
    from geo_optimizer.crawler import CrawledPage
    page = CrawledPage(
        url="https://example.com",
        title="示例产品页面",
        html="",
        text="这是一款智能空气净化器，采用HEPA滤网技术，适用于30-50平米空间。噪音低至25分贝，支持APP远程控制。价格为2999元。",
        language="zh-CN",
        meta_desc="智能空气净化器",
        meta_keywords="空气净化器, 智能, HEPA",
        headings=[(1, "智能空气净化器")],
        links=[],
        word_count=50,
    )
    generator = FAQGenerator(config)
    faqs = generator.generate(page)
    print(format_faqs_to_markdown(faqs))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
