# -*- coding: utf-8 -*-
"""页面快照持久化：爬取后落盘站点实际内容，供后续按需生成具体产出物。"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SNAPSHOT_NAME = "page_snapshot.json"

# 控制快照体积：正文摘录/链接数上限
_TEXT_LIMIT = 6000
_LINK_LIMIT = 300


def save_snapshot(artifact_dir: str | Path, page) -> None:
    """将 CrawledPage 关键内容写入产物目录（失败仅告警，不影响主流程）。"""
    data = {
        "url": page.url,
        "title": page.title,
        "language": page.language,
        "meta_desc": page.meta_desc,
        "meta_keywords": page.meta_keywords,
        "headings": [[lvl, txt] for lvl, txt in (page.headings or [])],
        "links": (page.links or [])[:_LINK_LIMIT],
        "word_count": page.word_count,
        "text": (page.text or "")[:_TEXT_LIMIT],
    }
    try:
        path = Path(artifact_dir) / SNAPSHOT_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        logger.warning("页面快照写入失败: %s", exc)


def load_snapshot(artifact_dir: str | Path | None) -> dict:
    """读取快照；不存在/损坏时返回空字典。"""
    if not artifact_dir:
        return {}
    path = Path(artifact_dir) / SNAPSHOT_NAME
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
