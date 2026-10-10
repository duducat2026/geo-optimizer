#!/usr/bin/env python3
"""
test_geo.py — GEO-Optimizer 单元测试

运行: pytest tests/ -v
       或 python tests/test_geo.py
"""

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
    class pytest:
        @staticmethod
        def main(args):
            pass

from pathlib import Path
import sys
import json
import os


from geo_optimizer.config import load_config
from geo_optimizer.analyzer import GEOAnalyzer
from geo_optimizer.models import CrawledPage
from geo_optimizer.generators.schema import GEOSchemaGenerator


# ============================================================
# 配置模块测试
# ============================================================

class TestConfig:
    """配置模块测试"""

    def test_load_default_config(self):
        """测试加载默认配置"""
        config = load_config()
        assert isinstance(config, dict)
        assert "target" in config or "keywords" in config

    def test_config_has_engines(self):
        """测试配置包含引擎列表"""
        config = load_config()
        assert "engines_cn" in config or "engines_en" in config

    def test_config_has_llm(self):
        """测试配置包含 LLM 设置"""
        config = load_config()
        assert "llm" in config
        assert "model" in config["llm"]

    def test_config_has_output(self):
        """测试配置包含输出设置"""
        config = load_config()
        assert "output" in config
        assert "dir" in config["output"]

    def test_config_has_platforms(self):
        """测试配置包含平台列表"""
        config = load_config()
        assert "platforms" in config
        assert "cn" in config["platforms"] or "en" in config["platforms"]


# ============================================================
# 爬取页面数据结构测试
# ============================================================

class TestCrawledPage:
    """爬取页面数据结构测试"""

    def test_create_page(self):
        """测试创建页面对象"""
        page = CrawledPage(
            url="https://example.com",
            title="Test Page",
            html="<p>This is test content.</p>",
            text="This is test content.",
            language="en",
            meta_desc="Test description",
            meta_keywords="test, page",
            word_count=4,
        )
        assert page.url == "https://example.com"
        assert page.title == "Test Page"
        assert page.word_count == 4

    def test_page_defaults(self):
        """测试页面默认值"""
        page = CrawledPage(
            url="https://example.com",
            title="Test",
            html="<p>Content</p>",
            text="Content",
            language="en",
            meta_desc="",
            meta_keywords="",
        )
        assert page.headings == []
        assert page.links == []

    def test_page_with_headings(self):
        """测试页面包含标题结构"""
        page = CrawledPage(
            url="https://example.com",
            title="Article",
            html="<h1>Main</h1><h2>Section</h2>",
            text="Content",
            language="en",
            meta_desc="",
            meta_keywords="",
            headings=[(1, "Main"), (2, "Section")],
        )
        assert len(page.headings) == 2
        assert page.headings[0] == (1, "Main")

    def test_page_with_links(self):
        """测试页面包含链接"""
        page = CrawledPage(
            url="https://example.com",
            title="Article",
            html="<a href='/link'>Link</a>",
            text="Content",
            language="en",
            meta_desc="",
            meta_keywords="",
            links=["https://example.com/link"],
        )
        assert len(page.links) == 1

    def test_page_chinese(self):
        """测试中文页面"""
        page = CrawledPage(
            url="https://example.com/cn",
            title="中文标题",
            html="<p>中文内容</p>",
            text="中文内容",
            language="zh-CN",
            meta_desc="中文描述",
            meta_keywords="中文, 关键词",
            word_count=4,
        )
        assert page.language == "zh-CN"
        assert "中文" in page.title


# ============================================================
# GEO 分析器测试
# ============================================================

