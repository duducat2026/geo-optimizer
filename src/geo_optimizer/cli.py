#!/usr/bin/env python3
"""
cli.py — GEO-Optimizer CLI 统一入口

用法:
  geo-optimizer analyze <URL>              # 爬取 + 分析
  geo-optimizer optimize <URL>             # 完整优化 pipeline
  geo-optimizer export <URL>               # 优化 + 多平台导出
  geo-optimizer monitor <URL>              # 引擎引用监控
  geo-optimizer report <URL>               # 生成分析报告
  geo-optimizer faq <URL>                  # 仅生成 FAQ
  geo-optimizer schema <URL>               # 仅生成 Schema

  未安装时可用: python -m geo_optimizer <子命令> <URL>

环境变量:
  DASHSCOPE_API_KEY     百炼 API Key
  GEO_CONFIG            配置文件路径（默认 geo_config.yaml）
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path


from geo_optimizer.config import load_config
from geo_optimizer.crawler import crawl_sync, GEOCrawler
from geo_optimizer.analyzer import GEOAnalyzer, format_report
from geo_optimizer.generators.content import GEOContentGenerator
from geo_optimizer.generators.faq import GEOFAQGenerator
from geo_optimizer.generators.schema import GEOSchemaGenerator
from geo_optimizer.export import GEOExporter
from geo_optimizer.evaluation.monitor import GEOMonitor
from geo_optimizer.evaluation.evaluator import GEOEvaluator, GEOEvalReport
from geo_optimizer.evaluation.index_checker import GEOIndexChecker


def setup_logging(verbose: bool = False):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_analyze(args, config):
    """爬取 + 分析"""
    logging.info(f"开始分析: {args.url}")

    # 1. 爬取
    logging.info("Step 1/2: 爬取页面...")
    pages = crawl_sync(config, [args.url])
    if not pages:
        logging.error("爬取失败，未获取到页面内容")
        return

    page = pages[0]
    logging.info(f"  标题: {page.title}")
    logging.info(f"  词数: {page.word_count}")
    logging.info(f"  链接数: {len(page.links)}")

    # 2. 分析
    logging.info("Step 2/2: GEO 就绪度分析...")
    analyzer = GEOAnalyzer()
    report = analyzer.analyze(page, config)

    print("\n" + "=" * 60)
    print(format_report(report))
    print("=" * 60)


def cmd_faq(args, config):
    """仅生成 FAQ"""
    logging.info(f"为 {args.url} 生成 FAQ...")

    pages = crawl_sync(config, [args.url])
    if not pages:
        logging.error("爬取失败")
        return

    page = pages[0]
    analyzer = GEOAnalyzer()
    report = analyzer.analyze(page, config)

    faq_gen = GEOFAQGenerator(config)
    faqs = faq_gen.generate_faqs(page, report, config)

    print("\n" + "=" * 60)
    print(f"生成了 {len(faqs)} 个 FAQ 问答对:\n")
    for i, faq in enumerate(faqs, 1):
        print(f"Q{i}: {faq.question}")
        print(f"A{i}: {faq.answer}\n")
    print("=" * 60)

    # 输出 JSON
    out_dir = Path(config.get("output", {}).get("dir", "./output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    faq_json = out_dir / "faq.json"
    faq_gen.save_faqs_json(faqs, str(faq_json))
    logging.info(f"FAQ JSON 已保存: {faq_json}")


def cmd_schema(args, config):
    """仅生成 Schema"""
    logging.info(f"为 {args.url} 生成 Schema...")

    pages = crawl_sync(config, [args.url])
    if not pages:
        logging.error("爬取失败")
        return

    page = pages[0]
    analyzer = GEOAnalyzer()
    report = analyzer.analyze(page, config)

    faq_gen = GEOFAQGenerator(config)
    faqs = faq_gen.generate_faqs(page, report, config)

    schema_gen = GEOSchemaGenerator(config)
    schema_result = schema_gen.generate_all_schemas(page, faqs, config)

    print("\n" + "=" * 60)
    print(f"生成了 {len(schema_result.schemas)} 个 Schema:\n")
    for name, schema_data in schema_result.schemas.items():
        print(f"--- {name} ---")
        print(json.dumps(json.loads(schema_data), indent=2, ensure_ascii=False))
        print()
    print("=" * 60)

    # 保存
    out_dir = Path(config.get("output", {}).get("dir", "./output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in schema_result.schemas.items():
        path = out_dir / f"{name}.json"
        path.write_text(data, encoding="utf-8")
        logging.info(f"Schema 已保存: {path}")


def cmd_optimize(args, config):
    """完整优化 pipeline: 爬取 → 分析 → LLM 优化 → FAQ → Schema"""
    logging.info(f"完整优化 pipeline: {args.url}")

    # 1. 爬取
    logging.info("Step 1/5: 爬取页面...")
    pages = crawl_sync(config, [args.url])
    if not pages:
        logging.error("爬取失败")
        return
    page = pages[0]

    # 2. 分析
    logging.info("Step 2/5: GEO 就绪度分析...")
    analyzer = GEOAnalyzer()
    report = analyzer.analyze(page, config)
    print("\n" + format_report(report))

    # 3. LLM 内容优化
    logging.info("Step 3/5: LLM 内容优化...")
    content_gen = GEOContentGenerator(config)
    optimized = content_gen.generate_optimized_content(page, report, config)
    if optimized:
        logging.info(f"  生成了 {len(optimized)} 段优化内容")

    # 4. FAQ 生成
    logging.info("Step 4/5: FAQ 生成...")
    faq_gen = GEOFAQGenerator(config)
    faqs = faq_gen.generate_faqs(page, report, config)
    logging.info(f"  生成了 {len(faqs)} 个 FAQ")

    # 5. Schema 生成
    logging.info("Step 5/5: Schema 生成...")
    schema_gen = GEOSchemaGenerator(config)
    schema_result = schema_gen.generate_all_schemas(page, faqs, config)
    logging.info(f"  生成了 {len(schema_result.schemas)} 个 Schema")

    # 输出结果
    out_dir = Path(config.get("output", {}).get("dir", "./output"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # 保存优化内容
    for oc in optimized:
        out_path = out_dir / f"optimized_{oc.language}.html"
        out_path.write_text(oc.optimized_html, encoding="utf-8")
        logging.info(f"优化内容已保存: {out_path}")

    # 保存 FAQ
    faq_path = out_dir / "faq.json"
    faq_gen.save_faqs_json(faqs, str(faq_path))
    logging.info(f"FAQ 已保存: {faq_path}")

    # 保存 Schema
    for name, data in schema_result.schemas.items():
        schema_path = out_dir / f"{name}.json"
        schema_path.write_text(data, encoding="utf-8")

    print(f"\n✅ 优化完成! 输出目录: {out_dir.absolute()}")


def cmd_export(args, config):
    """优化 + 多平台导出"""
    logging.info(f"优化并导出: {args.url}")

    # 先跑完整优化
    pages = crawl_sync(config, [args.url])
    if not pages:
        logging.error("爬取失败")
        return
    page = pages[0]

    analyzer = GEOAnalyzer()
    report = analyzer.analyze(page, config)

    content_gen = GEOContentGenerator(config)
    optimized = content_gen.generate_optimized_content(page, report, config)

    faq_gen = GEOFAQGenerator(config)
    faqs = faq_gen.generate_faqs(page, report, config)

    schema_gen = GEOSchemaGenerator(config)
    schema_result = schema_gen.generate_all_schemas(page, faqs, config)

    # 导出
    logging.info("正在导出到各平台...")
    exporter = GEOExporter(config)
    results = exporter.export_all(optimized, faqs, schema_result.combined)

    print(f"\n✅ 导出完成! 共 {len(results)} 个文件:")
    for r in results:
        print(f"  📄 {r.platform} → {r.filename}")


def cmd_monitor(args, config):
    """引擎引用监控"""
    logging.info(f"监控引擎引用: {args.url}")

    monitor = GEOMonitor(config)
    report = monitor.check_url(args.url)

    print("\n" + "=" * 60)
    print(f"GEO 引用监控报告")
    print(f"URL: {report.url}")
    print(f"检测时间: {report.checked_at}")
    print(f"引擎总数: {report.total_engines}")
    print(f"被引用数: {report.cited_count}")
    print(f"引用率: {report.citation_rate:.1%}")
    print(f"平均排名: {report.avg_position:.1f}")
    print("-" * 60)

    for c in report.citations:
        status = "✅" if c.cited else "❌"
        pos = f"#{c.position}" if c.cited else "N/A"
        print(f"  {status} {c.engine:20s} 排名: {pos:5s}  置信度: {c.confidence:.2f}")
    print("=" * 60)

    # 保存记录
    monitor.save_report(report)


def cmd_report(args, config):
    """生成分析报告"""
    logging.info(f"生成分析报告: {args.url}")

    # 跑一遍完整流程
    pages = crawl_sync(config, [args.url])
    if not pages:
        logging.error("爬取失败")
        return
    page = pages[0]

    analyzer = GEOAnalyzer()
    report = analyzer.analyze(page, config)

    content_gen = GEOContentGenerator(config)
    optimized = content_gen.generate_optimized_content(page, report, config)

    faq_gen = GEOFAQGenerator(config)
    faqs = faq_gen.generate_faqs(page, report, config)

    # 生成报告
    from geo_optimizer.report import GEOReportGenerator
    report_gen = GEOReportGenerator(config)
    report_result = report_gen.generate(page, report, optimized, faqs)

    print("\n" + report_result.summary)

    out_dir = Path(config.get("output", {}).get("dir", "./output"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # 保存 Markdown 报告
    md_path = out_dir / "geo_report.md"
    md_path.write_text(report_result.markdown, encoding="utf-8")
    logging.info(f"Markdown 报告: {md_path}")

    # 保存 HTML 报告
    if report_result.html:
        html_path = out_dir / "geo_report.html"
        html_path.write_text(report_result.html, encoding="utf-8")
        logging.info(f"HTML 报告: {html_path}")

    print(f"\n✅ 报告已保存到: {out_dir.absolute()}")


def cmd_eval(args, config):
    """GEO 多引擎表现评估"""
    from urllib.parse import urlparse
    from geo_optimizer.evaluation.index_checker import AI_BOT_AGENTS
    
    logging.info(f"GEO 多引擎评估: {args.url}")
    
    # 提取域名
    parsed = urlparse(args.url)
    domain = parsed.netloc or parsed.path
    if domain.startswith("www."):
        domain = domain[4:]
    
    # 获取关键词
    keywords = args.keywords.split(",") if args.keywords else []
    
    # 执行评估
    evaluator = GEOEvaluator(domain, keywords)
    report = evaluator.evaluate(keywords, run_index_check=not args.skip_index)
    
    print("\n" + "=" * 70)
    print(f"GEO 多引擎评估报告")
    print(f"域名: {report.domain}")
    print(f"评估时间: {report.evaluated_at}")
    print(f"综合评分: {report.overall_score:.1f}/100 ({report.overall_grade})")
    print("=" * 70)
    
    # 国内引擎
    domestic = [e for e in report.engines if e.category == "domestic"]
    if domestic:
        print("\n【国内 AI 引擎】")
        for e in domestic:
            status = "✅" if e.indexed else "❌"
            print(f"  {status} {e.engine_name:15s} 评分: {e.overall_score:5.1f}  引用格式: {e.citation_format or 'N/A'}")
            if e.issues:
                for issue in e.issues[:2]:
                    print(f"      ⚠️ {issue}")
    
    # 国外引擎
    international = [e for e in report.engines if e.category == "international"]
    if international:
        print("\n【国外 AI 引擎】")
        for e in international:
            status = "✅" if e.indexed else "❌"
            print(f"  {status} {e.engine_name:20s} 评分: {e.overall_score:5.1f}  引用格式: {e.citation_format or 'N/A'}")
            if e.issues:
                for issue in e.issues[:2]:
                    print(f"      ⚠️ {issue}")
    
    # 索引检测摘要
    if report.index_check:
        print("\n【索引状态】")
        https_status = "✅" if report.index_check.https and report.index_check.https.has_https else "❌"
        print(f"  {https_status} HTTPS: {report.index_check.https.cert_issuer or '未配置'}")
        
        robots_status = "✅" if report.index_check.robots and report.index_check.robots.exists else "❌"
        ai_allowed = 0
        if report.index_check.robots and report.index_check.robots.ai_bots_allowed:
            ai_allowed = sum(1 for v in report.index_check.robots.ai_bots_allowed.values() if v)
        print(f"  {robots_status} robots.txt: AI 爬虫允许 {ai_allowed}/{len(AI_BOT_AGENTS)}")
        
        sitemap_status = "✅" if any(s.exists for s in report.index_check.sitemaps) else "❌"
        print(f"  {sitemap_status} sitemap.xml")
    
    # 建议
    if report.recommendations:
        print("\n【改进建议】")
        for i, rec in enumerate(report.recommendations[:5], 1):
            print(f"  {i}. {rec}")
    
    print("\n" + "=" * 70)
    
    # 保存报告
    out_dir = Path(config.get("output", {}).get("dir", "./output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    
    import json
    report_path = out_dir / "geo_eval_report.json"
    report_data = {
        "domain": report.domain,
        "evaluated_at": report.evaluated_at,
        "overall_score": report.overall_score,
        "overall_grade": report.overall_grade,
        "engines": [
            {
                "engine_id": e.engine_id,
                "engine_name": e.engine_name,
                "category": e.category,
                "indexed": e.indexed,
                "overall_score": e.overall_score,
                "citation_format": e.citation_format,
                "issues": e.issues,
                "recommendations": e.recommendations,
            }
            for e in report.engines
        ],
        "recommendations": report.recommendations,
    }
    report_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")
    logging.info(f"评估报告已保存: {report_path}")


def cmd_check(args, config):
    """索引状态检测"""
    from urllib.parse import urlparse
    from geo_optimizer.evaluation.index_checker import AI_BOT_AGENTS
    
    logging.info(f"索引状态检测: {args.url}")
    
    # 提取域名
    parsed = urlparse(args.url)
    domain = parsed.netloc or parsed.path
    if domain.startswith("www."):
        domain = domain[4:]
    
    # 执行检测
    with GEOIndexChecker(domain) as checker:
        result = checker.check_all()
    
    print("\n" + "=" * 60)
    print(f"索引状态检测报告")
    print(f"域名: {result.domain}")
    print(f"检测时间: {result.checked_at}")
    print("=" * 60)
    
    # HTTPS
    print("\n【HTTPS 证书】")
    if result.https:
        status = "✅" if result.https.has_https else "❌"
        print(f"  {status} HTTPS: {result.https.tls_version or 'N/A'}")
        if result.https.cert_issuer:
            print(f"     颁发者: {result.https.cert_issuer}")
        if result.https.days_until_expiry:
            print(f"     剩余天数: {result.https.days_until_expiry}")
        if result.https.issues:
            for issue in result.https.issues:
                print(f"     ⚠️ {issue}")
    else:
        print("  ❌ 未检测到 HTTPS")
    
    # robots.txt
    print("\n【robots.txt】")
    if result.robots and result.robots.exists:
        print("  ✅ robots.txt 存在")
        print(f"     AI 爬虫允许情况:")
        for bot, allowed in result.robots.ai_bots_allowed.items():
            status = "✅" if allowed else "❌"
            bot_name = AI_BOT_AGENTS.get(bot, bot)
            print(f"       {status} {bot}: {bot_name}")
        if result.robots.recommendations:
            print("     建议:")
            for rec in result.robots.recommendations[:3]:
                print(f"       💡 {rec}")
    else:
        print("  ❌ robots.txt 不存在")
    
    # Sitemap
    print("\n【Sitemap】")
    if result.sitemaps:
        for sm in result.sitemaps:
            status = "✅" if sm.exists and sm.valid_xml else "❌"
            print(f"  {status} {sm.url}")
            if sm.exists and sm.valid_xml:
                print(f"     URL 数量: {sm.url_count}")
    else:
        print("  ❌ 未检测到 sitemap.xml")
    
    # Site 查询
    print("\n【搜索引擎收录】")
    for sq in result.site_queries:
        status = "✅" if sq.accessible else "❌"
        est = f"~{sq.estimated_results}" if sq.estimated_results else "N/A"
        print(f"  {status} {sq.engine:10s} 预估收录: {est}")
    
    
    print("\n" + "=" * 60)


def cmd_full(args, config):
    """完整 pipeline: optimize + export + monitor"""
    logging.info("🚀 运行完整 GEO Pipeline")
    logging.info("=" * 50)

    url = args.url

    # Phase 1-3: 优化
    cmd_optimize(argparse.Namespace(url=url), config)

    # Phase 4: 导出
    print("\n" + "=" * 50)
    cmd_export(argparse.Namespace(url=url), config)

    # Phase 5: 监控
    print("\n" + "=" * 50)
    cmd_monitor(argparse.Namespace(url=url), config)

    print("\n🎉 完整 Pipeline 执行完毕!")


def main():
    parser = argparse.ArgumentParser(
        prog="geo-optimizer",
        description="GEO (Generative Engine Optimization) 自动化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志")
    parser.add_argument("-c", "--config", help="配置文件路径")

    sub = parser.add_subparsers(dest="command", help="子命令")

    # analyze
    p = sub.add_parser("analyze", help="爬取页面 + GEO 就绪度分析")
    p.add_argument("url", help="目标 URL")
    p.set_defaults(func=cmd_analyze)

    # optimize
    p = sub.add_parser("optimize", help="完整优化 (爬取→分析→LLM优化→FAQ→Schema)")
    p.add_argument("url", help="目标 URL")
    p.set_defaults(func=cmd_optimize)

    # export
    p = sub.add_parser("export", help="优化 + 多平台导出")
    p.add_argument("url", help="目标 URL")
    p.set_defaults(func=cmd_export)

    # monitor
    p = sub.add_parser("monitor", help="引擎引用监控")
    p.add_argument("url", help="目标 URL")
    p.set_defaults(func=cmd_monitor)

    # report
    p = sub.add_parser("report", help="生成分析报告 (Markdown + HTML)")
    p.add_argument("url", help="目标 URL")
    p.set_defaults(func=cmd_report)

    # faq
    p = sub.add_parser("faq", help="仅生成 FAQ")
    p.add_argument("url", help="目标 URL")
    p.set_defaults(func=cmd_faq)

    # schema
    p = sub.add_parser("schema", help="仅生成 Schema")
    p.add_argument("url", help="目标 URL")
    p.set_defaults(func=cmd_schema)

    # full
    p = sub.add_parser("full", help="完整 Pipeline (optimize + export + monitor)")
    p.add_argument("url", help="目标 URL")
    p.set_defaults(func=cmd_full)

    # eval
    p = sub.add_parser("eval", help="GEO 多引擎表现评估")
    p.add_argument("url", help="目标 URL")
    p.add_argument("-k", "--keywords", help="评估关键词（逗号分隔）")
    p.add_argument("--skip-index", action="store_true", help="跳过索引检测")
    p.set_defaults(func=cmd_eval)

    # check
    p = sub.add_parser("check", help="索引状态检测 (HTTPS/robots/sitemap)")
    p.add_argument("url", help="目标 URL")
    p.set_defaults(func=cmd_check)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    setup_logging(args.verbose)

    config = load_config(args.config)
    args.func(args, config)


if __name__ == "__main__":
    main()
