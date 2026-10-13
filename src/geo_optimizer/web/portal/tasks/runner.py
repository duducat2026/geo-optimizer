# -*- coding: utf-8 -*-
"""后台线程任务执行器：爬取 -> 分析 -> 体检 -> (方案生成) -> 打包。

含队列调度器：当全局并发槽位空出时自动启动排队任务。
"""
import logging
import threading
import time
from pathlib import Path

from geo_optimizer.web.portal.tasks import service
from geo_optimizer.web.portal.tasks.config_builder import build_config
from geo_optimizer.web.portal.tasks.service import TaskCancelledError

logger = logging.getLogger(__name__)

# 队列调度器检查间隔（秒）
QUEUE_CHECK_INTERVAL = 3


def start(app, task_id: str, target_url: str, task_type: str) -> None:
    """启动后台线程执行任务。"""
    thread = threading.Thread(
        target=_run, args=(app, task_id, target_url, task_type), daemon=True
    )
    thread.start()


def start_queue_dispatcher(app) -> None:
    """启动队列调度守护线程：当并发槽位空出时自动启动排队任务。"""
    thread = threading.Thread(target=_dispatcher_loop, args=(app,), daemon=True)
    thread.start()


def _dispatcher_loop(app) -> None:
    """定期检查排队任务并启动。"""
    while True:
        time.sleep(QUEUE_CHECK_INTERVAL)
        try:
            with app.app_context():
                _dispatch_queued(app)
        except Exception:  # noqa: BLE001
            logger.debug("Queue dispatcher error", exc_info=True)


def _dispatch_queued(app) -> None:
    """将排队任务提升到并发槽位中运行。"""
    running = service.global_running_count()
    if running >= service.MAX_GLOBAL_CONCURRENT:
        return
    slots = service.MAX_GLOBAL_CONCURRENT - running
    queued = service.queued_tasks()
    for task in queued[:slots]:
        # 更新状态为 pending，然后启动线程
        task.status = "pending"
        task.progress = 0
        from geo_optimizer.web.portal.extensions import db
        db.session.commit()
        service.add_log(task.id, "log_dequeued")
        start(app, task.id, task.target_url, task.type)


