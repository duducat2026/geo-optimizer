#!/usr/bin/env python3
"""
geo_content_generator.py — LLM 驱动的内容优化生成器
基于分析评分结果，调用百炼 API 生成针对性优化内容
"""

import json
import logging
from dataclasses import dataclass

from openai import OpenAI

from geo_optimizer.analyzer import AnalysisReport, EngineScore
from geo_optimizer.config import load_config
from geo_optimizer.crawler import CrawledPage

logger = logging.getLogger(__name__)


@dataclass
class OptimizedContent:
    """优化后的内容"""
    original_url: str
    target_engine: str
    optimized_text: str          # 优化后的正文
    optimized_title: str         # 优化后的标题
    optimized_meta_desc: str     # 优化后的 meta description
    faq_items: list[dict]        # [{question, answer}, ...]
    schema_json_ld: str          # JSON-LD 结构化数据
    improvements: list[str]      # 具体改进了哪些维度


class GEOContentGenerator:
    """GEO 内容生成器"""

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
            "[内容生成器] 调用接口: %s | model=%s, base_url=%s",
            source_label, self.model, llm.get("base_url", "default"),
        )

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM API"""
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
            logger.error(f"LLM API call failed: {e}")
            return ""

    def generate_for_engine(
        self,
        page: CrawledPage,
        engine_score: EngineScore,
        report: AnalysisReport,
    ) -> OptimizedContent:
        """针对特定引擎生成优化内容"""
        engine = engine_score.engine
        weak_dims = [dim for dim, score in engine_score.breakdown.items() if score < 60]
        strong_dims = [dim for dim, score in engine_score.breakdown.items() if score >= 70]

        # 获取关键词
        is_zh = page.language.startswith("zh")
        lang_key = "zh" if is_zh else "en"
        keywords = self.config.get("keywords", {}).get(lang_key, {})
        primary_kw = keywords.get("primary", [])
        longtail_kw = keywords.get("longtail", [])
        scenarios = keywords.get("scenarios", [])

        # 构建系统提示
        system_prompt = self._build_system_prompt(engine, is_zh)

        # 构建用户提示
        user_prompt = self._build_user_prompt(
            page=page,
            engine=engine,
            weak_dims=weak_dims,
            strong_dims=strong_dims,
            primary_kw=primary_kw,
            longtail_kw=longtail_kw,
            scenarios=scenarios,
        )

        result = self._call_llm(system_prompt, user_prompt)

        if not result:
            return OptimizedContent(
                original_url=page.url,
                target_engine=engine,
                optimized_text="",
                optimized_title="",
                optimized_meta_desc="",
                faq_items=[],
                schema_json_ld="",
                improvements=[],
            )

        # 解析结果
        return self._parse_result(page.url, engine, result, weak_dims)

    def _build_system_prompt(self, engine: str, is_zh: bool) -> str:
        """构建系统提示词"""
        if is_zh:
            return (
                "你是一个专业的 SEO/GEO 内容优化专家。你的任务是根据目标引擎的偏好，"
                "优化网页内容，使其在该引擎的 AI 生成结果中获得更好的排名和展示。\n"
                "请保持内容自然、专业、有价值。"
            )
        else:
            return (
                "You are a professional SEO/GEO content optimization expert. "
                "Your task is to optimize web content for better ranking and "
                "visibility in AI-generated search results.\n"
                "Keep the content natural, professional, and valuable."
            )

    def _build_user_prompt(
        self,
        page: CrawledPage,
        engine: str,
        weak_dims: list[str],
        strong_dims: list[str],
        primary_kw: list[str],
        longtail_kw: list[str],
        scenarios: list[str],
    ) -> str:
        """构建用户提示词"""
        prompt = f"""# 任务：为「{engine}」优化以下内容

## 原始页面
- URL: {page.url}
- 标题: {page.title}
- 描述: {page.meta_desc}
- 当前内容摘要: {page.text[:1000]}

## 当前评分薄弱维度
{', '.join(weak_dims) if weak_dims else '无明显薄弱项'}

## 当前评分优势维度
{', '.join(strong_dims) if strong_dims else '无明显优势项'}

## 目标关键词
- 核心词: {', '.join(primary_kw)}
- 长尾词: {', '.join(longtail_kw)}
- 场景词: {', '.join(scenarios)}

## 输出要求
请按以下 JSON 格式返回优化结果（只返回 JSON，不要额外文字）：

```json
{{
  "optimized_title": "优化后的标题（60字符以内，包含核心关键词）",
  "optimized_meta_desc": "优化后的meta描述（160字符以内，包含核心关键词和行动号召）",
  "optimized_text": "优化后的正文内容（保持原意但增强{', '.join(weak_dims)}维度）",
  "faq": [
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}}
  ],
  "improvements": ["改进点1", "改进点2", ...]
}}
```
"""
        return prompt

    @staticmethod
    def _parse_result(url: str, engine: str, result: str, weak_dims: list[str]) -> OptimizedContent:
        """解析 LLM 返回的 JSON 结果"""
        try:
            # 尝试提取 JSON（可能被 markdown 代码块包裹）
            json_str = result
            if "```json" in result:
                json_str = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                json_str = result.split("```")[1].split("```")[0].strip()

            data = json.loads(json_str)

            return OptimizedContent(
                original_url=url,
                target_engine=engine,
                optimized_title=data.get("optimized_title", ""),
                optimized_meta_desc=data.get("optimized_meta_desc", ""),
                optimized_text=data.get("optimized_text", ""),
                faq_items=data.get("faq", []),
                schema_json_ld="",  # 由 geo_schema 模块生成
                improvements=data.get("improvements", []),
            )
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logger.error(f"Failed to parse LLM result for {engine}: {e}")
            return OptimizedContent(
                original_url=url,
                target_engine=engine,
                optimized_text=result[:2000],
                optimized_title="",
                optimized_meta_desc="",
                faq_items=[],
                schema_json_ld="",
                improvements=weak_dims,
            )

    def generate_all_engines(
        self,
        page: CrawledPage,
        report: AnalysisReport,
    ) -> list[OptimizedContent]:
        """为所有引擎生成优化内容"""
        results = []
        for score in report.engine_scores:
            logger.info(f"Generating optimized content for: {score.engine} (score: {score.score})")
            optimized = self.generate_for_engine(page, score, report)
            results.append(optimized)
        return results


# --- 快捷测试 ---
def main():
    config = load_config()
    page = CrawledPage(
        url="https://example.com",
        title="示例产品页面",
        html="",
        text="这是一个示例产品页面。我们的产品很好用。",
        language="zh-CN",
        meta_desc="示例产品",
        meta_keywords="示例,产品",
        headings=[(1, "示例产品"), (2, "功能介绍")],
        links=[],
        word_count=20,
    )
    from geo_optimizer.analyzer import GEOAnalyzer
    analyzer = GEOAnalyzer()
    report = analyzer.analyze(page, config)

    generator = GEOContentGenerator(config)
    results = generator.generate_all_engines(page, report)

    for r in results:
        print(f"\n{'='*60}")
        print(f"Engine: {r.target_engine}")
        print(f"Title: {r.optimized_title}")
        print(f"Improvements: {r.improvements}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
