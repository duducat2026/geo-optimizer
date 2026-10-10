# -*- coding: utf-8 -*-
"""GEO-Optimizer MCP 服务端单元测试（不依赖网络与运行中的平台）。

覆盖：配置解析、错误映射、工具注册（含 streamable-HTTP 元信息）、
以及无鉴权时工具返回可执行错误文本（不打网络）。
"""
import sys
from pathlib import Path

import anyio
import pytest

# 确保仓库根可导入 mcp_server 包（与 test_api_client.py 同一约定）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_server import config as mcp_config  # noqa: E402
from mcp_server.api_client import GeoApiError, describe_error  # noqa: E402
from mcp_server.server import (  # noqa: E402
    geo_get_usage,
    geo_submit_task,
    mcp,
)

EXPECTED_TOOLS = {
    "geo_submit_task", "geo_list_tasks", "geo_get_task_status",
    "geo_get_task_logs", "geo_get_task_result", "geo_cancel_task",
    "geo_get_usage", "geo_download_report",
}


class FakeCtx:
    """最小伪 Context：工具内仅通过 getattr(ctx, 'headers', None) 读取请求头。"""

    def __init__(self, headers=None):
        self.headers = headers or {}


# ─── 配置解析 ────────────────────────────────────────────────────────
class TestConfig:
    def test_normalize_url_bare_domain(self):
        assert mcp_config.normalize_url("www.aliyun.com") == "https://www.aliyun.com"

    def test_normalize_url_keeps_scheme(self):
        assert mcp_config.normalize_url("http://a.com") == "http://a.com"

    def test_normalize_url_strips_whitespace(self):
        assert mcp_config.normalize_url("  example.com ") == "https://example.com"

    def test_bearer_from_headers_case_insensitive(self):
        assert mcp_config.bearer_from_headers({"Authorization": "Bearer geo_x"}) == "geo_x"
        assert mcp_config.bearer_from_headers({"authorization": "bearer geo_y"}) == "geo_y"

    def test_bearer_from_headers_non_bearer_or_empty(self):
        assert mcp_config.bearer_from_headers({"Authorization": "Basic abc"}) is None
        assert mcp_config.bearer_from_headers({"Authorization": "Bearer "}) is None
        assert mcp_config.bearer_from_headers(None) is None

    def test_transport_defaults(self):
        s = mcp_config.resolve_transport_settings()
        assert s.transport == "streamable-http"
        assert s.host == "127.0.0.1"
        assert s.port == 8000
        assert s.path == "/mcp"
        assert s.endpoint == "http://127.0.0.1:8000/mcp"

    def test_transport_explicit_overrides_and_path_normalization(self):
        s = mcp_config.resolve_transport_settings(host="0.0.0.0", port=9001, path="sse-x")
        assert s.host == "0.0.0.0" and s.port == 9001
        assert s.path == "/sse-x"  # 自动补前导斜杠

    def test_transport_env_override(self, monkeypatch):
        monkeypatch.setenv("GEO_MCP_PORT", "8123")
        monkeypatch.setenv("GEO_MCP_HOST", "127.0.0.2")
        s = mcp_config.resolve_transport_settings()
        assert s.port == 8123 and s.host == "127.0.0.2"

    def test_base_url_env_and_default(self, monkeypatch):
        monkeypatch.delenv("GEO_BASE_URL", raising=False)
        monkeypatch.setattr(mcp_config, "load_config_json", lambda: {})
        assert mcp_config.resolve_base_url() == mcp_config.DEFAULT_BASE_URL
        monkeypatch.setenv("GEO_BASE_URL", "https://geo.example.com/")
        assert mcp_config.resolve_base_url() == "https://geo.example.com"  # 去尾斜杠

    def test_server_api_key_placeholder_ignored(self, monkeypatch):
        monkeypatch.delenv("GEO_API_KEY", raising=False)
        monkeypatch.setattr(mcp_config, "load_config_json", lambda: {"api_key": "<your_key>"})
        assert mcp_config.resolve_server_api_key() is None
        monkeypatch.setenv("GEO_API_KEY", "geo_real")
        assert mcp_config.resolve_server_api_key() == "geo_real"


# ─── 错误映射 ────────────────────────────────────────────────────────
class TestDescribeError:
    def test_missing_token_hint(self):
        msg = describe_error(GeoApiError(401, "missing_token", ""))
        assert "GEO_API_KEY" in msg and "missing_token" in msg

    def test_known_business_codes(self):
        assert "配额" in describe_error(GeoApiError(403, "quota_exceeded", ""))
        assert "并发" in describe_error(GeoApiError(429, "concurrent_limit", ""))
        assert "算力" in describe_error(GeoApiError(503, "llm_unavailable", ""))
        assert "geo_list_tasks" in describe_error(GeoApiError(404, "not_found", ""))

    def test_bare_403_status_hint(self):
        # 网关返回裸 403（无 error 码）时仍有可执行提示
        msg = describe_error(GeoApiError(403, "unknown", ""))
        assert "403" in msg and "GEO_BASE_URL" in msg

    def test_network_and_timeout(self):
        assert "超时" in describe_error(GeoApiError(0, "timeout", "x"))
        assert "无法连接平台" in describe_error(GeoApiError(0, "network", "y"))

    def test_unexpected_error_no_leak(self):
        msg = describe_error(RuntimeError("secret internals"))
        assert "unexpected" in msg and "secret internals" not in msg


# ─── 工具注册（streamable-HTTP 服务端元信息）─────────────────────────
class TestToolRegistration:
    def test_eight_tools_registered(self):
        async def run():
            return await mcp.list_tools()
        # 服务端 MCPServer.list_tools() 直接返回 Tool 列表
        tools = anyio.run(run)
        names = {t.name for t in tools}
        assert names == EXPECTED_TOOLS

    def test_annotations_and_schema(self):
        async def run():
            return await mcp.list_tools()
        tools = {t.name: t for t in anyio.run(run)}

        submit = tools["geo_submit_task"]
        assert submit.annotations.read_only_hint is False
        assert submit.input_schema["required"] == ["target_url"]
        # task_type 默认 plan
        assert submit.input_schema["properties"]["task_type"]["default"] == "plan"

        assert tools["geo_cancel_task"].annotations.destructive_hint is True
        assert tools["geo_get_usage"].annotations.read_only_hint is True
        assert tools["geo_download_report"].input_schema["required"] == ["task_id", "save_path"]


# ─── 工具行为：无鉴权时返回可执行错误（不打网络）─────────────────────
class TestToolNoAuth:
    @pytest.fixture(autouse=True)
    def _no_credentials(self, monkeypatch):
        """清空凭据来源，确保 _resolve_api_key 返回 None。"""
        monkeypatch.delenv("GEO_API_KEY", raising=False)
        monkeypatch.setattr(mcp_config, "load_config_json", lambda: {})

    def test_usage_without_key_returns_missing_token(self):
        text = anyio.run(lambda: geo_get_usage(ctx=FakeCtx(), response_format="json"))
        assert "missing_token" in text and "GEO_API_KEY" in text

    def test_submit_without_key_returns_missing_token(self):
        text = anyio.run(lambda: geo_submit_task(
            ctx=FakeCtx(), target_url="www.aliyun.com", task_type="plan"))
        assert "missing_token" in text
