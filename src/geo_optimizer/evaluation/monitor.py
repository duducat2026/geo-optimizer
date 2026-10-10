#!/usr/bin/env python3
"""
geo_monitor.py — 11引擎引用检测 & 双语监控报告
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from geo_optimizer.config import load_config

logger = logging.getLogger(__name__)


@dataclass
class EngineCitation:
    """引擎引用记录"""
    engine: str
    cited: bool               # 是否被引用
    citation_url: str = ""    # 引用链接
    citation_text: str = ""   # 引用内容摘要
    position: int = 0         # 排名位置（1-based）
    confidence: float = 0.0   # 置信度 0-1
    checked_at: str = ""


@dataclass
class MonitorReport:
    """监控报告"""
    url: str
    checked_at: str
    citations: list[EngineCitation]
    total_engines: int
    cited_count: int
    citation_rate: float      # 引用率
    avg_position: float
    changes: list             # 与上次对比的变化


class GEOMonitor:
    """GEO 引擎引用监控"""

    def __init__(self, config: dict):
        self.config = config
        self.output_dir = config.get("output", {}).get("dir", "./output")
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.history_dir = os.path.join(self.output_dir, "monitor_history")
        Path(self.history_dir).mkdir(parents=True, exist_ok=True)

    def check_all(self, url: str, keywords_zh: list[str] = None, keywords_en: list[str] = None) -> MonitorReport:
        """检测所有引擎的引用情况

        注意：真实引擎检测需要API或爬虫，
        当前版本输出检测框架+模拟数据，
        实际接入时替换 _check_engine 方法即可
        """
        all_engines = []

        # 国内引擎
        for eng in self.config.get("engines_cn", []):
            if eng.get("enabled", True):
                all_engines.append(eng)

        # 国外引擎
        for eng in self.config.get("engines_en", []):
            if eng.get("enabled", True):
                all_engines.append(eng)

        citations = []
        for eng in all_engines:
            citation = self._check_engine(eng, url, keywords_zh, keywords_en)
            citations.append(citation)

        cited_count = sum(1 for c in citations if c.cited)
        total = len(citations)
        cited_positions = [c.position for c in citations if c.cited and c.position > 0]
        avg_pos = sum(cited_positions) / len(cited_positions) if cited_positions else 0

        # 对比上次记录
        changes = self._compare_with_history(url, citations)

        report = MonitorReport(
            url=url,
            checked_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            citations=citations,
            total_engines=total,
            cited_count=cited_count,
            citation_rate=round(cited_count / max(total, 1) * 100, 1),
            avg_position=round(avg_pos, 1),
            changes=changes,
        )

        # 保存历史
        self._save_history(url, report)

        return report

    def _check_engine(self, eng: dict, url: str, keywords_zh: list = None, keywords_en: list = None) -> EngineCitation:
        """检测单个引擎的引用

        TODO: 实际接入各引擎 API 或爬虫
        当前返回模拟数据结构，供后续对接
        """
        engine_name = eng["name"]
        focus = eng.get("focus", [])

        # --- 模拟检测结果 ---
        # 实际应调用:
        # - Google: Custom Search API / SERP API
        # - Bing: Bing Web Search API
        # - 百度: 百度搜索爬虫
        # - 其他引擎：对应搜索/查询API

        return EngineCitation(
            engine=engine_name,
            cited=False,       # TODO: 真实检测结果
            citation_url="",
            citation_text="",
            position=0,
            confidence=0.0,
            checked_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

    def _compare_with_history(self, url: str, citations: list[EngineCitation]) -> list:
        """与历史记录对比"""
        history = self._load_history(url)
        if not history:
            return []

        changes = []
        prev_map = {c.engine: c for c in history.citations}

        for curr in citations:
            prev = prev_map.get(curr.engine)
            if prev:
                if prev.cited != curr.cited:
                    changes.append(
                        f"{'🆕' if curr.cited else '⚠️'} {curr.engine}: "
                        f"{'首次被引用' if curr.cited else '不再被引用'}"
                    )
                elif curr.cited and curr.position != prev.position:
                    diff = prev.position - curr.position
                    if diff > 0:
                        changes.append(f"📈 {curr.engine}: 排名上升 {diff} 位 ({prev.position}→{curr.position})")
                    elif diff < 0:
                        changes.append(f"📉 {curr.engine}: 排名下降 {abs(diff)} 位 ({prev.position}→{curr.position})")

        return changes

    def _save_history(self, url: str, report: MonitorReport):
        """保存监控记录"""
        slug = url.replace("https://", "").replace("http://", "").replace("/", "_")
        filename = f"{slug}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        filepath = os.path.join(self.history_dir, filename)

        data = {
            "url": report.url,
            "checked_at": report.checked_at,
            "total_engines": report.total_engines,
            "cited_count": report.cited_count,
            "citation_rate": report.citation_rate,
            "avg_position": report.avg_position,
            "citations": [
                {
                    "engine": c.engine,
                    "cited": c.cited,
                    "position": c.position,
                    "confidence": c.confidence,
                }
                for c in report.citations
            ],
            "changes": report.changes,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_history(self, url: str) -> Optional[MonitorReport]:
        """加载最近一次历史记录"""
        slug = url.replace("https://", "").replace("http://", "").replace("/", "_")
        files = sorted(Path(self.history_dir).glob(f"{slug}_*.json"))
        if not files:
            return None

        with open(files[-1], "r", encoding="utf-8") as f:
            data = json.load(f)

        citations = [EngineCitation(**c) for c in data.get("citations", [])]
        return MonitorReport(
            url=data["url"],
            checked_at=data["checked_at"],
            citations=citations,
            total_engines=data["total_engines"],
            cited_count=data["cited_count"],
            citation_rate=data["citation_rate"],
            avg_position=data["avg_position"],
            changes=data.get("changes", []),
        )


def format_monitor_report(report: MonitorReport) -> str:
    """格式化监控报告为 Markdown"""
    lines = [
        "# GEO 引擎监控报告",
        "",
        f"**检测时间:** {report.checked_at}",
        f"**目标URL:** {report.url}",
        f"**引擎总数:** {report.total_engines}",
        f"**被引用数:** {report.cited_count}",
        f"**引用率:** {report.citation_rate}%",
        f"**平均排名:** {report.avg_position}",
        "",
        "## 引擎详情",
        "",
        "| 引擎 | 被引用 | 排名 | 置信度 |",
        "|------|--------|------|--------|",
    ]

    for c in report.citations:
        icon = "✅" if c.cited else "❌"
        pos = str(c.position) if c.position > 0 else "—"
        conf = f"{c.confidence:.0%}" if c.confidence > 0 else "—"
        lines.append(f"| {c.engine} | {icon} | {pos} | {conf} |")

    if report.changes:
        lines.append("\n## 变化提醒")
        for ch in report.changes:
            lines.append(f"- {ch}")
    else:
        lines.append("\n## 变化提醒")
        lines.append("- 无变化（或与上次无差异）")

    return "\n".join(lines)


# --- 快捷测试 ---
def main():
    config = load_config()
    monitor = GEOMonitor(config)
    report = monitor.check_all(
        url="https://example.com",
        keywords_zh=["空气净化器"],
        keywords_en=["air purifier"],
    )
    print(format_monitor_report(report))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