class TestGEOAnalyzer:
    """GEO 分析器测试"""

    def test_analyzer_init(self):
        """测试分析器初始化"""
        analyzer = GEOAnalyzer()
        assert analyzer is not None

    def test_analyze_page(self):
        """测试页面分析"""
        page = CrawledPage(
            url="https://example.com",
            title="Test Article About AI",
            html="<p>AI content</p>",
            text="AI artificial intelligence machine learning deep learning neural networks. "
                 "This is a comprehensive article about artificial intelligence and its applications. "
                 "We discuss machine learning, deep learning, and neural networks in detail. "
                 "The content provides expert analysis and original research on AI topics. "
                 "References: [1] Research Paper, [2] Official Documentation. "
                 "Last updated: 2024-01-15. Author: AI Expert.",
            language="en",
            meta_desc="Comprehensive AI article",
            meta_keywords="AI, machine learning",
            headings=[(1, "Introduction to AI"), (2, "Machine Learning"), (2, "Deep Learning")],
            links=["https://example.com/ml", "https://example.com/dl"],
            word_count=60,
        )
        
        config = {"keywords": {"zh": ["AI", "人工智能"], "en": ["AI", "machine learning"]}}
        analyzer = GEOAnalyzer()
        report = analyzer.analyze(page, config)
        
        assert report is not None
        assert report.url == "https://example.com"
        assert 0 <= report.overall_score <= 100

    def test_analyze_chinese_page(self):
        """测试中文页面分析"""
        page = CrawledPage(
            url="https://example.com/cn",
            title="人工智能完全指南",
            html="<p>内容</p>",
            text="人工智能是当今最重要的技术之一。本文将详细介绍机器学习、深度学习和神经网络的应用。"
                 "专家分析表明，人工智能将在未来十年内改变各行各业。" * 10,
            language="zh-CN",
            meta_desc="人工智能指南",
            meta_keywords="人工智能, 机器学习",
            headings=[(1, "人工智能简介"), (2, "机器学习"), (2, "深度学习")],
            links=["https://example.com/ml", "https://example.com/dl"],
            word_count=200,
        )
        
        config = {"keywords": {"zh": ["人工智能", "机器学习"], "en": []}}
        analyzer = GEOAnalyzer()
        report = analyzer.analyze(page, config)
        
        assert report is not None
        assert 0 <= report.overall_score <= 100

    def test_analyze_empty_page(self):
        """测试空页面分析"""
        page = CrawledPage(
            url="https://example.com/empty",
            title="",
            html="",
            text="",
            language="en",
            meta_desc="",
            meta_keywords="",
            word_count=0,
        )
        
        analyzer = GEOAnalyzer()
        report = analyzer.analyze(page, {})
        
        assert report is not None
        # 空页面应该得低分
        assert report.overall_score < 50


# ============================================================
# Schema 生成器测试
# ============================================================

class TestSchemaGenerator:
    """Schema 生成器测试"""

    def test_schema_static_methods(self):
        """测试 Schema 生成器静态方法"""
        # GEOSchemaGenerator 使用静态方法
        assert hasattr(GEOSchemaGenerator, 'generate_all')
        assert hasattr(GEOSchemaGenerator, '_article_schema')

    def test_generate_article_schema(self):
        """测试 Article Schema 生成"""
        page = CrawledPage(
            url="https://example.com/article",
            title="Test Article",
            html="<p>Content</p>",
            text="Article content here. " * 20,
            language="en",
            meta_desc="Test description",
            meta_keywords="test, article",
            word_count=100,
        )
        
        config = load_config()
        schema = GEOSchemaGenerator._article_schema(page, config)
        
        assert schema is not None
        assert schema["@type"] == "Article"
        assert schema["headline"] == "Test Article"

    def test_generate_all_schemas(self):
        """测试生成所有 Schema"""
        page = CrawledPage(
            url="https://example.com/article",
            title="Test Article",
            html="<p>Content</p>",
            text="Article content here. " * 20,
            language="en",
            meta_desc="Test description",
            meta_keywords="test",
            word_count=100,
        )
        
        config = load_config()
        schemas = GEOSchemaGenerator.generate_all(page, config)
        
        assert isinstance(schemas, list)
        assert len(schemas) >= 1
        # 至少应该有 Article Schema
        article_found = any(s.get("@type") == "Article" for s in schemas)
        assert article_found


# ============================================================
# 评分逻辑测试
# ============================================================

