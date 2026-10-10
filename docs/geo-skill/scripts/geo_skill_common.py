#!/usr/bin/env python3
"""
GEO-Optimizer Skill 公共模块 — 配置解析、工具函数与异常定义。

凭据解析优先级: 显式参数 > 环境变量 (GEO_API_KEY / GEO_BASE_URL) > 技能根目录 config.json。
轮询间隔优先级: 显式参数 > 环境变量 GEO_POLL_INTERVAL > config.json poll_interval > 默认 6 秒。
"""
import functools
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# 智能体/管道环境下 stdout 默认块缓冲，强制行缓冲确保进展实时可见
# （否则所有 print 会摊到进程结束才一次性输出，表现为“持续等待”）
try:
    sys.stdout.reconfigure(line_buffering=True)
except (AttributeError, ValueError, OSError):  # stdout 被替换为非标准对象时忽略
    pass

# 双保险：reconfigure 可能静默失效（stdout 被替换），本模块内每条 print 强制刷新
print = functools.partial(print, flush=True)

# 默认平台地址（未显式指定且无环境变量/config.json 时使用）
DEFAULT_BASE_URL = "http://localhost:5001"

# 各任务类型预计耗时（分钟），提交后提示用户
ESTIMATED_MINUTES = {"eval": 2, "plan": 5}

# 默认轮询间隔（秒），可通过 config.json 的 poll_interval 或环境变量 GEO_POLL_INTERVAL 覆盖
DEFAULT_POLL_INTERVAL = 6


def load_config() -> dict:
    """读取技能根目录下的 config.json（scripts/ 的上级目录），不存在时返回空字典。"""
    for candidate in (
        Path(__file__).resolve().parent.parent / "config.json",
        Path(__file__).resolve().parent / "config.json",
    ):
        if candidate.is_file():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                return {}
    return {}


def resolve_credentials(base_url: Optional[str] = None,
                        api_key: Optional[str] = None) -> tuple:
    """按优先级解析凭据: 显式参数 > 环境变量 > config.json > 默认值。

    Returns:
        (base_url, api_key)，api_key 未解析到时为 None
    """
    cfg = load_config()
    base_url = (base_url
                or os.environ.get("GEO_BASE_URL")
                or cfg.get("base_url")
                or DEFAULT_BASE_URL)
    api_key = (api_key
               or os.environ.get("GEO_API_KEY")
               or cfg.get("api_key"))
    return base_url, api_key


def resolve_poll_interval(explicit: Optional[float] = None) -> float:
    """按优先级解析轮询间隔（秒）: 显式参数 > 环境变量 GEO_POLL_INTERVAL > config.json > 默认 6 秒。

    非法值（非数字/非正数）自动回退到默认值。
    """
    candidates = (explicit,
                  os.environ.get("GEO_POLL_INTERVAL"),
                  load_config().get("poll_interval"))
    for value in candidates:
        if value is None:
            continue
        try:
            interval = float(value)
        except (TypeError, ValueError):
            continue
        if interval > 0:
            return interval
    return DEFAULT_POLL_INTERVAL


def normalize_url(target_url: str) -> str:
    """归一化目标 URL：裸域名自动补全 https:// 前缀。

    支持提示词直接传入的网站写法，如 "www.example.com" → "https://www.example.com"。
    """
    url = (target_url or "").strip()
    if url and "://" not in url:
        url = f"https://{url}"
    return url


def format_log_entry(entry: dict) -> str:
    """格式化一条云端执行日志为中文展示行。"""
    line = f"  [云端日志 {entry.get('time', '')}] {entry.get('message', '')}"
    if entry.get("detail"):
        line += f": {entry['detail']}"
    return line


def client_log(message: str) -> None:
    """打印一条客户端执行日志（带时间戳，智能体控制台实时展示）。"""
    print(f"  [客户端 {datetime.now().strftime('%H:%M:%S')}] {message}")


class GeoSkillError(Exception):
    """GEO-Optimizer API 调用异常。"""

    def __init__(self, status_code: int, error: str = "", message: str = ""):
        self.status_code = status_code
        self.error = error
        self.message = message
        super().__init__(f"[{status_code}] {error}: {message}")
