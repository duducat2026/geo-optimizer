# -*- coding: utf-8 -*-
"""GEO-Optimizer MCP 服务端配置解析。

两类配置：

1. 平台凭据（访问 GEO 开放 API 用）
   - base_url 优先级: 显式参数 > 环境变量 GEO_BASE_URL > config.json > 默认 http://localhost:5000
   - api_key  优先级: 请求头 Authorization: Bearer > 显式参数 > 环境变量 GEO_API_KEY > config.json

2. MCP 传输参数（streamable-HTTP 模式）
   - host    优先级: 命令行 > 环境变量 GEO_MCP_HOST    > 默认 127.0.0.1
   - port    优先级: 命令行 > 环境变量 GEO_MCP_PORT    > 默认 8000
   - path    优先级: 命令行 > 环境变量 GEO_MCP_PATH    > 默认 /mcp

环境变量名与 docs/geo-skill 技能保持一致（GEO_API_KEY / GEO_BASE_URL），
并会顺带读取技能目录下的 config.json，方便复用同一份凭据。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ─── 默认值 ──────────────────────────────────────────────────────────
# 平台默认地址：与 deployment/start.sh 的 GEO_PORT 默认值(5000)保持一致
DEFAULT_BASE_URL = "http://localhost:5000"

# streamable-HTTP 传输默认值。host 默认 127.0.0.1（而非 0.0.0.0），
# 遵循 MCP 安全最佳实践：本地服务绑定回环地址可降低 DNS rebinding 风险。
DEFAULT_MCP_HOST = "127.0.0.1"
DEFAULT_MCP_PORT = 8000
DEFAULT_MCP_PATH = "/mcp"
DEFAULT_TRANSPORT = "streamable-http"

# DNS rebinding 防护默认放行的 Host/Origin（回环地址）。当经 Nginx 反代暴露公网
# 域名时，需用 GEO_MCP_ALLOWED_HOSTS / GEO_MCP_ALLOWED_ORIGINS 追加该域名，
# 否则 SDK 会因 Host 头非回环而返回 421 Invalid Host header（见 resolve_allowed_*）。
DEFAULT_ALLOWED_HOSTS = ("127.0.0.1:*", "localhost:*", "[::1]:*")
DEFAULT_ALLOWED_ORIGINS = ("http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*")

# 各任务类型预计耗时（分钟），提交后回显给调用方
ESTIMATED_MINUTES = {"eval": 2, "plan": 5}

# config.json 候选路径（按顺序查找第一个存在的文件）
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
_CONFIG_CANDIDATES = (
    _HERE / "config.json",
    _REPO_ROOT / "config.json",
    _REPO_ROOT / "docs" / "geo-skill" / "config.json",
)


def load_config_json() -> dict:
    """读取 config.json（本目录 / 仓库根 / 技能目录），均不存在时返回空字典。"""
    for candidate in _CONFIG_CANDIDATES:
        if candidate.is_file():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except (ValueError, OSError):
                return {}
    return {}


def normalize_url(target_url: str) -> str:
    """归一化目标 URL：裸域名自动补全 https:// 前缀。

    例如 "www.aliyun.com" → "https://www.aliyun.com"；已带协议的原样返回。
    """
    url = (target_url or "").strip()
    if url and "://" not in url:
        url = f"https://{url}"
    return url


def resolve_base_url(explicit: Optional[str] = None) -> str:
    """解析平台 base_url：显式参数 > GEO_BASE_URL > config.json > 默认值。"""
    cfg = load_config_json()
    return (explicit
            or os.environ.get("GEO_BASE_URL")
            or cfg.get("base_url")
            or DEFAULT_BASE_URL).rstrip("/")


def resolve_server_api_key(explicit: Optional[str] = None) -> Optional[str]:
    """解析服务端默认 api_key：显式参数 > GEO_API_KEY > config.json。

    未配置时返回 None —— 此时仍可由每个 MCP 请求通过
    Authorization 头携带自己的 key（多客户端场景）。
    """
    cfg = load_config_json()
    key = explicit or os.environ.get("GEO_API_KEY") or cfg.get("api_key")
    if key and not str(key).startswith("<"):
        return str(key)
    return None


def bearer_from_headers(headers: Optional[dict]) -> Optional[str]:
    """从请求头中提取 Bearer Token（用于按请求转发调用方自带的 API Key）。

    headers 键大小写不敏感；仅在形如 "Bearer geo_xxx" 时返回 token。
    """
    if not headers:
        return None
    # 统一成小写键查找，兼容不同大小写的 Authorization
    lookup = {(k or "").lower(): v for k, v in dict(headers).items()}
    raw = lookup.get("authorization") or ""
    raw = raw.strip()
    if raw.lower().startswith("bearer "):
        token = raw[7:].strip()
        return token or None
    return None


@dataclass(frozen=True)
class TransportSettings:
    """MCP 传输层配置（streamable-HTTP）。"""

    transport: str = DEFAULT_TRANSPORT
    host: str = DEFAULT_MCP_HOST
    port: int = DEFAULT_MCP_PORT
    path: str = DEFAULT_MCP_PATH

    @property
    def endpoint(self) -> str:
        """完整访问端点，如 http://127.0.0.1:8000/mcp。"""
        return f"http://{self.host}:{self.port}{self.path}"


