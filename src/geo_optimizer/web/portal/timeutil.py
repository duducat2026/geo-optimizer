# -*- coding: utf-8 -*-
"""时间工具：数据库统一存 UTC，展示统一转北京时间（UTC+8）。"""
from datetime import datetime, timedelta

UTC_OFFSET = timedelta(hours=8)  # 北京时间


def to_local(dt: datetime | None) -> datetime | None:
    """UTC naive datetime 转北京时间。"""
    if dt is None:
        return None
    return dt + UTC_OFFSET


def fmt_local(dt: datetime | None, pattern: str = "%Y-%m-%d %H:%M") -> str:
    """UTC naive datetime 格式化为北京时间字符串；空值返回空串。"""
    local = to_local(dt)
    return local.strftime(pattern) if local else ""
