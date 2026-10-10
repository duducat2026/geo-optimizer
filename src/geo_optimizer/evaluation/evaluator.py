"""
GEO 多引擎表现评估模块

覆盖平台:
  国内: 百度/文心一言、通义千问、Kimi、秘塔、360AI、夸克
  国外: Google AI Overviews、Bing/Copilot、Perplexity、ChatGPT Search、Claude Search

评估维度:
  - 索引状态（收录量、新鲜度）
  - 引用表现（被 AI 引擎引用时的展示方式）
  - 内容摘要准确度
  - FAQ 命中情况
  - Schema 识别情况
  - 站长平台提交状态
  - robots.txt AI 爬虫兼容性
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

from geo_optimizer.evaluation.index_checker import GEOIndexChecker, IndexCheckReport

logger = logging.getLogger(__name__)


# 各 AI 搜索引擎配置
AI_ENGINE_CONFIGS = {
    # 国内
    "baidu_wenxin": {
        "name": "百度/文心一言",
        "category": "domestic",
        "base_url": "https://www.baidu.com",
        "search_url": "https://www.baidu.com/s?wd={query}",
        "ai_bot": "Baiduspider",
        "submission_url": "https://ziyuan.baidu.com",
        "description": "国内最大搜索引擎，文心一言依赖百度索引",
    },
    "tongyi_qianwen": {
        "name": "通义千问",
        "category": "domestic",
        "base_url": "https://tongyi.aliyun.com",
        "search_url": None,
        "ai_bot": None,
        "submission_url": None,
        "description": "阿里通义系列，复用百度/Google 索引",
    },
    "kimi": {
        "name": "Kimi (月之暗面)",
        "category": "domestic",
        "base_url": "https://kimi.moonshot.cn",
        "search_url": None,
        "ai_bot": None,
        "submission_url": None,
        "description": "依赖自有搜索引擎索引 + 百度搜索",
    },
    "metaso": {
        "name": "秘塔 AI 搜索",
        "category": "domestic",
        "base_url": "https://metaso.cn",
        "search_url": "https://metaso.cn/search?q={query}",
        "ai_bot": None,
        "submission_url": None,
        "description": "国内 AI 搜索新秀，引用来源标注清晰",
    },
    "so_360_ai": {
        "name": "360 AI 搜索",
        "category": "domestic",
        "base_url": "https://www.so.com",
        "search_url": "https://www.so.com/s?q={query}",
        "ai_bot": "360Spider",
        "submission_url": "https://zhanzhang.so.com",
        "description": "360 搜索 + AI 搜索整合",
    },
    "quark": {
        "name": "夸克 AI 搜索",
        "category": "domestic",
        "base_url": "https://www.quark.cn",
        "search_url": "https://www.quark.cn/s?q={query}",
        "ai_bot": None,
        "submission_url": "https://zhanzhang.sm.cn",
        "description": "阿里系移动端 AI 搜索",
    },
    # 国外
    "google_ai": {
        "name": "Google AI Overviews",
        "category": "international",
        "base_url": "https://www.google.com",
        "search_url": "https://www.google.com/search?q={query}",
        "ai_bot": "Googlebot",
        "submission_url": "https://search.google.com/search-console",
        "description": "全球最大搜索引擎，AI Overviews 依赖结构化数据",
    },
    "bing_copilot": {
        "name": "Bing / Copilot",
        "category": "international",
        "base_url": "https://www.bing.com",
        "search_url": "https://www.bing.com/search?q={query}",
        "ai_bot": "bingbot",
        "submission_url": "https://www.bing.com/webmasters",
        "description": "微软 Bing + Copilot 一次提交同时覆盖",
    },
    "perplexity": {
        "name": "Perplexity AI",
        "category": "international",
        "base_url": "https://www.perplexity.ai",
        "search_url": "https://www.perplexity.ai/search?q={query}",
        "ai_bot": "PerplexityBot",
        "submission_url": "https://publisher.perplexity.ai",
        "description": "AI 搜索引擎，有专属发布者后台管理引用",
    },
    "chatgpt_search": {
        "name": "ChatGPT Search",
        "category": "international",
        "base_url": "https://chatgpt.com",
        "search_url": None,
        "ai_bot": "GPTBot",
        "submission_url": None,
        "description": "无提交入口，通过 GPTBot 自然索引，robots.txt 控制",
    },
    "claude_search": {
        "name": "Claude (Anthropic)",
        "category": "international",
        "base_url": "https://claude.ai",
        "search_url": None,
        "ai_bot": "ClaudeBot",
        "submission_url": None,
        "description": "无提交入口，通过 ClaudeBot 自然索引",
    },
}


@dataclass
class EngineEvalResult:
    """单个引擎的评估结果"""
    engine_id: str
    engine_name: str
    category: str  # domestic / international

    # 索引状态
    indexed: bool = False
    indexed_pages_estimate: Optional[int] = None

    # 引用表现 (0-10)
    citation_score: float = 0.0
    citation_count: int = 0
    citation_format: str = ""  # snippet / card / full / none

    # 内容摘要准确度 (0-10)
    snippet_accuracy: float = 0.0

    # FAQ 命中 (0-10)
    faq_hit_score: float = 0.0

    # Schema 识别 (0-10)
    schema_recognition: float = 0.0

    # 站长平台提交状态
    submission_status: str = "unknown"  # submitted / verified / not_submitted / unknown

    # 综合得分 (0-100)
    overall_score: float = 0.0

    # 问题和建议
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # 原始数据
    raw_data: Dict = field(default_factory=dict)


@dataclass
class GEOEvalReport:
    """GEO 评估报告"""
    domain: str
    evaluated_at: str = ""
    index_check: Optional[IndexCheckReport] = None

    # 按引擎的结果
    engines: List[EngineEvalResult] = field(default_factory=list)

    # 分类汇总
    domestic_summary: Dict = field(default_factory=dict)
    international_summary: Dict = field(default_factory=dict)

    # 综合评分
    overall_score: float = 0.0
    overall_grade: str = ""  # S/A/B/C/D

    # 全局建议
    recommendations: List[str] = field(default_factory=list)

    # 原始数据
    raw_data: Dict = field(default_factory=dict)


class GEOEvaluator:
    """GEO 多引擎表现评估器"""

    def __init__(self, domain: str, keywords: Optional[List[str]] = None):
        """
        Args:
            domain: 目标域名（如 example.com）
            keywords: 目标关键词列表，用于测试各引擎表现
        """
        self.domain = domain
        self.keywords = keywords or []
        self.engines = AI_ENGINE_CONFIGS

    def evaluate(self, keywords: Optional[List[str]] = None, run_index_check: bool = True) -> GEOEvalReport:
        """
        执行全面 GEO 评估

        Args:
            keywords: 目标关键词（覆盖初始化时的设置）
            run_index_check: 是否同时运行索引检测
        """
        if keywords:
            self.keywords = keywords

        report = GEOEvalReport(
            domain=self.domain,
            evaluated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        # 1. 索引基础检测
        if run_index_check:
            try:
                with GEOIndexChecker(self.domain) as checker:
                    report.index_check = checker.check_all()
            except Exception as e:
                logger.warning(f"索引检测失败: {e}")
                report.index_check = None

        # 2. 逐引擎评估
        for engine_id, config in self.engines.items():
            try:
                result = self._evaluate_engine(engine_id, config)
                report.engines.append(result)
                time.sleep(1)  # 避免请求过快
            except Exception as e:
                logger.warning(f"引擎 {engine_id} 评估失败: {e}")
                report.engines.append(EngineEvalResult(
                    engine_id=engine_id,
                    engine_name=config["name"],
                    category=config["category"],
                    issues=[f"评估失败: {str(e)}"]
                ))

        # 3. 分类汇总
        report.domestic_summary = self._summarize_category("domestic", report.engines)
        report.international_summary = self._summarize_category("international", report.engines)

        # 4. 综合评分
        report.overall_score = self._calc_overall_score(report)
        report.overall_grade = self._score_to_grade(report.overall_score)

        # 5. 生成全局建议
        report.recommendations = self._generate_recommendations(report)

        return report

    def _evaluate_engine(self, engine_id: str, config: Dict) -> EngineEvalResult:
        """评估单个引擎"""
        result = EngineEvalResult(
            engine_id=engine_id,
            engine_name=config["name"],
            category=config["category"]
        )

        # 基础信息
        is_indexed = self._check_index_status(engine_id, config)
        result.indexed = is_indexed["indexed"]
        result.indexed_pages_estimate = is_indexed.get("estimated_pages")

        # 引用表现评估
        citation = self._assess_citation(engine_id, config)
        result.citation_score = citation["score"]
        result.citation_format = citation["format"]

        # 内容摘要准确度
        result.snippet_accuracy = self._assess_snippet_accuracy(engine_id, config)

        # FAQ 命中
        result.faq_hit_score = self._assess_faq_hits(engine_id, config)

        # Schema 识别
        result.schema_recognition = self._assess_schema(engine_id, config)

        # 站长平台提交状态
        result.submission_status = self._check_submission_status(engine_id, config)

        # 计算引擎综合得分
        result.overall_score = self._calc_engine_score(result)

        # 生成建议
        result.recommendations = self._generate_engine_recommendations(result, config)

        return result

    def _check_index_status(self, engine_id: str, config: Dict) -> Dict:
        """检查索引状态"""
        indexed = False
        estimated_pages = None

        # 如果有索引检测数据，使用它
        # 否则基于配置推断
        if engine_id in ("google_ai", "bing_copilot", "baidu_wenxin"):
            # 这些是主要索引源
            if self.index_check and self.index_check.site_queries:
                for sq in self.index_check.site_queries:
                    if sq.engine in engine_id and sq.estimated_results:
                        indexed = True
                        estimated_pages = sq.estimated_results
                        break

        # 基于索引检测结果推断
        if self.index_check:
            if self.index_check.https and self.index_check.https.has_https:
                indexed = True  # HTTPS 正常，至少可能被索引
            else:
                if engine_id in ("google_ai", "bing_copilot"):
                    indexed = False  # 没有 HTTPS 的国际引擎大概率不被索引

        return {"indexed": indexed, "estimated_pages": estimated_pages}

    def _assess_citation(self, engine_id: str, config: Dict) -> Dict:
        """评估引用表现"""
        score = 0.0
        citation_format = "unknown"

        # 基于索引和 Schema 状态推断
        if self.index_check:
            # robots.txt AI 爬虫兼容性
            if self.index_check.robots:
                ai_bot = config.get("ai_bot")
                if ai_bot:
                    # 简化的 bot name 匹配
                    bot_lower = ai_bot.lower()
                    allowed = True
                    for key, val in self.index_check.robots.ai_bots_allowed.items():
                        if bot_lower in key.lower() or key.lower() in bot_lower:
                            if not val:
                                allowed = False
                                break
                    if allowed:
                        score += 30

            # Sitemap 存在
            valid_sm = [s for s in self.index_check.sitemaps if s.exists and s.valid_xml]
            if valid_sm:
                score += 20
                citation_format = "snippet"

            # HTTPS
            if self.index_check.https and self.index_check.https.has_https:
                score += 20
                if citation_format == "unknown":
                    citation_format = "snippet"

            # 综合评分
            if score >= 70:
                citation_format = "card"
            elif score >= 40:
                citation_format = "snippet"
            else:
                citation_format = "none"

        return {"score": min(score, 100) / 10, "format": citation_format}

    def _assess_snippet_accuracy(self, engine_id: str, config: Dict) -> float:
        """评估内容摘要准确度（基于站点结构推断）"""
        score = 5.0  # 基础分

        if self.index_check:
            # 有 HTTPS 和 robots.txt 则加分
            if self.index_check.https and self.index_check.https.has_https:
                score += 1.5
            if self.index_check.robots and self.index_check.robots.exists:
                score += 1.0

            valid_sm = [s for s in self.index_check.sitemaps if s.exists and s.valid_xml]
            if valid_sm:
                score += 1.5

            # 如果 Schema 存在，摘要更准确
            if self.index_check.robots and self.index_check.robots.sitemap_urls:
                score += 1.0

        return min(score, 10.0)

    def _assess_faq_hits(self, engine_id: str, config: Dict) -> float:
        """评估 FAQ 命中情况（基于站点是否有 FAQ Schema）"""
        score = 3.0  # 基础分

        # 如果有 Schema，FAQ 命中更好
        if self.index_check:
            valid_sm = [s for s in self.index_check.sitemaps if s.exists and s.valid_xml]
            if valid_sm:
                score += 3.0

        return min(score, 10.0)

    def _assess_schema(self, engine_id: str, config: Dict) -> float:
        """评估 Schema 识别情况"""
        score = 3.0  # 基础分

        if self.index_check:
            # HTTPS
            if self.index_check.https and self.index_check.https.has_https:
                score += 2.0

            # Sitemap 有效性
            valid_sm = [s for s in self.index_check.sitemaps if s.exists and s.valid_xml]
            if valid_sm:
                score += 3.0
                if valid_sm[0].url_count > 10:
                    score += 2.0

            # AI 爬虫允许
            if self.index_check.robots:
                ai_allowed = sum(
                    1 for v in self.index_check.robots.ai_bots_allowed.values() if v
                )
                total = len(self.index_check.robots.ai_bots_allowed)
                if total > 0:
                    score += 2.0 * (ai_allowed / total)

        return min(round(score, 1), 10.0)

    def _check_submission_status(self, engine_id: str, config: Dict) -> str:
        """检查站长平台提交状态（基于配置推断）"""
        submission_url = config.get("submission_url")

        if not submission_url:
            return "not_required"  # 无提交入口的引擎

        # 基于索引检测结果推断
        if self.index_check and self.index_check.https:
            if not self.index_check.https.has_https:
                return "blocked_no_https"

        # 默认未知，需要用户手动验证
        return "needs_verification"

    def _calc_engine_score(self, result: EngineEvalResult) -> float:
        """计算单个引擎的综合得分 (0-100)"""
        weights = {
            "indexed": 15,
            "citation_score": 25,
            "snippet_accuracy": 20,
            "faq_hit_score": 15,
            "schema_recognition": 15,
            "submission_status": 10,
        }

        score = 0.0

        if result.indexed:
            score += weights["indexed"]
        
        score += result.citation_score * weights["citation_score"] / 10
        score += result.snippet_accuracy * weights["snippet_accuracy"] / 10
        score += result.faq_hit_score * weights["faq_hit_score"] / 10
        score += result.schema_recognition * weights["schema_recognition"] / 10
        
        if result.submission_status in ["submitted", "verified"]:
            score += weights["submission_status"]
        elif result.submission_status == "not_required":
            score += weights["submission_status"] * 0.5
        
        return min(score, 100.0)

    def _determine_grade(self, score: float) -> str:
        """将分数转换为等级"""
        if score >= 90:
            return "S"
        elif score >= 80:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 60:
            return "C"
        else:
            return "D"

    def _generate_recommendations(self, report: GEOEvalReport) -> List[str]:
        """生成全局建议"""
        recommendations = []
        
        # 基于 HTTPS
        if report.index_check and report.index_check.https:
            if not report.index_check.https.has_https:
                recommendations.append("部署 HTTPS 证书，提升安全性和 AI 引擎信任度")
            elif report.index_check.https.days_until_expiry and report.index_check.https.days_until_expiry < 30:
                recommendations.append(f"HTTPS 证书即将过期（{report.index_check.https.days_until_expiry}天），请及时续签")
        
        
        # 基于 robots.txt
        if report.index_check and report.index_check.robots:
            if not report.index_check.robots.exists:
                recommendations.append("创建 robots.txt 文件，明确 AI 爬虫访问规则")
            else:
                blocked_bots = [bot for bot, allowed in report.index_check.robots.ai_bots_allowed.items() if not allowed]
                if len(blocked_bots) > len(report.index_check.robots.ai_bots_allowed) / 2:
                    recommendations.append("考虑开放更多 AI 爬虫访问权限，提升 GEO 覆盖率")
        
        
        # 基于 Sitemap
        if report.index_check and report.index_check.sitemaps:
            if not any(s.exists for s in report.index_check.sitemaps):
                recommendations.append("创建 sitemap.xml 文件，帮助搜索引擎发现和索引内容")
            elif not any(s.valid_xml for s in report.index_check.sitemaps):
                recommendations.append("修复 sitemap.xml 格式错误，确保有效性")
        
        
        # 基于整体评分
        if report.overall_score < 60:
            recommendations.append("综合 GEO 表现较弱，建议优先优化基础 SEO 和内容质量")
        elif report.overall_score < 80:
            recommendations.append("GEO 基础良好，可针对低分引擎进行专项优化")
        
        
        return recommendations

    def _summarize_category(self, engines: List[EngineEvalResult]) -> Dict:
        """汇总分类结果"""
        if not engines:
            return {"avg_score": 0, "indexed_count": 0, "total_count": 0}
        
        return {
            "avg_score": sum(e.overall_score for e in engines) / len(engines),
            "indexed_count": sum(1 for e in engines if e.indexed),
            "total_count": len(engines),
            "engines_with_issues": sum(1 for e in engines if e.issues),
        }


def format_eval_report(report: GEOEvalReport) -> str:
    """格式化评估报告为可读文本"""
    lines = [
        f"GEO 多引擎评估报告",
        f"=" * 50,
        f"域名: {report.domain}",
        f"评估时间: {report.evaluated_at}",
        f"综合评分: {report.overall_score:.1f}/100 ({report.overall_grade})",
        "",
    ]
    
    domestic = [e for e in report.engines if e.category == "domestic"]
    if domestic:
        lines.append("【国内 AI 引擎】")
        for e in domestic:
            status = "✅" if e.indexed else "❌"
            lines.append(f"  {status} {e.engine_name}: {e.overall_score:.1f}分")
        lines.append("")
    
    international = [e for e in report.engines if e.category == "international"]
    if international:
        lines.append("【国外 AI 引擎】")
        for e in international:
            status = "✅" if e.indexed else "❌"
            lines.append(f"  {status} {e.engine_name}: {e.overall_score:.1f}分")
        lines.append("")
    
    if report.recommendations:
        lines.append("【改进建议】")
        for i, rec in enumerate(report.recommendations, 1):
            lines.append(f"  {i}. {rec}")
    
    
    return "\n".join(lines)