# -*- coding: utf-8 -*-
"""产出物生成：sitemap/robots 规则即时生成；文章/FAQ 等由 LLM 结合站点实际内容生成。"""
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from urllib.parse import urlparse

from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models import (
    SOURCE_LLM,
    SOURCE_RULE,
    SOURCE_TEMPLATE,
    PlanArtifact,
)
from geo_optimizer.web.portal.planitems.generator import _is_connection_error, _make_client

logger = logging.getLogger(__name__)

# 产出物（多平台内容/FAQ 等）的 LLM 内容生成并发数（各产出物相互独立）
_ARTIFACT_MAX_WORKERS = 5

AI_BOTS = ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended",
           "Bingbot", "Baiduspider", "Bytespider")

_PROMPT = """你是资深 GEO（生成式引擎优化）内容专家。请根据下面网站的实际内容完成任务。

任务：{instruction}

网站实际内容：
- URL: {url}
- 标题: {title}
- 描述: {meta_desc}
- 主要标题结构: {headings}
- 正文摘录: {text}

要求：内容必须紧扣该网站实际业务，可直接使用；只输出成品内容本身，不要任何解释。"""


def generate(spec: dict, target_url: str, snapshot: dict, config: dict) -> tuple[str, str]:
    """按规格生成产出物内容，返回 (content, source)。"""
    content, source, _conn_err = _generate_with(
        _make_client(config), spec, target_url, snapshot)
    return content, source


def _generate_with(client_model: tuple, spec: dict, target_url: str,
                   snapshot: dict) -> tuple[str, str, bool]:
    """用已构造的客户端生成，返回 (content, source, 是否连接类错误)。"""
    if spec["mode"] == "rule":
        return _rule_generate(spec["kind"], target_url, snapshot), SOURCE_RULE, False
    client, model = client_model
    if client is not None:
        try:
            return _llm_generate(client, model, spec, target_url, snapshot), SOURCE_LLM, False
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM 生成产出物 %s 失败，回退骨架: %s", spec["kind"], exc)
            if _is_connection_error(exc):
                return _skeleton(spec, target_url, snapshot), SOURCE_TEMPLATE, True
    return _skeleton(spec, target_url, snapshot), SOURCE_TEMPLATE, False


def upsert(item, spec: dict, content: str, source: str) -> PlanArtifact:
    """按 (item, kind) 覆盖式保存产出物。"""
    artifact = PlanArtifact.query.filter_by(item_id=item.id, kind=spec["kind"]).first()
    if artifact is None:
        artifact = PlanArtifact(item_id=item.id, task_id=item.task_id,
                                user_id=item.user_id, kind=spec["kind"],
                                filename=spec["filename"])
        db.session.add(artifact)
    artifact.content = content
    artifact.source = source
    db.session.commit()
    return artifact


def auto_generate_rules(items, target_url: str, snapshot: dict) -> int:
    """任务流水线中自动生成规则类产出物（sitemap/robots），返回生成数。"""
    total, _llm = auto_generate_all(items, target_url, snapshot, None)
    return total


def auto_generate_all(items, target_url: str, snapshot: dict, config,
                      on_done=None) -> tuple[int, int]:
    """首批全量生成产出物：规则类即时生成，config 非空时 LLM 类也一并生成。

    各产出物的内容生成相互独立，以最多 _ARTIFACT_MAX_WORKERS 并发调用 LLM（纯网络），
    再在主线程按序落库与上报进度（SQLAlchemy session / on_done 回调非线程安全）。
    返回 (总生成数, llm 生成数)；on_done(filename, source) 用于逐个上报进度。
    """
    from geo_optimizer.web.portal.planitems.artifact_catalog import specs_for

    # 共享一次客户端；连接类错误后置位标志，剩余 LLM 产出物直接骨架避免逐个等待超时
    client_model = _make_client(config or {}) if config is not None else (None, "")

    # 收集待生成的 (item, spec)，LLM 类在 config 为空时跳过
    work = [(item, spec) for item in items for spec in specs_for(item.code)
            if not (spec["mode"] != "rule" and config is None)]

    conn_failed = threading.Event()

    def _gen(unit):
        item, spec = unit
        # 已检测到连接失败时，剩余 LLM 产出物直接骨架，避免继续等待超时
        if spec["mode"] != "rule" and conn_failed.is_set():
            return unit, _skeleton(spec, target_url, snapshot), SOURCE_TEMPLATE, None
        try:
            content, source, conn_err = _generate_with(
                client_model, spec, target_url, snapshot)
            if conn_err:
                conn_failed.set()
            return unit, content, source, None
        except Exception as exc:  # noqa: BLE001
            return unit, None, None, exc

    total = llm_count = 0
    with ThreadPoolExecutor(max_workers=_ARTIFACT_MAX_WORKERS) as executor:
        for (item, spec), content, source, exc in executor.map(_gen, work):
            if exc is not None:
                logger.warning("产出物 %s 生成失败: %s", spec["kind"], exc)
                continue
            upsert(item, spec, content, source)
            total += 1
            if source == SOURCE_LLM:
                llm_count += 1
            if on_done:
                on_done(spec["filename"], source)
    return total, llm_count


