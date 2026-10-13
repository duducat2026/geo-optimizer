# -*- coding: utf-8 -*-
"""将任务双语产物打包为可下载 ZIP（包内按 zh/ 与 en/ 分语言归档）。"""
import logging
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_BJT = timezone(timedelta(hours=8))


def download_filename(target_url: str, suffix: str = ".zip") -> str:
    """生成下载文件名：评估网站域名 + 导出时间戳（北京时间）。

    例如: example.com_20260729_143022.zip
    """
    domain = urlparse(target_url).netloc or "site"
    # 去掉端口号（如 localhost:5001 → localhost_5001）
    domain = domain.replace(":", "_")
    ts = datetime.now(_BJT).strftime("%Y%m%d_%H%M%S")
    return f"{domain}_{ts}{suffix}"


def bundle_task(task_id: str, artifact_dir: Path, target_url: str = "") -> Optional[str]:
    """把 artifact_dir 下的所有产物（不含 zip 自身）按双语布局打成 zip。

    磁盘目录保持扁平，仅归档名重排：报告/方案条目/FAQ/Schema 各出中英两份
    （见 packaging.layout），并在包根生成双语 README 索引。
    """
    from geo_optimizer.web.portal.packaging import layout

    artifact_dir = Path(artifact_dir)
    has_files = any(
        p.is_file() and p.suffix.lower() != ".zip" for p in artifact_dir.rglob("*")
    )
    if not has_files:
        return None

    zip_path = artifact_dir / f"geo_plan_{task_id}.zip"
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            stats = layout.pack_artifact_dir(zf, artifact_dir)
            zf.writestr("README.md",
                        layout.readme_text(stats, target_url).encode("utf-8"))
        return str(zip_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("打包失败: %s", exc)
        return None