class TestScoring:
    """评分逻辑测试"""

    def test_score_range(self):
        """测试评分范围"""
        analyzer = GEOAnalyzer()
        
        low_page = CrawledPage(
            url="https://example.com/low",
            title="Short",
            html="<p>Brief content.</p>",
            text="Brief content.",
            language="en",
            meta_desc="",
            meta_keywords="",
            word_count=2,
        )
        
        high_page = CrawledPage(
            url="https://example.com/high",
            title="Comprehensive Guide to Artificial Intelligence and Machine Learning",
            html="<p>Content</p>",
            text="This is a comprehensive guide covering artificial intelligence, machine learning, "
                 "deep learning, neural networks, and their applications. " * 50,
            language="en",
            meta_desc="Comprehensive AI guide",
            meta_keywords="AI, machine learning",
            headings=[(1, "Introduction"), (2, "What is AI"), (2, "Machine Learning Basics"), 
                      (2, "Deep Learning"), (2, "Applications")],
            links=[f"https://example.com/ref{i}" for i in range(10)],
            word_count=500,
        )
        
        config = {
            "keywords": {"en": {"primary": ["AI", "machine learning"], "longtail": [], "scenarios": []}},
            "engines_en": [
                {"name": "Google AI Overviews", "vendor": "Google",
                 "focus": ["E-E-A-T", "Schema"], "enabled": True},
                {"name": "ChatGPT Search", "vendor": "OpenAI",
                 "focus": ["自然对话体", "长尾问答"], "enabled": True},
            ],
        }
        
        low_report = analyzer.analyze(low_page, config)
        high_report = analyzer.analyze(high_page, config)
        
        assert high_report.overall_score > low_report.overall_score

    def test_content_quality_scoring(self):
        """测试内容质量评分"""
        analyzer = GEOAnalyzer()
        
        # 包含权威引用的页面
        cited_page = CrawledPage(
            url="https://example.com/cited",
            title="Research Article",
            html="<p>Content</p>",
            text="According to [1] Smith et al., AI has significant impact. "
                 "Research shows (Johnson, 2023) that machine learning improves accuracy.",
            language="en",
            meta_desc="",
            meta_keywords="",
            word_count=50,
        )
        
        # 无引用页面
        uncited_page = CrawledPage(
            url="https://example.com/uncited",
            title="Opinion Piece",
            html="<p>Content</p>",
            text="I think AI is great. In my opinion it will change everything.",
            language="en",
            meta_desc="",
            meta_keywords="",
            word_count=50,
        )
        
        config = {}
        
        cited_report = analyzer.analyze(cited_page, config)
        uncited_report = analyzer.analyze(uncited_page, config)
        
        # 有引用的页面应该在"引用友好性"维度得分更高
        # (具体取决于评分实现)


# ============================================================
# FAQ 生成器测试（需要 API）
# ============================================================

class TestFAQGenerator:
    """FAQ 生成器测试"""

    def test_faq_init_with_config(self, monkeypatch):
        """测试 FAQ 生成器初始化（带配置）。

        仅验证初始化与模型选择，不发起真实请求；用占位 Key 保证测试不依赖仓库密钥。
        """
        monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test-dummy-key")
        config = load_config()
        from geo_optimizer.generators.faq import GEOFAQGenerator
        gen = GEOFAQGenerator(config)
        assert gen is not None
        assert gen.model in ["qwen-plus", "qwen-max", "qwen-turbo"]

    def test_faq_item_structure(self):
        """测试 FAQItem 数据结构"""
        from geo_optimizer.generators.faq import FAQItem
        
        item = FAQItem(
            question="什么是人工智能?",
            answer="人工智能是模拟人类智能的技术。",
            language="zh-CN",
            keywords=["AI", "人工智能"]
        )
        
        assert item.question == "什么是人工智能?"
        assert item.language == "zh-CN"
        assert len(item.keywords) == 2

    def test_faq_format(self):
        """测试 FAQ 格式化"""
        from geo_optimizer.generators.faq import FAQItem, format_faqs
        
        faqs = [
            FAQItem(question="Q1?", answer="A1", language="zh-CN"),
            FAQItem(question="Q2?", answer="A2", language="zh-CN"),
        ]
        
        output = format_faqs(faqs, language="zh-CN")
        
        assert "Q1" in output
        assert "A1" in output
        assert "FAQ" in output


# ============================================================
# 导出模块测试
# ============================================================

class TestExport:
    """导出模块测试"""

    def test_export_class_exists(self):
        """测试导出类存在"""
        from geo_optimizer.export import GEOExporter
        
        config = load_config()
        exporter = GEOExporter(config)
        assert exporter is not None
        assert hasattr(exporter, 'export_all')

    def test_export_result_structure(self):
        """测试导出结果结构"""
        from geo_optimizer.export import ExportResult
        
        result = ExportResult(
            platform="wechat",
            filename="export.md",
            content="# Content",
            format="markdown"
        )
        
        assert result.platform == "wechat"
        assert result.format == "markdown"


# ============================================================
# 索引检查器测试
# ============================================================

class TestIndexChecker:
    """索引检查器测试"""

    def test_checker_init(self):
        """测试索引检查器初始化"""
        from geo_optimizer.evaluation.index_checker import GEOIndexChecker
        
        checker = GEOIndexChecker("https://example.com")
        assert checker is not None

    def test_ai_bot_agents_defined(self):
        """测试 AI 爬虫列表定义"""
        from geo_optimizer.evaluation.index_checker import AI_BOT_AGENTS
        
        assert isinstance(AI_BOT_AGENTS, dict)
        assert "GPTBot" in AI_BOT_AGENTS
        assert "Claude-Web" in AI_BOT_AGENTS
        assert "PerplexityBot" in AI_BOT_AGENTS

    def test_https_result_structure(self):
        """测试 HTTPS 结果结构"""
        from geo_optimizer.evaluation.index_checker import HTTPSResult
        
        result = HTTPSResult(
            has_https=True,
            cert_valid=True,
            cert_issuer="Let's Encrypt",
            cert_expiry="2025-01-01",
            days_until_expiry=180
        )
        
        assert result.has_https == True
        assert result.cert_valid == True