# ---------- 规则生成 ----------

def _rule_generate(kind: str, target_url: str, snapshot: dict) -> str:
    if kind == "sitemap_xml":
        return build_sitemap(target_url, snapshot.get("links") or [])
    if kind == "robots_txt":
        return build_robots(target_url)
    raise ValueError(f"unknown rule artifact: {kind}")


def build_sitemap(target_url: str, links: list[str]) -> str:
    """基于首页 + 实际爬取的同域链接生成 sitemap.xml。"""
    host = urlparse(target_url).netloc
    urls, seen = [], set()
    for u in [target_url] + list(links):
        p = urlparse(u)
        if p.scheme not in ("http", "https") or p.netloc != host:
            continue
        clean = f"{p.scheme}://{p.netloc}{p.path or '/'}"
        if clean not in seen:
            seen.add(clean)
            urls.append(clean)
    today = date.today().isoformat()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for i, u in enumerate(urls[:500]):
        prio = "1.0" if i == 0 else "0.8"
        lines += ["  <url>", f"    <loc>{u}</loc>", f"    <lastmod>{today}</lastmod>",
                  f"    <priority>{prio}</priority>", "  </url>"]
    lines.append("</urlset>")
    return "\n".join(lines)


def build_robots(target_url: str) -> str:
    """生成放行主流 AI 爬虫并声明 Sitemap 的 robots.txt。"""
    p = urlparse(target_url)
    base = f"{p.scheme}://{p.netloc}"
    lines = ["User-agent: *", "Allow: /", ""]
    for bot in AI_BOTS:
        lines += [f"User-agent: {bot}", "Allow: /", ""]
    lines.append(f"Sitemap: {base}/sitemap.xml")
    return "\n".join(lines)


# ---------- LLM 生成 ----------

def _build_site_ctx(target_url: str, snapshot: dict) -> dict:
    headings = snapshot.get("headings") or []
    return {
        "url": snapshot.get("url") or target_url,
        "title": snapshot.get("title") or "-",
        "meta_desc": snapshot.get("meta_desc") or "-",
        "headings": " | ".join(f"H{lvl}:{txt}" for lvl, txt in headings[:15]) or "-",
        "text": (snapshot.get("text") or "")[:3000] or "-",
    }


def _llm_generate(client, model: str, spec: dict, target_url: str, snapshot: dict) -> str:
    prompt = _PROMPT.format(instruction=spec["instruction"],
                            **_build_site_ctx(target_url, snapshot))
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
        max_tokens=2400,
    )
    content = (resp.choices[0].message.content or "").strip()
    content = re.sub(r"^```(?:\w+)?\s*|\s*```$", "", content)
    if not content.strip():
        raise ValueError("empty LLM response")
    return content.strip()


def _skeleton(spec: dict, target_url: str, snapshot: dict) -> str:
    """LLM 不可用时的骨架模板（提示用户补全）。"""
    title = snapshot.get("title") or target_url
    return "\n".join([
        f"# {spec['title']['zh']} / {spec['title']['en']}",
        "",
        f"**站点 / Site:** {target_url}（{title}）",
        "",
        "> LLM 暂不可用，以下为待补全骨架。请在系统配置中填写 API Key 后重新生成。",
        "> LLM unavailable; skeleton only. Configure the API key and regenerate.",
        "",
        f"任务要求 / Task: {spec.get('instruction', '-')}",
    ])
