# -*- coding: utf-8 -*-
"""
部署配置加载器

优先级：环境变量 > deployment/settings.py > deployment/settings.example.py
"""
import importlib.util
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    # src/geo_optimizer/web/portal/settings.py -> 上溯 5 级到仓库根
    return Path(__file__).resolve().parents[4]


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(f"geo_deploy_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _load_deploy_module():
    deploy_dir = _repo_root() / "deployment"
    real = deploy_dir / "settings.py"
    example = deploy_dir / "settings.example.py"
    if real.exists():
        return _load_module(real)
    if example.exists():
        return _load_module(example)
    return None


@lru_cache(maxsize=1)
def get_settings() -> dict[str, Any]:
    """返回合并后的配置字典。"""
    mod = _load_deploy_module()

    def val(name: str, default: Any) -> Any:
        return os.environ.get(f"GEO_{name}", getattr(mod, name, default) if mod else default)

    llm_defaults = getattr(mod, "LLM_DEFAULTS", {}) if mod else {}

    return {
        "SECRET_KEY": val("SECRET_KEY", "change-me-to-a-random-secret"),
        "DB_HOST": val("DB_HOST", "localhost"),
        "DB_PORT": int(val("DB_PORT", 3306)),
        "DB_USER": val("DB_USER", "root"),
        "DB_PASSWORD": val("DB_PASSWORD", "change-me-db-password"),
        "DB_NAME": val("DB_NAME", "geo-op"),
        "ADMIN_USERNAME": val("ADMIN_USERNAME", "admin"),
        "ADMIN_PASSWORD": val("ADMIN_PASSWORD", "admin123"),
        "DEFAULT_EVAL_QUOTA": int(val("DEFAULT_EVAL_QUOTA", 10)),
        # GTM 容器 ID：由环境变量 GEO_GTM_CONTAINER 或 deployment/settings.py 配置。
        # 默认占位值 GTM-XXXXXXX 不注入真实埋点；部署方填入自有容器 ID 后全站生效。
        "GTM_CONTAINER": val("GTM_CONTAINER", "GTM-XXXXXXX"),
        "LLM_DEFAULTS": llm_defaults,
    }


def sqlalchemy_uri() -> str:
    """构造 MySQL 连接串（库名含连字符已正确转义）。"""
    s = get_settings()
    return (
        f"mysql+pymysql://{s['DB_USER']}:{s['DB_PASSWORD']}"
        f"@{s['DB_HOST']}:{s['DB_PORT']}/{s['DB_NAME']}?charset=utf8mb4"
    )