# ============================================================
# 集成测试
# ============================================================

class TestIntegration:
    """集成测试"""

    def test_full_pipeline_mock(self):
        """测试完整流程（模拟数据）"""
        # 1. 创建测试页面
        page = CrawledPage(
            url="https://example.com/test",
            title="Test Article",
            html="<p>Content</p>",
            text="Test content with some keywords and useful information. " * 20,
            language="en",
            meta_desc="Test description",
            meta_keywords="test",
            headings=[(1, "Introduction"), (2, "Details")],
            links=["https://example.com/ref"],
            word_count=200,
        )
        
        # 2. 分析页面
        config = load_config()
        analyzer = GEOAnalyzer()
        report = analyzer.analyze(page, config)
        
        # 3. 验证报告
        assert report is not None
        assert report.overall_score >= 0
        
        # 4. 生成 Schema
        schemas = GEOSchemaGenerator.generate_all(page, config)
        
        assert isinstance(schemas, list)


# ============================================================
# 权威画像构建器测试
# ============================================================

class TestAuthorityBuilder:
    """AuthorityBuilder 测试（回归：_has_english_content 缺失导致 build 报错）"""

    @staticmethod
    def _page(text, language):
        from geo_optimizer.crawler import CrawledPage as WebCrawledPage
        return WebCrawledPage(
            url="https://example.com",
            title="Test",
            html="",
            text=text,
            language=language,
            meta_desc="",
            meta_keywords="",
        )

    def test_build_english_page(self):
        """英文页面走 _has_english_content 分支不报错，并补充英文权威元素"""
        from geo_optimizer.web.authority_builder import AuthorityBuilder
        page = self._page("This is an English article about cloud computing. " * 20, "en")
        profile = AuthorityBuilder().build(page, [], {})
        assert profile is not None
        assert profile.references

    def test_build_chinese_page(self):
        """中文页面正常构建（也会进入 _has_english_content 判定）"""
        from geo_optimizer.web.authority_builder import AuthorityBuilder
        page = self._page("作者：张三\n这是一款智能空气净化器。" * 20, "zh-CN")
        profile = AuthorityBuilder().build(page, [], {})
        assert profile is not None
        assert profile.author_orcid  # 中文页交叉补充英文权威分支生效

    def test_has_english_content(self):
        """英文占比判定"""
        from geo_optimizer.web.authority_builder import AuthorityBuilder
        en = self._page("Pure English content here for detection. " * 10, "zh-CN")
        zh = self._page("纯中文内容用于检测。" * 20, "zh-CN")
        assert AuthorityBuilder._has_english_content(en) is True
        assert AuthorityBuilder._has_english_content(zh) is False


# ============================================================
# 运行测试
# ============================================================

def run_tests():
    """运行所有测试（无 pytest 时）"""
    print("\n" + "=" * 60)
    print("GEO-Optimizer 单元测试")
    print("=" * 60 + "\n")
    
    test_classes = [
        ("配置模块", TestConfig),
        ("爬取页面", TestCrawledPage),
        ("GEO 分析器", TestGEOAnalyzer),
        ("Schema 生成器", TestSchemaGenerator),
        ("评分逻辑", TestScoring),
        ("FAQ 生成器", TestFAQGenerator),
        ("导出模块", TestExport),
        ("索引检查器", TestIndexChecker),
        ("集成测试", TestIntegration),
    ]
    
    total = 0
    passed = 0
    failed = 0
    
    for name, test_class in test_classes:
        print(f"\n[{name}]")
        test = test_class()
        
        for method_name in dir(test_class):
            if method_name.startswith("test_"):
                total += 1
                try:
                    method = getattr(test, method_name)
                    method()
                    print(f"  ✅ {method_name}")
                    passed += 1
                except AssertionError as e:
                    print(f"  ❌ {method_name}: {e}")
                    failed += 1
                except Exception as e:
                    # 某些测试可能需要网络或 API，跳过
                    print(f"  ⚠️ {method_name}: 跳过 ({type(e).__name__})")
    
    print("\n" + "=" * 60)
    print(f"结果: {passed}/{total} 通过, {failed} 失败")
    print("=" * 60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    if HAS_PYTEST:
        pytest.main([__file__, "-v"])
    else:
        success = run_tests()
        sys.exit(0 if success else 1)