#!/usr/bin/env python3
"""
basic_usage.py — GEO-Optimizer 使用示例

运行: python examples/basic_usage.py
"""

import sys
from pathlib import Path


from geo_optimizer.config import load_config
from geo_optimizer.crawler import crawl_sync, CrawledPage
from geo_optimizer.analyzer import GEOAnalyzer, format_report
from geo_optimizer.generators.faq import GEOFAQGenerator
from geo_optimizer.generators.schema import GEOSchemaGenerator


def example_analyze():
    """示例: 分析页面 GEO 就绪度"""
    print("=" * 60)
    print("示例 1: GEO 就绪度分析")
    print("=" * 60)
    
    # 模拟爬取的页面数据
    page = CrawledPage(
        url="https://example.com/ai-guide",
        title="Complete Guide to Artificial Intelligence 2024",
        content="""
        Artificial Intelligence (AI) represents one of the most transformative technologies of our time.
        
        This comprehensive guide covers:
        - Machine Learning fundamentals
        - Deep Learning architectures
        - Neural network applications
        - Natural Language Processing
        - Computer Vision
        
        Key Statistics:
        - 80% of businesses will use AI by 2025
        - AI market size: $500 billion by 2024
        - 97% of mobile users use AI-powered assistants
        
        References:
        [1] Gartner AI Report 2024
        [2] McKinsey Global AI Survey
        [3] Stanford AI Index Report
        
        Expert Analysis by Dr. Jane Smith, AI Research Lead at MIT
        Last updated: January 2024
        """ * 5,  # 重复以达到足够字数
        headings=[
            "Introduction to AI",
            "Machine Learning Basics",
            "Deep Learning Explained",
            "Neural Network Architectures",
            "Real-World Applications",
            "Future of AI",
        ],
        links=[
            "https://example.com/ml-basics",
            "https://example.com/deep-learning",
            "https://example.com/neural-networks",
            "https://example.com/nlp-guide",
        ],
        meta={
            "description": "Comprehensive guide to AI covering ML, deep learning, and neural networks",
            "author": "Dr. Jane Smith",
            "publish_date": "2024-01-15",
        },
        word_count=500,
    )
    
    config = load_config()
    analyzer = GEOAnalyzer()
    report = analyzer.analyze(page, config)
    
    print(format_report(report))
    return page, report


def example_faq(page, report):
    """示例: 生成 FAQ"""
    print("\n" + "=" * 60)
    print("示例 2: FAQ 生成")
    print("=" * 60)
    
    config = load_config()
    faq_gen = GEOFAQGenerator(config)
    faqs = faq_gen.generate_faqs(page, report, config)
    
    print(f"生成了 {len(faqs)} 个 FAQ:\n")
    for i, faq in enumerate(faqs[:5], 1):
        print(f"Q{i}: {faq.question}")
        print(f"A{i}: {faq.answer[:100]}...")
        print()


def example_schema(page):
    """示例: 生成 Schema"""
    print("\n" + "=" * 60)
    print("示例 3: Schema 结构化数据生成")
    print("=" * 60)
    
    config = load_config()
    
    # 生成 FAQ
    faq_gen = GEOFAQGenerator(config)
    faqs = faq_gen.generate_faqs(page, {}, config)
    
    # 生成 Schema
    schema_gen = GEOSchemaGenerator(config)
    result = schema_gen.generate_all_schemas(page, faqs, config)
    
    print(f"生成了 {len(result.schemas)} 个 Schema:")
    for name in result.schemas:
        print(f"  - {name}")


def example_eval():
    """示例: GEO 评估"""
    print("\n" + "=" * 60)
    print("示例 4: GEO 多引擎评估")
    print("=" * 60)
    
    from geo_optimizer.evaluation.evaluator import GEOEvaluator
    
    evaluator = GEOEvaluator("example.com", ["AI", "machine learning"])
    report = evaluator.evaluate(run_index_check=False)
    
    print(f"域名: {report.domain}")
    print(f"综合评分: {report.overall_score:.1f}/100 ({report.overall_grade})")
    print(f"检测引擎数: {len(report.engines)}")
    
    print("\n国内引擎:")
    for e in report.engines:
        if e.category == "domestic":
            status = "✅" if e.indexed else "❌"
            print(f"  {status} {e.engine_name}: {e.overall_score:.1f}分")
    
    print("\n国外引擎:")
    for e in report.engines:
        if e.category == "international":
            status = "✅" if e.indexed else "❌"
            print(f"  {status} {e.engine_name}: {e.overall_score:.1f}分")


def main():
    """运行所有示例"""
    print("\n🚀 GEO-Optimizer 使用示例\n")
    
    # 示例 1: 分析
    page, report = example_analyze()
    
    # 示例 2: FAQ
    example_faq(page, report)
    
    # 示例 3: Schema
    example_schema(page)
    
    # 示例 4: 评估
    example_eval()
    
    print("\n✅ 所有示例运行完成!\n")


if __name__ == "__main__":
    main()