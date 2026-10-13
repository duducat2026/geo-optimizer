#!/usr/bin/env python3
"""
geo_analyzer.py — 双引擎评分：国内5引擎 + 国外6引擎适配度

评分策略：
  - 国内外引擎全覆盖（不做语言门控），仅由 config enabled 控制
  - 每个引擎的 focus 字段映射到对应评分维度，命中维度获得 +30% 权重加成
  - 国内引擎使用 CN_DIMENSIONS 基础维度，国外引擎使用 EN_DIMENSIONS
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from geo_optimizer.config import load_config
from geo_optimizer.models import CrawledPage

logger = logging.getLogger(__name__)


@dataclass
class EngineScore:
    """单个引擎的评分"""
    engine: str
    vendor: str
    score: float            # 0-100
    breakdown: dict         # 子维度分数
    suggestions: list       # 改进建议
    focus: list = field(default_factory=list)   # 引擎关注点（报告双语渲染需要）


@dataclass
class AnalysisReport:
    """完整分析报告"""
    url: str
    language: str
    engine_scores: list[EngineScore]
    overall_score: float
    strengths: list
    weaknesses: list


class GEOAnalyzer:
    """GEO 适配度分析器"""

    # focus 关键词 → 评分维度映射（用于将引擎 focus 字段关联到具体维度）
    FOCUS_DIMENSION_MAP = {
        # 国内维度
        "结构化": "结构化", "口语化": "口语化", "生活场景": "生活场景",
        "权威来源": "权威性", "数据支撑": "权威性",
        "微信生态": "生活场景", "公众号格式": "结构化",
        "学术引用": "权威性", "专业深度": "技术深度",
        "精准回答": "关键词覆盖", "代码块": "技术深度",
        # 国外维度
        "E-E-A-T": "E-E-A-T", "Schema": "结构化",
        "权威引用": "E-E-A-T", "权威背书": "E-E-A-T",
        "自然对话体": "可读性", "长尾问答": "关键词覆盖",
        "来源链接": "引用标注", "引用标注": "引用标注",
        "深度分析": "内容深度", "结构化输出": "结构化",
        "Bing索引": "结构化", "多模态": "内容深度", "Google生态": "E-E-A-T",
    }

    FOCUS_BOOST = 0.3  # 命中 focus 的维度权重加成比例

    # 国内引擎评分维度（基础权重）
    CN_DIMENSIONS = {
        "结构化": 20,        # 内容结构清晰度
        "口语化": 15,        # 自然语言表达
        "权威性": 20,        # 来源、数据、背书
        "关键词覆盖": 15,   # 关键词匹配度
        "生活场景": 15,      # 是否包含使用场景
        "技术深度": 15,      # 专业深度
    }

    # 国外引擎评分维度（基础权重）
    EN_DIMENSIONS = {
        "E-E-A-T": 25,       # 经验/专业/权威/可信
        "结构化": 15,        # Schema/结构化数据
        "引用标注": 15,      # 来源链接
        "关键词覆盖": 15,    # 关键词/长尾词
        "内容深度": 15,      # 内容全面性
        "可读性": 15,        # 清晰易懂
    }

    def analyze(self, page: CrawledPage, config: dict) -> AnalysisReport:
        """分析单页对所有引擎的适配度（国内外全覆盖，不做语言门控）"""
        lang = page.language

        engine_scores = []

        # 国内引擎（全覆盖）
        for engine_cfg in config.get("engines_cn", []):
            if engine_cfg.get("enabled", True):
                score = self._score_cn(page, engine_cfg, config)
                engine_scores.append(score)

        # 国外引擎（全覆盖）
        for engine_cfg in config.get("engines_en", []):
            if engine_cfg.get("enabled", True):
                score = self._score_en(page, engine_cfg, config)
                engine_scores.append(score)

        overall = sum(s.score for s in engine_scores) / max(len(engine_scores), 1)

        strengths, weaknesses = self._extract_insights(engine_scores)

        return AnalysisReport(
            url=page.url,
            language=lang,
            engine_scores=engine_scores,
            overall_score=round(overall, 1),
            strengths=strengths,
            weaknesses=weaknesses,
        )

    def _score_cn(self, page: CrawledPage, engine_cfg: dict, config: dict) -> EngineScore:
        """国内引擎评分"""
        text = page.text.lower()
        breakdown = {}

        # 结构化：是否有标题层级、列表
        has_headings = len(page.headings) > 2
        has_lists = any(tag in text for tag in ["•", "-", "*", "1.", "2."])
        breakdown["结构化"] = 80 if (has_headings and has_lists) else 40

        # 口语化：句子长度、语气词
        sentences = [s.strip() for s in text.replace("\n", " ").split("。") if s.strip()]
        avg_len = sum(len(s) for s in sentences) / max(len(sentences), 1)
        breakdown["口语化"] = 70 if avg_len < 50 else 40

        # 权威性：是否有数据、引用
        has_data = any(c.isdigit() for c in text)
        has_citations = any(w in text for w in ["据", "研究表明", "来源", "引用"])
        breakdown["权威性"] = 75 if (has_data and has_citations) else 35

        # 关键词覆盖
        kw_zh = config.get("keywords", {}).get("zh", {}).get("primary", [])
        matched = sum(1 for kw in kw_zh if kw.lower() in text) if kw_zh else 0
        breakdown["关键词覆盖"] = min(100, matched * 33) if kw_zh else 30

        # 生活场景
        scenario_words = ["怎么", "如何", "什么时候", "哪里", "为什么", "多少钱", "好用"]
        scenario_match = sum(1 for w in scenario_words if w in text)
        breakdown["生活场景"] = min(100, scenario_match * 20)

        # 技术深度
        tech_indicators = page.headings and any(lv <= 3 for lv, _ in page.headings)
        breakdown["技术深度"] = 70 if tech_indicators else 35

        # 加权总分（引擎 focus 命中维度获得 +30% 权重加成）
        weights = self._boosted_weights(self.CN_DIMENSIONS, engine_cfg)
        total = sum(breakdown.get(k, 50) * v for k, v in weights.items())
        max_score = sum(weights.values())
        final_score = round(total / max_score, 1)

        suggestions = self._generate_cn_suggestions(breakdown, engine_cfg)

        return EngineScore(
            engine=engine_cfg["name"],
            vendor=engine_cfg["vendor"],
            score=final_score,
            breakdown=breakdown,
            suggestions=suggestions,
            focus=list(engine_cfg.get("focus", [])),
        )

    def _score_en(self, page: CrawledPage, engine_cfg: dict, config: dict) -> EngineScore:
        """国外引擎评分"""
        text = page.text.lower()
        breakdown = {}

        # E-E-A-T
        has_author = any(w in text for w in ["author", "by", "written by", "editor"])
        has_expertise = any(w in text for w in ["expert", "professional", "certified", "research"])
        has_trust = any(w in text for w in ["https", "privacy", "terms", "policy"])
        eeat_score = sum([has_author, has_expertise, has_trust]) * 33
        breakdown["E-E-A-T"] = eeat_score

        # 结构化
        has_schema = any(w in text for w in ["schema.org", "json-ld", "microdata"])
        has_headings = len(page.headings) > 2
        breakdown["结构化"] = 80 if (has_schema or has_headings) else 30

        # 引用标注
        has_citations = any(w in text for w in ["source:", "reference", "citation", "doi", "via:"])
        has_links = len(page.links) > 5
        breakdown["引用标注"] = 70 if (has_citations or has_links) else 30

        # 关键词覆盖
        kw_en = config.get("keywords", {}).get("en", {}).get("primary", [])
        matched = sum(1 for kw in kw_en if kw.lower() in text) if kw_en else 0
        breakdown["关键词覆盖"] = min(100, matched * 33) if kw_en else 30

        # 内容深度
        word_count_score = min(100, page.word_count / 10)  # 1000+ words = 100
        breakdown["内容深度"] = round(word_count_score)

        # 可读性
        sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
        avg_len = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
        breakdown["可读性"] = 80 if avg_len < 25 else 40

        # 加权总分（引擎 focus 命中维度获得 +30% 权重加成）
        weights = self._boosted_weights(self.EN_DIMENSIONS, engine_cfg)
        total = sum(breakdown.get(k, 50) * v for k, v in weights.items())
        max_score = sum(weights.values())
        final_score = round(total / max_score, 1)

        suggestions = self._generate_en_suggestions(breakdown, engine_cfg)

        return EngineScore(
            engine=engine_cfg["name"],
            vendor=engine_cfg["vendor"],
            score=final_score,
            breakdown=breakdown,
            suggestions=suggestions,
            focus=list(engine_cfg.get("focus", [])),
        )

    def _boosted_weights(self, base_dimensions: dict, engine_cfg: dict) -> dict:
        """根据引擎 focus 字段对基础维度权重进行加成。

        命中 focus 映射的维度权重 × (1 + FOCUS_BOOST)，使不同引擎产生分数差异。
        """
        focus = engine_cfg.get("focus", [])
        boosted_dims = set()
        for kw in focus:
            dim = self.FOCUS_DIMENSION_MAP.get(kw)
            if dim and dim in base_dimensions:
                boosted_dims.add(dim)
        return {
            dim: round(w * (1 + self.FOCUS_BOOST) if dim in boosted_dims else w, 2)
            for dim, w in base_dimensions.items()
        }

    @staticmethod
    def _generate_cn_suggestions(breakdown: dict, engine_cfg: dict) -> list:
        suggestions = []
        focus = engine_cfg.get("focus", [])
        for dim, score in breakdown.items():
            if score < 50:
                suggestions.append(f"提升「{dim}」(当前{score}分)，重点关注：{', '.join(focus)}")
        return suggestions

    @staticmethod
    def _generate_en_suggestions(breakdown: dict, engine_cfg: dict) -> list:
        suggestions = []
        focus = engine_cfg.get("focus", [])
        for dim, score in breakdown.items():
            if score < 50:
                suggestions.append(f"Improve '{dim}' (current: {score}), focus on: {', '.join(focus)}")
        return suggestions

    @staticmethod
    def _extract_insights(scores: list[EngineScore]) -> tuple:
        strengths = []
        weaknesses = []
        for s in scores:
            for dim, score in s.breakdown.items():
                if score >= 70:
                    strengths.append(f"{s.engine}/{dim}: {score}")
                elif score < 40:
                    weaknesses.append(f"{s.engine}/{dim}: {score}")
        return strengths[:10], weaknesses[:10]


# --- 格式化输出 ---
def format_report(report: AnalysisReport) -> str:
    """格式化分析报告为 Markdown"""
    lines = [
        f"# GEO 适配分析报告",
        f"",
        f"**URL:** {report.url}",
        f"**语言:** {report.language}",
        f"**综合得分:** {report.overall_score}/100",
        f"",
        f"## 引擎评分",
        f"",
        f"| 引擎 | 厂商 | 得分 |",
        f"|------|------|------|",
    ]
    for s in report.engine_scores:
        lines.append(f"| {s.engine} | {s.vendor} | {s.score} |")

    lines.append(f"")
    lines.append(f"## 优势")
    for s in report.strengths:
        lines.append(f"- ✅ {s}")

    lines.append(f"")
    lines.append(f"## 待改进")
    for w in report.weaknesses:
        lines.append(f"- ⚠️ {w}")

    lines.append(f"")
    lines.append(f"## 详细建议")
    for s in report.engine_scores:
        if s.suggestions:
            lines.append(f"\n### {s.engine}")
            for sug in s.suggestions:
                lines.append(f"- {sug}")

    return "\n".join(lines)


# --- 快捷测试 ---
def main():
    config = load_config()
    # 模拟一页内容
    from geo_optimizer.models import CrawledPage
    page = CrawledPage(
        url="https://example.com",
        title="示例页面",
        html="",
        text="这是一个示例文本，包含一些内容。如何优化你的网站？据研究表明...",
        language="zh-CN",
        meta_desc="示例描述",
        meta_keywords="",
        headings=[(1, "标题"), (2, "子标题"), (3, "详细内容")],
        links=[],
        word_count=50,
    )
    analyzer = GEOAnalyzer()
    report = analyzer.analyze(page, config)
    print(format_report(report))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
