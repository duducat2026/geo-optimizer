#!/usr/bin/env python3
"""
config.py — 配置加载器
"""

import os
from pathlib import Path

import yaml

CONFIG_FILENAME = "geo_config.yaml"


def _resolve_config_path() -> str:
    """按优先级查找配置文件: GEO_CONFIG 环境变量 > 当前工作目录 > 项目根目录"""
    env_path = os.environ.get("GEO_CONFIG")
    if env_path:
        return env_path

    cwd_path = Path.cwd() / CONFIG_FILENAME
    if cwd_path.exists():
        return str(cwd_path)

    # 源码运行时回退到仓库根目录 (src/geo_optimizer/ 上两级)
    repo_root = Path(__file__).resolve().parent.parent.parent
    return str(repo_root / CONFIG_FILENAME)


def load_config(path: str | None = None) -> dict:
    """加载 geo_config.yaml，支持环境变量覆盖"""
    if path is None:
        path = _resolve_config_path()

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 环境变量覆盖
    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if api_key and not config.get("llm", {}).get("api_key"):
        config.setdefault("llm", {})["api_key"] = api_key

    return config
