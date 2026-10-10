# -*- coding: utf-8 -*-
"""将任务双语产物打包为可下载 ZIP。"""
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


def bundle_task(task_id: str, artifact_dir: Path) -> Optional[str]:
    """把 artifact_dir 下的所有产物（不含 zip 自身）打成 zip，返回 zip 路径。"""
    artifact_dir = Path(artifact_dir)
    files = [
        p for p in artifact_dir.rglob("*")
        if p.is_file() and p.suffix.lower() != ".zip"
    ]
    if not files:
        return None

    zip_path = artifact_dir / f"geo_plan_{task_id}.zip"
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.write(f, arcname=f.relative_to(artifact_dir).as_posix())
        return str(zip_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("打包失败: %s", exc)
        return None