def _env_int(name: str, default: int) -> int:
    """读取整型环境变量，非法值回退默认。"""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def resolve_transport_settings(
    host: Optional[str] = None,
    port: Optional[int] = None,
    path: Optional[str] = None,
    transport: Optional[str] = None,
) -> TransportSettings:
    """解析传输配置：显式参数 > 环境变量 > 默认值。

    显式参数一般来自命令行；未提供时读取 GEO_MCP_HOST/PORT/PATH。
    """
    resolved_host = host or os.environ.get("GEO_MCP_HOST") or DEFAULT_MCP_HOST
    resolved_port = port or _env_int("GEO_MCP_PORT", DEFAULT_MCP_PORT)
    resolved_path = path or os.environ.get("GEO_MCP_PATH") or DEFAULT_MCP_PATH
    resolved_transport = (transport
                          or os.environ.get("GEO_MCP_TRANSPORT")
                          or DEFAULT_TRANSPORT)
    # path 必须以 / 开头
    if not resolved_path.startswith("/"):
        resolved_path = "/" + resolved_path
    return TransportSettings(
        transport=resolved_transport,
        host=resolved_host,
        port=resolved_port,
        path=resolved_path,
    )


def _env_list(name: str) -> list[str]:
    """读取逗号分隔的环境变量为去空白列表；未设置时返回空列表。"""
    raw = os.environ.get(name)
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def resolve_allowed_hosts() -> list[str]:
    """streamable-HTTP DNS rebinding 防护放行的 Host 列表。

    环境变量 GEO_MCP_ALLOWED_HOSTS（逗号分隔，如反代公网域名
    ``geo.tool.example.com,geo.tool.example.com:*``）会追加到默认回环白名单之前；
    去重并保留顺序。未设置时行为与 SDK 默认（仅回环）一致。
    """
    return list(dict.fromkeys(
        [*_env_list("GEO_MCP_ALLOWED_HOSTS"), *DEFAULT_ALLOWED_HOSTS]))


def resolve_allowed_origins() -> list[str]:
    """streamable-HTTP DNS rebinding 防护放行的 Origin 列表。

    环境变量 GEO_MCP_ALLOWED_ORIGINS（逗号分隔，如 ``https://geo.tool.example.com``）
    追加到默认回环白名单之前；去重并保留顺序。Origin 头缺失时 SDK 一律放行，
    故非浏览器型 MCP 客户端通常无需额外配置。
    """
    return list(dict.fromkeys(
        [*_env_list("GEO_MCP_ALLOWED_ORIGINS"), *DEFAULT_ALLOWED_ORIGINS]))
