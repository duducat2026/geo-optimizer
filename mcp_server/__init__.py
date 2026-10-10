# -*- coding: utf-8 -*-
"""GEO-Optimizer MCP 服务端包（streamable-HTTP 模式）。

把 GEO-Optimizer 平台开放 API 封装为 MCP 工具集，供任意 MCP 客户端调用。

启动::

    python -m mcp_server                         # streamable-HTTP，默认 127.0.0.1:8000/mcp
    python -m mcp_server --host 0.0.0.0 --port 8000
    python -m mcp_server --transport stdio       # 本地调试

对外导出 ``mcp``（MCPServer 实例）与 ``main``（启动入口），
便于 ``python -m mcp_server`` 或 MCP CLI 导入。
"""
from .server import main, mcp

__all__ = ["main", "mcp"]