def _run(app, task_id: str, target_url: str, task_type: str) -> None:
    with app.app_context():
        try:
            _pipeline(task_id, target_url, task_type)
        except TaskCancelledError:
            logger.info("任务 %s 已被用户取消", task_id)
            service.mark_cancelled(task_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("任务 %s 执行失败", task_id)
            service.mark_failed(task_id, str(exc))
            # 任务失败归还预扣配额
            task = _get_task(task_id)
            if task:
                service.refund_quota(task.user_id)


def _pipeline(task_id: str, target_url: str, task_type: str) -> None:
    from geo_optimizer.web.portal.models import TYPE_PLAN

    task = _get_task(task_id)
    user_id = task.user_id if task else None
    artifact_dir = service.artifact_dir_for(task_id)
    config = build_config(target_url, str(artifact_dir), user_id=user_id)

    # 1. 爬取（计时供体检展示）
    service.check_cancelled(task_id)
    service.update_progress(task_id, 10, "crawling")
    from geo_optimizer.crawler import crawl_sync

    t0 = time.monotonic()
    pages = crawl_sync(config, [target_url])
    crawl_ms = int((time.monotonic() - t0) * 1000)
    if not pages:
        raise RuntimeError(f"Failed to crawl {target_url}")
    page = pages[0]
    service.add_log(task_id, "log_crawl_done", detail=f"{crawl_ms}ms")
    service.add_log(
        task_id, "log_page_meta",
        detail=(f"title={(page.title or '-')[:60]} | words={page.word_count} "
                f"| links={len(page.links)} | images={len(page.images)}"),
    )
    # 落盘页面快照，供后续按需生成具体产出物（sitemap/文章/FAQ 等）
    from geo_optimizer.web.portal.tasks.snapshot import save_snapshot

    save_snapshot(artifact_dir, page)

    # 2. 分析（规则打分，无需 LLM）+ 页面技术体检
    service.check_cancelled(task_id)
    service.update_progress(task_id, 40, "analyzing")
    from geo_optimizer.analyzer import GEOAnalyzer
    from geo_optimizer.page_audit import audit_page

    analysis = GEOAnalyzer().analyze(page, config)
    result = _serialize_analysis(page, analysis)
    result["page_audit"] = audit_page(page, crawl_ms, analysis.overall_score)
    service.add_log(task_id, "log_analyze_done",
                    detail=f"score={analysis.overall_score:.1f}")
    service.add_log(task_id, "log_engine_scores",
                    detail=", ".join(f"{s.engine}={s.score:.0f}"
                                     for s in analysis.engine_scores))
    audit = result["page_audit"]
    service.add_log(task_id, "log_audit_done",
                    detail=(f"issues={len(audit.get('issues', []))}, "
                            f"strengths={len(audit.get('strengths', []))}"))

    # 写中英两份分析报告（含体检与分引擎小节）+ 两份 PDF
    # eval/plan 共用：补充中间进度点，避免仅评估任务在 40% 后长时间静默
    service.check_cancelled(task_id)
    service.update_progress(task_id, 55, "generating_report")
    from geo_optimizer.web.portal.packaging.layout import report_names
    from geo_optimizer.web.portal.tasks import report_builder
    from geo_optimizer.web.portal.tasks.pdf_report import generate_pdf

    for lang in ("zh", "en"):
        md_name, pdf_name = report_names(lang)
        report_md = report_builder.build_markdown(result, lang=lang)
        (artifact_dir / md_name).write_text(report_md, encoding="utf-8")
        service.add_log(task_id, "log_report_written", detail=md_name)
        if generate_pdf(report_md, artifact_dir / pdf_name):
            service.add_log(task_id, "log_report_written", detail=pdf_name)

    # 3. 方案生成（仅 plan 类型；依赖 LLM）
    if task_type == TYPE_PLAN:
        service.check_cancelled(task_id)
        service.update_progress(task_id, 60, "generating_plan")
        _generate_plan(task_id, page, config, artifact_dir, result)

        # 3.5 LLM 个性化改进方案条目（失败回退内置模板）
        service.check_cancelled(task_id)
        service.update_progress(task_id, 75, "generating_items")
        _generate_plan_items(task_id, config, artifact_dir, result)

    # 4. 打包 + 完成
    service.check_cancelled(task_id)
    service.update_progress(task_id, 90, "packaging")
    from geo_optimizer.web.portal.packaging.bundler import bundle_task

    zip_path = bundle_task(task_id, artifact_dir, target_url)
    result["zip_available"] = bool(zip_path)
    if zip_path:
        try:
            size_kb = Path(zip_path).stat().st_size // 1024
            service.add_log(task_id, "log_zip_done",
                            detail=f"{Path(zip_path).name} ({size_kb} KB)")
        except OSError:
            service.add_log(task_id, "log_zip_done")

    task = _get_task(task_id)
    if task_type == TYPE_PLAN and zip_path:
        _record_plan(task, zip_path, result.get("overall_score", 0.0))

    service.mark_completed(task_id, result, result.get("overall_score", 0.0), str(artifact_dir))


def _generate_plan(task_id, page, config, artifact_dir, result) -> None:
    """调用双语生成链路并落盘产物。"""
    from geo_optimizer.web.authority_builder import AuthorityBuilder
    from geo_optimizer.web.content_enhancer import ContentEnhancer
    from geo_optimizer.web.faq_generator import FAQGenerator
    from geo_optimizer.web.multi_platform_export import MultiPlatformExporter
    from geo_optimizer.web.schema_generator import SchemaGenerator

    try:
        faqs = FAQGenerator(config).generate(page)
        service.add_log(task_id, "log_faq_done", detail=str(len(faqs)))
    except Exception as exc:  # noqa: BLE001
        logger.warning("FAQ 生成失败: %s", exc)
        service.add_log(task_id, "log_faq_failed", detail=str(exc)[:200], level="warn")
        faqs = []

    try:
        from geo_optimizer.web.portal.packaging.layout import schema_name

        gen = SchemaGenerator()
        for lang in ("zh", "en"):
            schemas = gen.generate(page, faqs, config, lang=lang)
            if not schemas:
                continue
            (artifact_dir / schema_name(lang)).write_text(
                gen.render_jsonld(schemas), encoding="utf-8"
            )
        service.add_log(task_id, "log_schema_done", detail="zh + en JSON-LD")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Schema 生成失败: %s", exc)
        service.add_log(task_id, "log_schema_failed", detail=str(exc)[:200], level="warn")

    try:
        profile = AuthorityBuilder().build(page, faqs, config)
        service.add_log(task_id, "log_authority_done")
    except Exception as exc:  # noqa: BLE001
        logger.warning("权威画像失败: %s", exc)
        service.add_log(task_id, "log_authority_failed", detail=str(exc)[:200], level="warn")
        profile = None

    try:
        ContentEnhancer(config).enhance(page, faqs)
        service.add_log(task_id, "log_enhance_done")
    except Exception as exc:  # noqa: BLE001
        logger.warning("内容增强失败: %s", exc)
        service.add_log(task_id, "log_enhance_failed", detail=str(exc)[:200], level="warn")

    try:
        exports = MultiPlatformExporter(config).export_all(page, faqs, profile)
        result["platforms"] = [e.platform for e in exports]
        service.add_log(task_id, "log_export_done",
                        detail=", ".join(result["platforms"]))
    except Exception as exc:  # noqa: BLE001
        logger.warning("多平台导出失败: %s", exc)
        service.add_log(task_id, "log_export_failed", detail=str(exc)[:200], level="warn")

    result["faq_count"] = len(faqs)


def _generate_plan_items(task_id, config, artifact_dir, result) -> None:
    """生成可编辑改进方案条目并落库/落盘，随后首批全量生成具体产出物。"""
    from geo_optimizer.web.portal.planitems import generator

    try:
        items = generator.generate_for_task(task_id, config, result)
        generator.write_to_dir(items, artifact_dir / "plan_items")
        result["plan_items"] = len(items)
        llm_count = sum(1 for i in items if getattr(i, "source", "") == "llm")
        service.add_log(task_id, "log_items_done",
                        detail=(f"{len(items)} (llm={llm_count}, "
                                f"template={len(items) - llm_count})"))
        # 首批自动生成全部具体产出物（sitemap/robots 规则生成，文章/FAQ 等 LLM 生成）
        service.update_progress(task_id, 82, "generating_artifacts")
        from geo_optimizer.web.portal.planitems import artifact_generator
        from geo_optimizer.web.portal.tasks.snapshot import load_snapshot

        def _on_done(filename, source):
            service.add_log(task_id, "log_artifact_one",
                            detail=f"{filename} ({source})")

        total, art_llm = artifact_generator.auto_generate_all(
            items, result.get("url", ""), load_snapshot(artifact_dir),
            config, on_done=_on_done)
        if total:
            service.add_log(task_id, "log_artifacts_done",
                            detail=f"{total} (llm={art_llm})")
    except Exception as exc:  # noqa: BLE001
        logger.warning("改进方案条目生成失败: %s", exc)
        service.add_log(task_id, "log_items_failed", detail=str(exc)[:200],
                        level="warn")


def _serialize_analysis(page, analysis) -> dict:
    return {
        "url": page.url,
        "title": page.title,
        "language": analysis.language,
        "overall_score": analysis.overall_score,
        "engine_scores": [
            {
                "engine": s.engine,
                "vendor": s.vendor,
                "score": s.score,
                "breakdown": s.breakdown,
                "suggestions": s.suggestions,
                "focus": list(getattr(s, "focus", []) or []),
            }
            for s in analysis.engine_scores
        ],
        "strengths": analysis.strengths,
        "weaknesses": analysis.weaknesses,
    }


def _record_plan(task, zip_path, score) -> None:
    from geo_optimizer.web.portal.extensions import db
    from geo_optimizer.web.portal.models import GeoPlan

    plan = GeoPlan(
        task_id=task.id,
        user_id=task.user_id,
        target_url=task.target_url,
        summary=f"score={score}",
        zip_path=str(zip_path),
    )
    db.session.add(plan)
    db.session.commit()


def _get_task(task_id: str):
    from geo_optimizer.web.portal.extensions import db
    from geo_optimizer.web.portal.models import EvalTask

    return db.session.get(EvalTask, task_id)
